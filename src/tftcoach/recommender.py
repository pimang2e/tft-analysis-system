import sqlite3

from .database import Database
from .models import GameContext, Recommendation


COST_POOLS = {1: 377, 2: 286, 3: 234, 4: 156, 5: 130}

ACTION_ORDER = {
    "2성 찍기": 6,
    "기물 판매 후 이자 모으기": 14,
    "별업 보류": 7,
    "증강 선택": 1,
    "아이템 장착": 2,
    "기물 구매": 3,
    "조합 변경": 4,
    "레벨업": 5,
    "롤링": 6,
    "리롤로 증강 보강": 7,
    "기물 판매": 8,
    "아이템 교체": 9,
    "아이템 이월": 10,
    "포지셔닝": 11,
    "자리 옮기기": 12,
    "자리 교환": 13,
    "경제 모으기": 14,
    "상위 배치 유지": 15,
}

ACTION_PREREQUISITES = {
    "아이템 교체": ("아이템 장착",),
    "아이템 이월": ("아이템 장착",),
    "조합 변경": ("기물 구매",),
    "레벨업": ("경제 모으기",),
    "롤링": ("기물 구매",),
    "자리 옮기기": ("포지셔닝",),
    "자리 교환": ("포지셔닝",),
}

MAX_COMPOSITION_CANDIDATES = 5

ACTION_PRIORITIES = (
    "상위 배치 유지",
    "경제 모으기",
    "레벨업",
    "롤링",
    "리롤로 증강 보강",
    "아이템 장착",
    "아이템 교체",
    "아이템 이월",
    "기물 구매",
    "기물 판매",
    "조합 변경",
    "포지셔닝",
    "자리 옮기기",
    "자리 교환",
    "증강 선택",
    "2성 찍기",
    "기물 판매 후 이자 모으기",
    "별업 보류",
)


