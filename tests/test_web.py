from fastapi.testclient import TestClient

from tftcoach.web import app


client = TestClient(app)


def test_web_index_returns_interface():
    response = client.get("/")

    assert response.status_code == 200
    assert "TFT Coach 분석기" in response.text


def test_recommend_api_returns_ranked_actions():
    response = client.post(
        "/api/recommend",
        json={
            "stage": "4-5",
            "round_type": "pvplive",
            "health": 55,
            "gold": 30,
            "level": 8,
            "board": ["가렌", "샤코", "애쉬", "세트", "레이블", "벡스", "진", "카이사"],
            "opponents": ["상대1", "상대2", "상대3", "상대4"],
            "units": [],
            "items": ["거인학살자", "피바디", "밤의끝자락"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["recommendations"]
    assert payload["recommendations"][0]["action"]
