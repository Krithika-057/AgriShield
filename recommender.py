"""Core context-aware and collaborative treatment ranking for AgriShield."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).parent / "data"


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
