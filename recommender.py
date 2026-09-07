"""Core context-aware and collaborative treatment ranking for AgriShield."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).parent / "data"

CUSTOM_GROUND_TRUTH: dict[tuple[str, str], dict[str, int]] = {
    ("Tomato", "Late blight"): {"bio_trichoderma": 3, "copper_fixed": 2},
    ("Cucumber", "Powdery mildew"): {"potassium_bicarbonate": 3, "sulfur_wettable": 2},
    ("Tomato", "Aphid"): {"neem_azadirachtin": 3},
    ("Cabbage", "Caterpillar / armyworm"): {"bacillus_thuringiensis": 3, "spinosad": 2},
    ("Tomato", "Caterpillar / armyworm"): {"spinosad": 3, "bacillus_thuringiensis": 2},
}


@dataclass(frozen=True)
class WeatherContext:
    temperature_c: float
    humidity_pct: float
    rain_next_6h_mm: float
    dry_hours_next_12h: float

    @property
    def heat_band(self) -> str:
        if self.temperature_c >= 32:
            return "high"
        if self.temperature_c <= 27:
            return "low"
        return "moderate"


def load_records(filename: str) -> list[dict[str, Any]]:
    with (DATA_DIR / filename).open(encoding="utf-8") as file:
        return json.load(file)


def relevance_grade(success_rate: float) -> int:
    if success_rate >= 0.85:
        return 3
    if success_rate >= 0.75:
        return 2
    if success_rate >= 0.60:
        return 1
    return 0


def ground_truth_for(
    crop: str,
    diagnosis: str,
    outbreaks: list[dict[str, Any]],
) -> dict[str, int]:
    custom_ground_truth = CUSTOM_GROUND_TRUTH.get((crop, diagnosis))
    if custom_ground_truth is not None:
        return custom_ground_truth

    matching_rows = [
        row for row in outbreaks
        if row["crop"] == crop and row["diagnosis"] == diagnosis
    ]
    return {
        treatment_id: relevance_grade(sum(row["success_rate"] for row in rows) / len(rows))
        for treatment_id in {row["treatment_id"] for row in matching_rows}
        for rows in [[row for row in matching_rows if row["treatment_id"] == treatment_id]]
    }


def ranking_metrics_at_k(
    recommended_ids: list[str],
    relevance: dict[str, int],
    k: int,
) -> dict[str, float]:
    ranked_ids = recommended_ids[:k]
    relevant_count = sum(treatment_id in relevance for treatment_id in ranked_ids)
    precision = relevant_count / k if k else 0.0
    recall = relevant_count / len(relevance) if relevance else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    dcg = sum(
        (2 ** relevance.get(treatment_id, 0) - 1) / math.log2(rank + 2)
        for rank, treatment_id in enumerate(ranked_ids)
    )
    ideal_grades = sorted(relevance.values(), reverse=True)[:k]
    ideal_dcg = sum(
        (2 ** grade - 1) / math.log2(rank + 2)
        for rank, grade in enumerate(ideal_grades)
    )
    ndcg = dcg / ideal_dcg if ideal_dcg else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "ndcg": ndcg,
    }


def _weather_fit(treatment: dict[str, Any], weather: WeatherContext) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if weather.rain_next_6h_mm > 2 and treatment["rain_sensitivity"] == "avoid_rain":
        return False, ["Rain is expected within 6 hours; foliar product would be washed off."]
    if weather.dry_hours_next_12h < treatment["min_dry_hours"]:
        return False, [f"Needs {treatment['min_dry_hours']} dry hours, but only {weather.dry_hours_next_12h:g} are forecast."]
    if weather.temperature_c >= 32 and treatment["heat_fit"] == "low":
        return False, ["High heat raises phytotoxicity risk for this treatment."]
    if weather.humidity_pct >= 80 and treatment["humidity_fit"] == "high":
        reasons.append("Strong fit for the current high-humidity disease pressure.")
    elif weather.humidity_pct < 60 and treatment["humidity_fit"] == "moderate":
        reasons.append("Moderate fit for the current drier canopy conditions.")
    return True, reasons


def _collaborative_signal(treatment_id: str, crop: str, diagnosis: str, outbreaks: list[dict[str, Any]]) -> tuple[float, int, float]:
    matches = [
        row for row in outbreaks
        if row["treatment_id"] == treatment_id and row["diagnosis"] == diagnosis
    ]
    if not matches:
        return 0.45, 0, 0.0
    crop_matches = [row for row in matches if row["crop"] == crop]
    evidence = crop_matches or matches
    success = sum(row["success_rate"] for row in evidence) / len(evidence)
    cost = sum(row["cost_per_acre"] for row in evidence) / len(evidence)
    return success, len(evidence), cost


def recommend(
    crop: str,
    diagnosis: str,
    weather: WeatherContext,
    preferred_category: str = "Any",
    treatments: list[dict[str, Any]] | None = None,
    outbreaks: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    treatments = treatments if treatments is not None else load_records("treatments.json")
    outbreaks = outbreaks if outbreaks is not None else load_records("outbreaks.json")
    recommendations: list[dict[str, Any]] = []
    for treatment in treatments:
        if diagnosis not in treatment["targets"] or crop not in treatment["crops"]:
            continue
        if preferred_category != "Any" and treatment["category"] != preferred_category:
            continue
        allowed, weather_reasons = _weather_fit(treatment, weather)
        if not allowed:
            continue
        success, evidence_count, historical_cost = _collaborative_signal(treatment["id"], crop, diagnosis, outbreaks)
        cost = historical_cost or treatment["cost"]
        cost_score = max(0.0, 1 - (cost / 5))
        context_score = 1.0 + (0.08 if weather_reasons else 0.0)
        score = (success * 0.62 + cost_score * 0.18 + context_score * 0.20) * 100
        reasons = weather_reasons + [
            f"{success:.0%} average success across {evidence_count} similar outbreak{'s' if evidence_count != 1 else ''}." if evidence_count else "No matching local history yet; ranked using the treatment profile.",
            f"Estimated material cost: ${cost:.2f}/acre.",
        ]
        recommendations.append({**treatment, "score": round(score, 1), "success_rate": success, "evidence_count": evidence_count, "estimated_cost": cost, "reasons": reasons})
    return sorted(recommendations, key=lambda item: item["score"], reverse=True)
