from dataclasses import dataclass


@dataclass(frozen=True)
class GameContext:
    stage: str
    round_type: str
    health: int
    gold: int
    level: int
    board: tuple[str, ...] = ()
    opponents: tuple[str, ...] = ()


@dataclass(frozen=True)
class Recommendation:
    action: str
    score: float
    sample_count: int
    confidence: str
    reason: str
