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

CREATE INDEX IF NOT EXISTS idx_observations_context
ON observations(patch, region, rank_tier, stage, round_type);
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
