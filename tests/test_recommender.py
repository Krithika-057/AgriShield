from recommender import WeatherContext, ground_truth_for, ranking_metrics_at_k, recommend


def test_rain_removes_foliar_recommendations():
    weather = WeatherContext(26, 84, 10, 2)
    assert recommend("Tomato", "Late blight", weather) == []


def test_humidity_and_history_rank_late_blight():
    weather = WeatherContext(25, 90, 0, 10)
    results = recommend("Tomato", "Late blight", weather)
    assert results
    assert results[0]["id"] == "bio_trichoderma"
    assert results[0]["evidence_count"] > 0


def test_category_filter_is_respected():
    weather = WeatherContext(25, 70, 0, 10)
    results = recommend("Tomato", "Aphid", weather, preferred_category="Organic")
    assert results
    assert all(result["category"] == "Organic" for result in results)


def test_custom_ground_truth_is_available_for_demo_query():
    ground_truth = ground_truth_for("Tomato", "Late blight", [])
    assert ground_truth == {"bio_trichoderma": 3, "copper_fixed": 2}


def test_prediction_metrics_are_calculated_at_each_rank():
    ground_truth = {"bio_trichoderma": 3, "copper_fixed": 2}
    metrics = ranking_metrics_at_k(["bio_trichoderma", "copper_fixed"], ground_truth, 1)
    assert metrics == {"precision": 1.0, "recall": 0.5, "f1": 2 / 3, "ndcg": 1.0}
