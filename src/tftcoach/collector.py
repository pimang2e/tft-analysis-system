import json
from datetime import datetime, timezone
from urllib.request import Request, urlopen

from .database import Database


class DataDragonCollector:
    base_url = "https://ddragon.leagueoflegends.com"

    def __init__(self, locale: str = "ko_KR", database: Database | None = None) -> None:
        self.locale = locale
        self.database = database or Database()

    def _get_json(self, url: str) -> dict:
        request = Request(url, headers={"User-Agent": "TFT-Coach/0.1"})
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))

    def collect(self) -> dict:
        versions = self._get_json(f"{self.base_url}/api/versions.json")
        if not versions:
            raise RuntimeError("Data Dragon returned no versions")

        version = versions[0]
        collected_at = datetime.now(timezone.utc).isoformat()
        datasets = (
            ("tft-champion", "champion"),
            ("tft-trait", "trait"),
            ("tft-augments", "augment"),
            ("tft-item", "item"),
        )
        counts: dict[str, int] = {}

        with self.database.connect() as connection:
            for dataset, key in datasets:
                payload = self._get_json(
                    f"{self.base_url}/cdn/{version}/data/{self.locale}/{dataset}.json"
                )
                count = len(payload.get("data", {}))
                counts[f"{key}_count"] = count
                connection.execute(
                    """
                    INSERT INTO metadata_versions
                        (source, locale, version, collected_at, payload)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(source, locale, version) DO UPDATE SET
                        collected_at = excluded.collected_at,
                        payload = excluded.payload
                    """,
                    (
                        f"riot-datadragon:{dataset}",
                        self.locale,
                        version,
                        collected_at,
                        json.dumps(payload, ensure_ascii=False),
                    ),
                )

        return {
            "source": "Riot Data Dragon",
            "locale": self.locale,
            "version": version,
            "collected_at": collected_at,
            **counts,
        }
