import pytest

from tftcoach.collector import RiotMatchCollector
from tftcoach.database import Database
from tftcoach.models import GameContext, UnitState
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


def test_full_board_prioritizes_stable_positioning(tmp_path):
    database = Database(tmp_path / "test.sqlite3")
    recommendations = Recommender(database).recommend(
        GameContext(
            stage="4-1",
            round_type="pvplive",
            health=70,
            gold=25,
            level=8,
            board=("가렌", "샤코", "애쉬", "세트", "레이블", "벡스", "진", "카이사"),
            opponents=("상대1", "상대2", "상대3", "상대4", "상대5", "상대6"),
        )
    )

    by_action = {item.action: item for item in recommendations}
    assert by_action["상위 배치 유지"].score > by_action["레벨업"].score


def test_unit_pool_and_items_change_roll_score(tmp_path):
    database = Database(tmp_path / "test.sqlite3")
    recommendations = Recommender(database).recommend(
        GameContext(
            stage="4-5",
            round_type="pvplive",
            health=62,
            gold=30,
            level=8,
            board=("아펠", "이렐리아", "가렌", "리산드라", "진", "세트", "샤코", "애쉬"),
            opponents=("상대1", "상대2", "상대3", "상대4"),
            units=(
                UnitState(name="가렌", cost=1, star=1, owned_count=0),
                UnitState(name="리산드라", cost=5, star=1, owned_count=2),
            ),
            items=("거인학살자", "피바디", "밤의끝자락", "최후의속삭임"),
        )
    )

    by_action = {item.action: item for item in recommendations}
    assert by_action["롤링"].score > 0.5


def test_position_and_item_actions_are_rankable(tmp_path):
    database = Database(tmp_path / "test.sqlite3")
    recommendations = Recommender(database).recommend(
        GameContext(
            stage="5-1",
            round_type="pvplive",
            health=55,
            gold=25,
            level=8,
            board=("가렌", "샤코", "애쉬", "세트", "레이블", "벡스", "진", "카이사"),
            opponents=("상대1", "상대2", "상대3", "상대4", "상대5"),
            units=(UnitState(name="가렌", cost=1, items=("거인학살자",)),),
            items=("거인학살자", "피바디", "밤의끝자락", "최후의속삭임"),
        )
    )

    actions = {item.action: item for item in recommendations}
    assert "아이템 장착" in actions
    assert "기물 판매" in actions
    assert "자리 옮기기" in actions
    assert "자리 교환" in actions
    assert "증강 선택" in actions


def test_recommendations_include_execution_order(tmp_path):
    database = Database(tmp_path / "test.sqlite3")
    recommendations = Recommender(database).recommend(
        GameContext(
            stage="5-1",
            round_type="pvplive",
            health=55,
            gold=25,
            level=8,
            board=("가렌", "샤코", "애쉬", "세트", "레이블", "벡스", "진", "카이사"),
            opponents=("상대1", "상대2", "상대3", "상대4", "상대5"),
            units=(UnitState(name="가렌", cost=1, items=("거인학살자",)),),
            items=("거인학살자", "피바디"),
        )
    )

    position_swap = next(item for item in recommendations if item.action == "자리 교환")
    positioning = next(item for item in recommendations if item.action == "포지셔닝")

    assert position_swap.execution_order > positioning.execution_order
    assert position_swap.prerequisites == ("포지셔닝",)


def test_star_upgrade_and_interest_are_separate_choices(tmp_path):
    database = Database(tmp_path / "test.sqlite3")

    star_context = Recommender(database).recommend(
        GameContext(
            stage="3-5",
            round_type="pvplive",
            health=60,
            gold=30,
            level=7,
            units=(UnitState(name="가렌", cost=1, star=1, owned_count=2),),
        )
    )
    star_actions = {item.action: item for item in star_context}

    assert star_actions["2성 찍기"].score > star_actions["기물 판매 후 이자 모으기"].score


def test_composition_candidates_are_pruned(tmp_path):
    database = Database(tmp_path / "test.sqlite3")
    recommender = Recommender(database)

    context = GameContext(
        stage="5-5",
        round_type="pvplive",
        health=50,
        gold=30,
        level=8,
        units=tuple(
            UnitState(name=f"기물{i}", cost=i % 5 + 1, star=2 if i < 2 else 1)
            for i in range(9)
        ),
    )

    pruned = recommender._prune_composition_candidates(context)

    assert len(pruned.units) == 5


def test_match_collector_requires_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("RIOT_API_KEY", raising=False)
    collector = RiotMatchCollector(database=Database(tmp_path / "test.sqlite3"))

    with pytest.raises(RuntimeError, match="RIOT_API_KEY"):
        collector.collect_challenger_matches(match_limit=1)
