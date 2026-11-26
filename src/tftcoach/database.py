import sqlite3
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata_versions (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    locale TEXT NOT NULL,
    version TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    payload TEXT NOT NULL,
    UNIQUE(source, locale, version)
);

CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY,
    patch TEXT NOT NULL,
    region TEXT NOT NULL,
    rank_tier TEXT NOT NULL,
    stage TEXT NOT NULL,
    round_type TEXT NOT NULL,
    health INTEGER NOT NULL,
    gold INTEGER NOT NULL,
    level INTEGER NOT NULL,
    board_json TEXT NOT NULL,
    opponent_json TEXT NOT NULL,
    action TEXT NOT NULL,
    result TEXT NOT NULL,
    placement INTEGER,
    collected_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS riot_players (
    puuid TEXT PRIMARY KEY,
    region TEXT NOT NULL,
    rank_tier TEXT NOT NULL,
    rank TEXT,
    wins INTEGER,
    losses INTEGER,
    collected_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS riot_matches (
    match_id TEXT PRIMARY KEY,
    patch TEXT,
    set_number TEXT,
    region TEXT NOT NULL,
    game_length REAL,
    payload TEXT NOT NULL,
    collected_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS match_participants (
    match_id TEXT NOT NULL,
    puuid TEXT NOT NULL,
    region TEXT NOT NULL,
    rank_tier TEXT,
    placement INTEGER NOT NULL,
    level INTEGER,
    last_round INTEGER,
    gold_left INTEGER,
    total_damage INTEGER,
    traits_json TEXT NOT NULL,
    units_json TEXT NOT NULL,
    augments_json TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    PRIMARY KEY(match_id, puuid)
);

CREATE INDEX IF NOT EXISTS idx_observations_context
ON observations(patch, region, rank_tier, stage, round_type);

CREATE INDEX IF NOT EXISTS idx_match_participants_context
ON match_participants(region, rank_tier, placement, last_round);
"""


class Database:
    def __init__(self, path: str | Path = "data/tftcoach.sqlite3") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(SCHEMA)
        return connection
