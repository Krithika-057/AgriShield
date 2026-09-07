from recommender import WeatherContext, recommend


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
