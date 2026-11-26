import sqlite3

from .database import Database
from .models import GameContext, Recommendation


ACTION_PRIORITIES = (
    "상위 배치 유지",
    "경제 모으기",
    "레벨업",
    "롤링",
    "리롤로 증강 보강",
)


class Recommender:
    def __init__(self, database: Database | None = None) -> None:
        self.database = database or Database()

    def recommend(self, context: GameContext) -> list[Recommendation]:
        observations = self._load_observations(context)
        if observations:
            return self._score_observations(observations)
        return self._score_heuristics(context)

    def _load_observations(self, context: GameContext) -> list[tuple]:
        with self.database.connect() as connection:
            return connection.execute(
                """
                SELECT action, result, placement
                FROM observations
                WHERE stage = ? AND round_type = ?
                """,
                (context.stage, context.round_type),
            ).fetchall()

    def _score_observations(self, observations: list[tuple]) -> list[Recommendation]:
        grouped: dict[str, list[tuple]] = {}
        for action, result, placement in observations:
            grouped.setdefault(action, []).append((result, placement))

        recommendations = []
        for action, rows in grouped.items():
            wins = sum(result == "win" for result, _ in rows)
            placements = [placement for _, placement in rows if placement is not None]
            win_rate = wins / len(rows)
            placement_score = (sum(placements) / len(placements) / 8.0) if placements else 0.5
            score = win_rate * 0.7 + (1.0 - placement_score) * 0.3
            sample_count = len(rows)
            confidence = "높음" if sample_count >= 100 else "중간" if sample_count >= 20 else "낮음"
            recommendations.append(
                Recommendation(
                    action=action,
                    score=round(score, 4),
                    sample_count=sample_count,
                    confidence=confidence,
                    reason="현재 구간과 라운드 상황의 실제 승률 및 최종 등수를 반영",
                )
            )

        return sorted(recommendations, key=lambda item: item.score, reverse=True)

    def _score_heuristics(self, context: GameContext) -> list[Recommendation]:
        recommendations = []
        for rank, action in enumerate(ACTION_PRIORITIES):
            score = 0.5
            reason = "실전 표본이 없어 기본 보수적 전략을 제안"

            if action == "경제 모으기" and context.gold >= 50:
                score += 0.25
                reason = "높은 이자 골드 구간이므로 경제 유지를 우선"
            elif action == "레벨업" and context.gold >= 30 and context.level <= 7:
                score += 0.18
                reason = "레벨업 비용을 감당할 수 있고 유닛 풀을 넓힐 여지가 있음"
            elif action == "롤링" and context.gold >= 20:
                score += 0.12
                reason = "보유 골드로 전력 강화가 가능"
            elif action == "상위 배치 유지" and context.health >= 60:
                score += 0.15
                reason = "체력이 여유 있어 성급한 변화를 줄이고 리듬을 유지"

            recommendations.append(
                Recommendation(
                    action=action,
                    score=round(score - rank * 0.01, 4),
                    sample_count=0,
                    confidence="낮음",
                    reason=reason,
                )
            )

        return sorted(recommendations, key=lambda item: item.score, reverse=True)
