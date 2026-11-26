from tftcoach.database import Database
from tftcoach.models import GameContext
from tftcoach.recommender import Recommender


def test_heuristic_recommendation_is_ranked(tmp_path):
    database = Database(tmp_path / "test.sqlite3")
    recommendations = Recommender(database).recommend(
        GameContext(stage="3-5", round_type="pvplive", health=70, gold=55, level=7)
    )

    assert recommendations
    assert recommendations[0].confidence == "낮음"
    assert recommendations[0].sample_count == 0


def test_observed_action_is_ranked_by_samples(tmp_path):
    database = Database(tmp_path / "test.sqlite3")
    with database.connect() as connection:
        connection.executemany(
            """
            INSERT INTO observations
                (patch, region, rank_tier, stage, round_type, health, gold, level,
                 board_json, opponent_json, action, result, placement, collected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("16.1", "KR", "challenger", "3-5", "pvplive", 50, 30, 7, "[]", "[]", "레벨업", "win", 2, "2026-01-01"),
                ("16.1", "KR", "challenger", "3-5", "pvplive", 50, 30, 7, "[]", "[]", "레벨업", "win", 3, "2026-01-01"),
                ("16.1", "KR", "challenger", "3-5", "pvplive", 50, 30, 7, "[]", "[]", "경제 모으기", "loss", 6, "2026-01-01"),
            ],
        )

    recommendations = Recommender(database).recommend(
        GameContext(stage="3-5", round_type="pvplive", health=50, gold=30, level=7)
    )

    assert recommendations[0].action == "레벨업"
    assert recommendations[0].sample_count == 2