class Recommender:
    def __init__(self, database: Database | None = None) -> None:
        self.database = database or Database()

    def recommend(self, context: GameContext) -> list[Recommendation]:
        context = self._prune_composition_candidates(context)
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
                    execution_order=ACTION_ORDER.get(action, 99),
                    prerequisites=ACTION_PREREQUISITES.get(action, ()),
                )
            )

        recommendations.sort(key=lambda item: (item.execution_order, -item.score))
        return recommendations

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

            if action == "아이템 장착" and context.items:
                score += 0.16
                reason = "보유 아이템을 핵심 기물에 장착해 전투 효율을 높임"
            elif action == "아이템 교체" and len(context.items) >= 3:
                score += 0.12
                reason = "현재 조합과 맞지 않는 아이템을 교체할 후보가 있음"
            elif action == "아이템 이월" and len(context.items) >= 6:
                score += 0.10
                reason = "아이템을 후반 핵심 기물로 이월할 여지가 있음"
            elif action == "기물 구매" and context.gold >= 10:
                score += 0.12
                reason = "보유 골드로 기물을 구매해 전력을 보강할 수 있음"
            elif action == "기물 판매" and len(context.board) >= 8:
                score += 0.10
                reason = "전력에 맞지 않는 기물을 판매해 자원과 조합을 재배치"
            elif action == "조합 변경" and len(context.units) <= 3:
                score += 0.12
                reason = "핵심 유닛과 아이템을 아우르는 다른 조합으로 전환"
            elif action == "포지셔닝" and context.opponents:
                score += 0.14
                reason = "상대 진형과 공격 배치를 고려해 포지셔닝을 조정"
            elif action == "자리 옮기기" and context.opponents:
                score += 0.13
                reason = "상대 공격 편중과 딜러 위치를 고려해 기물 위치를 이동"
            elif action == "자리 교환" and len(context.board) >= 6:
                score += 0.12
                reason = "핵심 딜러와 탱커의 좌우 위치를 교환해 생존성을 조정"
            elif action == "증강 선택" and context.health >= 35:
                score += 0.11
                reason = "현재 보드와 경제를 강화하는 증강을 우선 선택"

            scenario_score, scenario_reason = self._star_upgrade_scenario(context)
            if action == "2성 찍기":
                score += scenario_score
                reason = scenario_reason
            elif action == "기물 판매 후 이자 모으기":
                score += max(-0.20, 0.20 - scenario_score)
                reason = "희소한 별업 사본보다 현재 이자와 체력 안전도를 우선하는 상황을 반영"
            elif action == "별업 보류":
                score += 0.10 if context.health >= 45 else 0.04
                reason = "별업을 즉시 강행하지 않고 남은 골드와 체력 여력을 유지"

            board_size = len(context.board)
            opponent_count = len(context.opponents)

            if action == "롤링" and board_size >= 8:
                score -= 0.05
                reason = "이미 보드 인원이 충분하므로 무분별한 재리롤보다 합성과 배치에 집중"
            elif action == "레벨업" and board_size >= 8:
                score -= 0.08
                reason = "보드 인원은 충분하므로 새로운 유닛보다 현재 진형을 강화"
            elif action == "레벨업" and board_size <= 4:
                score += 0.12
                reason = "보드 인원이 부족해 유닛 풀 확대를 위한 레벨업이 우선"
            elif action == "상위 배치 유지" and opponent_count >= 5:
                score += 0.08
                reason = "다수 상대를 동시에 견제하는 구간이므로 검증된 배치를 유지"

            pool_probability = self._pool_probability(context)
            item_bonus = self._item_bonus(context)
            matchup_bonus = self._matchup_bonus(context)

            if action == "롤링":
                score += pool_probability * 0.18
                reason = "보유 유닛과 챔피언 풀 추정치가 롤링 성공 가능성에 반영됨"
            elif action == "레벨업":
                score += (0.16 - pool_probability * 0.05)
                reason = "레벨업은 유닛 풀 확장과 희귀 유닛 등장 가능성을 함께 반영"

            if action in ("상위 배치 유지", "리롤로 증강 보강"):
                score += item_bonus
                reason = "보유 아이템과 전투구도 보정을 반영"

            if action == "상위 배치 유지":
                score += matchup_bonus

            recommendations.append(
                Recommendation(
                    action=action,
                    score=round(score - rank * 0.01, 4),
                    sample_count=0,
                    confidence="낮음",
                    reason=reason,
                    execution_order=ACTION_ORDER.get(action, 99),
                    prerequisites=ACTION_PREREQUISITES.get(action, ()),
                )
            )

        recommendations.sort(key=lambda item: (item.execution_order, -item.score))
        return recommendations

    def _prune_composition_candidates(self, context: GameContext) -> GameContext:
        if len(context.units) <= MAX_COMPOSITION_CANDIDATES:
            return context

        scored_units = sorted(
            context.units,
            key=lambda unit: (
                unit.star * 2 + len(unit.items) + (unit.cost >= 4),
                unit.owned_count,
            ),
            reverse=True,
        )
        return GameContext(
            stage=context.stage,
            round_type=context.round_type,
            health=context.health,
            gold=context.gold,
            level=context.level,
            board=context.board,
            opponents=context.opponents,
            units=tuple(scored_units[:MAX_COMPOSITION_CANDIDATES]),
            items=context.items,
        )

    def _pool_probability(self, context: GameContext) -> float:
        if not context.units:
            return 0.0

        probabilities = []
        for unit in context.units:
            pool_size = COST_POOLS.get(unit.cost)
            if not pool_size:
                continue
            copies = max(1, pool_size - unit.owned_count)
            probability_per_slot = copies / pool_size
            shop_slots = 5 if context.level >= 8 else 4
            probability = 1.0 - (1.0 - probability_per_slot) ** shop_slots
            if unit.star == 2:
                probability *= 0.55
            probabilities.append(probability)

        return sum(probabilities) / len(probabilities) if probabilities else 0.0

    def _star_upgrade_scenario(self, context: GameContext) -> tuple[float, str]:
        one_star_units = [unit for unit in context.units if unit.star == 1]
        if not one_star_units:
            return -0.20, "현재 별업이 가능한 핵심 기물이 없어 별업 우선도는 낮음"

        best = max(one_star_units, key=lambda unit: unit.cost)
        required_copies = max(1, 3 - best.owned_count)
        interest = min(context.gold // 10, 5)

        if required_copies <= 1 and context.gold >= 20:
            return 0.20, "남은 사본 수가 적고 골드 여력이 있어 2성 직행 우선"
        if context.health <= 35 and required_copies <= 2:
            return 0.14, "체력이 낮아도 강한 2성 기물의 전투력 상승이 생존에 유리"
        if interest >= 3 and context.gold < 40:
            return -0.08, "추가 사본 구매보다 이자 골드와 경제 안전도가 우선"
        return 0.06, "별업 가능성을 유지하되 사본 비용과 이자를 함께 비교"

    def _item_bonus(self, context: GameContext) -> float:
        if not context.items:
            return 0.0

        unique_items = set(context.items)
        if len(unique_items) >= 6:
            return 0.08
        if len(unique_items) >= 3:
            return 0.04
        return 0.02

    def _matchup_bonus(self, context: GameContext) -> float:
        board_advantage = len(context.board) - len(context.opponents)
        health_factor = (context.health - 50) / 100
        return max(-0.10, min(0.10, board_advantage * 0.02 + health_factor * 0.08))
