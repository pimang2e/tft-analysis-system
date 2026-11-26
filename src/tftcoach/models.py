from dataclasses import dataclass


@dataclass(frozen=True)
class UnitState:
    name: str
    cost: int
    star: int = 1
    items: tuple[str, ...] = ()
    owned_count: int = 0
    traits: tuple[str, ...] = ()


@dataclass(frozen=True)
class GameContext:
    stage: str
    round_type: str
    health: int
    gold: int
    level: int
    board: tuple[str, ...] = ()
    opponents: tuple[str, ...] = ()
    units: tuple[UnitState, ...] = ()
    items: tuple[str, ...] = ()


@dataclass(frozen=True)
class Recommendation:
    action: str
    score: float
    sample_count: int
    confidence: str
    reason: str
    execution_order: int = 0
    prerequisites: tuple[str, ...] = ()
