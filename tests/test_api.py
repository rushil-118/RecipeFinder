import pytest

from recipefinder.api import create_app
from recipefinder.catalog import Catalog


@pytest.fixture
def client():
    return create_app({"APP_VERSION": "v1", "GIT_SHA": "abc123"}).test_client()


def test_health_ready_version(client):
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200
    assert client.get("/version").get_json() == {"version": "v1", "commit": "abc123"}


def test_not_ready_when_catalog_is_empty():
    app = create_app(catalog=Catalog([]))
    c = app.test_client()
    assert c.get("/ready").status_code == 503
    assert c.get("/health").status_code == 200


def test_fail_health_flag_makes_liveness_fail():
    c = create_app({"FAIL_HEALTH": "true"}).test_client()
    assert c.get("/health").status_code == 500
    assert c.get("/ready").status_code == 200


def test_queries_match_the_cli(client):
    assert client.get("/recipes/cuisines").get_json()["cuisines"][0] == "French"
    assert client.get("/recipes/count?cuisine=italian").get_json()["count"] == 7
    assert "Pad Thai" in client.get("/recipes/names?cuisine=Thai").get_json()["names"]
    veg = client.get("/recipes/quick?max_minutes=10&vegetarian=true").get_json()["recipes"]
    assert veg and all(r["vegetarian"] and r["minutes"] <= 10 for r in veg)
    assert client.get("/recipes/calories?cuisine=Indian").get_json()["average_calories"] == 474.3


@pytest.mark.parametrize("url", [
    "/recipes/count", "/recipes/names", "/recipes/quick", "/recipes/calories",
    "/recipes/quick?max_minutes=abc", "/recipes/quick?max_minutes=0",
    "/recipes/quick?max_minutes=5&vegetarian=maybe",
])
def test_bad_requests_return_400(client, url):
    assert client.get(url).status_code == 400


def test_unknown_cuisine(client):
    assert client.get("/recipes/count?cuisine=Martian").get_json()["count"] == 0
    assert client.get("/recipes/calories?cuisine=Martian").status_code == 404


def test_nutrition_feature_flag_off_returns_403():
    c = create_app({"FEATURE_NUTRITION": "false"}).test_client()
    assert c.get("/recipes/calories?cuisine=Indian").status_code == 403
    assert c.get("/recipes/count?cuisine=Indian").status_code == 200


def test_unknown_route_and_method(client):
    assert client.get("/nope").status_code == 404
    assert client.post("/recipes/cuisines").status_code == 405


def test_request_id_generated_and_echoed(client):
    assert client.get("/recipes/cuisines").headers["X-Request-Id"]
    assert client.get("/recipes/cuisines", headers={"X-Request-Id": "abc"}).headers["X-Request-Id"] == "abc"


def test_metrics_reflect_traffic_and_use_route_patterns(client):
    client.get("/recipes/count?cuisine=Thai")
    client.get("/totally/unknown")
    text = client.get("/metrics").get_data(as_text=True)
    assert 'http_requests_total{method="GET",route="/recipes/count",status="200"} 1.0' in text
    assert 'route="unmatched"' in text
    assert "/totally" not in text
    assert "recipes_loaded 37.0" in text
    assert 'feature_enabled{feature="nutrition"} 1.0' in text
    assert 'build_info{commit="abc123",version="v1"} 1.0' in text


def test_bad_data_file_fails_at_startup(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("name,cuisine,minutes,calories,vegetarian\nSoup,French,ten,1,true\n")
    with pytest.raises(ValueError):
        create_app({"DATA_PATH": str(bad)})
