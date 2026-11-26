import json
import os
from datetime import datetime, timezone
from urllib.parse import quote
from urllib.error import HTTPError
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


class RiotMatchCollector:
    platform_hosts = {
        "KR": "kr",
        "NA": "na1",
        "EUW": "euw1",
        "JP": "jp1",
    }
    regional_hosts = {
        "KR": "asia",
        "NA": "americas",
        "EUW": "europe",
        "JP": "asia",
    }

    def __init__(
        self,
        region: str = "KR",
        api_key: str | None = None,
        database: Database | None = None,
    ) -> None:
        self.region = region.upper()
        self.api_key = api_key or os.getenv("RIOT_API_KEY")
        self.database = database or Database()

    def _get_json(self, url: str) -> dict | list:
        if not self.api_key:
            raise RuntimeError("RIOT_API_KEY 환경변수가 설정되어 있지 않습니다")

        request = Request(
            url,
            headers={
                "X-Riot-Token": self.api_key,
                "User-Agent": "TFT-Coach/0.1",
            },
        )
        try:
            with urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            if error.code == 401:
                raise RuntimeError("Riot API 키가 만료됐거나 유효하지 않습니다") from error
            if error.code == 403:
                raise RuntimeError("이 Riot API 키로 해당 엔드포인트에 접근할 권한이 없습니다") from error
            if error.code == 429:
                raise RuntimeError("Riot API 요청 제한에 도달했습니다. 잠시 후 다시 시도하세요") from error
            raise RuntimeError(f"Riot API 요청 실패: HTTP {error.code}") from error

    def collect_challenger_matches(self, match_limit: int = 20) -> dict:
        platform = self.platform_hosts.get(self.region)
        regional = self.regional_hosts.get(self.region)
        if not platform or not regional:
            raise ValueError(f"지원하지 않는 지역입니다: {self.region}")

        leaderboard = self._get_json(
            f"https://{platform}.api.riotgames.com/tft/league/v1/challenger"
        )
        entries = leaderboard.get("entries", [])
        collected_at = datetime.now(timezone.utc).isoformat()
        match_count = 0
        participant_count = 0

        with self.database.connect() as connection:
            for entry in entries:
                puuid = entry.get("puuid")
                if not puuid:
                    summoner_id = quote(entry["summonerId"])
                    summoner = self._get_json(
                        f"https://{platform}.api.riotgames.com/tft/summoner/v1/summoners/{summoner_id}"
                    )
                    puuid = summoner["puuid"]

                connection.execute(
                    """
                    INSERT INTO riot_players
                        (puuid, region, rank_tier, rank, wins, losses, collected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(puuid) DO UPDATE SET
                        region = excluded.region,
                        rank_tier = excluded.rank_tier,
                        rank = excluded.rank,
                        wins = excluded.wins,
                        losses = excluded.losses,
                        collected_at = excluded.collected_at
                    """,
                    (
                        puuid,
                        self.region,
                        "challenger",
                        entry.get("rank"),
                        entry.get("wins", 0),
                        entry.get("losses", 0),
                        collected_at,
                    ),
                )

                match_ids = self._get_json(
                    f"https://{regional}.api.riotgames.com/tft/match/v1/matches/by-puuid/{quote(puuid)}/ids?start=0&count={match_limit}"
                )
                for match_id in match_ids:
                    payload = self._get_json(
                        f"https://{regional}.api.riotgames.com/tft/match/v1/matches/{quote(match_id)}"
                    )
                    info = payload.get("info", {})
                    game_version = info.get("game_version", "")
                    set_number = info.get("tft_set_core_name") or info.get("tft_set_number", "")
                    connection.execute(
                        """
                        INSERT INTO riot_matches
                            (match_id, patch, set_number, region, game_length, payload, collected_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(match_id) DO UPDATE SET
                            patch = excluded.patch,
                            set_number = excluded.set_number,
                            region = excluded.region,
                            game_length = excluded.game_length,
                            payload = excluded.payload,
                            collected_at = excluded.collected_at
                        """,
                        (
                            match_id,
                            game_version,
                            str(set_number),
                            self.region,
                            info.get("game_length"),
                            json.dumps(payload, ensure_ascii=False),
                            collected_at,
                        ),
                    )
                    match_count += 1

                    for participant in info.get("participants", []):
                        participant_puuid = participant.get("puuid")
                        if not participant_puuid:
                            continue
                        connection.execute(
                            """
                            INSERT INTO match_participants
                                (match_id, puuid, region, rank_tier, placement, level,
                                 last_round, gold_left, total_damage, traits_json,
                                 units_json, augments_json, collected_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(match_id, puuid) DO UPDATE SET
                                rank_tier = excluded.rank_tier,
                                placement = excluded.placement,
                                level = excluded.level,
                                last_round = excluded.last_round,
                                gold_left = excluded.gold_left,
                                total_damage = excluded.total_damage,
                                traits_json = excluded.traits_json,
                                units_json = excluded.units_json,
                                augments_json = excluded.augments_json,
                                collected_at = excluded.collected_at
                            """,
                            (
                                match_id,
                                participant_puuid,
                                self.region,
                                "challenger",
                                participant.get("placement", 8),
                                participant.get("level"),
                                participant.get("last_round"),
                                participant.get("gold_left"),
                                participant.get("total_damage_to_players"),
                                json.dumps(participant.get("traits", []), ensure_ascii=False),
                                json.dumps(participant.get("units", []), ensure_ascii=False),
                                json.dumps(participant.get("augments", []), ensure_ascii=False),
                                collected_at,
                            ),
                        )
                        participant_count += 1

        return {
            "region": self.region,
            "players": len(entries),
            "matches": match_count,
            "participants": participant_count,
            "collected_at": collected_at,
        }
