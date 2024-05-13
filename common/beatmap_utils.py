from __future__ import annotations

import random
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from enum import IntEnum
from typing import Any
from typing import Optional

import settings
from objects import glob

ONE_DAY = 86_400


class RankedStatus(IntEnum):
    NOT_SUBMITTED = -1
    PENDING = 0
    UPDATE_AVAILABLE = 1
    RANKED = 2
    APPROVED = 3
    QUALIFIED = 4
    LOVED = 5

    def osu_api(self) -> int:
        return {
            self.PENDING: 0,
            self.RANKED: 1,
            self.APPROVED: 2,
            self.QUALIFIED: 3,
            self.LOVED: 4,
        }[self]

    # TODO: do the defaults to .get below make sense?
    #       should we be enforcing existence? (e.g. {}[x])

    @classmethod
    def from_osu_api(cls, osu_api_status: int) -> RankedStatus:
        return {
            -2: cls.PENDING,  # graveyard
            -1: cls.PENDING,  # wip
            0: cls.PENDING,
            1: cls.RANKED,
            2: cls.APPROVED,
            3: cls.QUALIFIED,
            4: cls.LOVED,
        }.get(osu_api_status, cls.UPDATE_AVAILABLE)

    @classmethod
    def from_direct(cls, direct_status: int) -> RankedStatus:
        return {
            0: cls.RANKED,
            2: cls.PENDING,
            3: cls.QUALIFIED,
            5: cls.PENDING,  # graveyard
            7: cls.RANKED,  # played before
            8: cls.LOVED,
        }.get(direct_status, cls.UPDATE_AVAILABLE)


def _should_get_updates(ranked_status: int, last_updated: datetime) -> bool:
    if ranked_status is RankedStatus.QUALIFIED:
        update_interval = timedelta(minutes=5)
    elif ranked_status is RankedStatus.PENDING:
        update_interval = timedelta(minutes=10)
    elif ranked_status is RankedStatus.LOVED:
        # loved maps can *technically* be updated
        update_interval = timedelta(days=1)
    elif ranked_status in (RankedStatus.RANKED, RankedStatus.APPROVED):
        # in very rare cases, the osu! team has updated ranked/appvoed maps
        # this is usually done to remove things like inappropriate content
        update_interval = timedelta(days=1)
    else:
        raise NotImplementedError(f"Unknown ranked status: {ranked_status}")

    return last_updated <= (datetime.now() - update_interval)


@dataclass
class Beatmap:
    md5: str
    id: int
    set_id: int

    song_name: str

    status: RankedStatus

    plays: int
    passes: int
    mode: int  # vanilla mode

    od: float
    ar: float

    hit_length: int

    last_update: int = 0

    max_combo: int = 0
    bpm: int = 0
    filename: str = ""
    frozen: bool = False
    rating: Optional[float] = None

    @property
    def gives_pp(self) -> bool:
        return self.status in (RankedStatus.RANKED, RankedStatus.APPROVED)

    @property
    def has_leaderboard(self) -> bool:
        return self.status >= RankedStatus.RANKED

    @property
    def deserves_update(self) -> bool:
        """Checks if there should be an attempt to update a map/check if
        should be updated."""

        return _should_get_updates(
            int(self.status),
            datetime.fromtimestamp(self.last_update),
        )

    def osu_string(self, score_count: int, rating: float) -> str:
        return (
            f"{int(self.status)}|false|{self.id}|{self.set_id}|{score_count}|0|\n"  # |0| = featured artist bs
            f"0\n{self.song_name}\n{rating:.1f}"  # 0 = offset
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "beatmap_md5": self.md5,
            "beatmap_id": self.id,
            "beatmapset_id": self.set_id,
            "song_name": self.song_name,
            "ranked": self.status.value,
            "playcount": self.plays,
            "passcount": self.passes,
            "mode": self.mode,
            "od": self.od,
            "ar": self.ar,
            "hit_length": self.hit_length,
            "latest_update": self.last_update,
            "max_combo": self.max_combo,
            "bpm": self.bpm,
            "file_name": self.filename,
            "ranked_status_freezed": self.frozen,
            "rating": self.rating,
        }

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> Beatmap:
        return cls(
            md5=mapping["beatmap_md5"],
            id=mapping["beatmap_id"],
            set_id=mapping["beatmapset_id"],
            song_name=mapping["song_name"],
            status=RankedStatus(mapping["ranked"]),
            plays=mapping["playcount"],
            passes=mapping["passcount"],
            mode=mapping["mode"],
            od=mapping["od"],
            ar=mapping["ar"],
            hit_length=mapping["hit_length"],
            last_update=mapping["latest_update"],
            max_combo=mapping["max_combo"],
            bpm=mapping["bpm"],
            filename=mapping["file_name"],
            frozen=mapping["ranked_status_freezed"],
            rating=mapping["rating"],
        )


async def update_beatmap(beatmap: Beatmap) -> Optional[Beatmap]:
    if not beatmap.deserves_update:
        return beatmap

    new_beatmap = await id_from_api(beatmap.id, should_save=False)
    if new_beatmap is None:
        # it's now unsubmitted!

        await glob.db.execute(
            "DELETE FROM beatmaps WHERE beatmap_md5 = :old_md5",
            {"old_md5": beatmap.md5},
        )

        return None

    # handle deleting the old beatmap etc.
    if new_beatmap.md5 != beatmap.md5:
        # delete any instances of the old map
        await glob.db.execute(
            "DELETE FROM beatmaps WHERE beatmap_md5 = :old_md5",
            {"old_md5": beatmap.md5},
        )

        if beatmap.frozen:
            # if the previous version is status frozen
            # we should force the old status on the new version
            new_beatmap.status = beatmap.status
            new_beatmap.frozen = True

        # update for new shit
        new_beatmap.last_update = int(time.time())

        await save(new_beatmap)
        return new_beatmap
    else:
        beatmap.last_update = int(time.time())
        await save(beatmap)

        return beatmap


async def fetch_by_md5(md5: str) -> Optional[Beatmap]:
    if beatmap := await md5_from_database(md5):
        return beatmap

    if beatmap := await md5_from_api(md5):
        return beatmap


async def fetch_by_id(id: int) -> Optional[Beatmap]:
    if beatmap := await id_from_database(id):
        return beatmap

    if beatmap := await id_from_api(id):
        return beatmap


async def fetch_by_set_id(set_id: int) -> list[Beatmap]:
    if beatmaps := await set_from_database(set_id):
        return beatmaps

    if beatmaps := await set_from_api(set_id):
        return beatmaps

    return []


async def md5_from_database(md5: str) -> Optional[Beatmap]:
    db_result = await glob.db.fetch(
        "SELECT * FROM beatmaps WHERE beatmap_md5 = :md5",
        {"md5": md5},
    )

    if not db_result:
        return None

    return Beatmap.from_mapping(db_result)


async def id_from_database(id: int) -> Optional[Beatmap]:
    db_result = await glob.db.fetch(
        "SELECT * FROM beatmaps WHERE beatmap_id = :id",
        {"id": id},
    )

    if not db_result:
        return None

    return Beatmap.from_mapping(db_result)


async def set_from_database(set_id: int) -> list[Beatmap]:
    db_results = await glob.db.fetchAll(
        "SELECT * FROM beatmaps WHERE beatmapset_id = :id",
        {"id": set_id},
    )

    return [Beatmap.from_mapping(db_result) for db_result in db_results]  # type: ignore


GET_BEATMAP_URL = "https://old.ppy.sh/api/get_beatmaps"


async def save(beatmap: Beatmap) -> None:
    await glob.db.execute(
        (
            "REPLACE INTO beatmaps (beatmap_id, beatmapset_id, beatmap_md5, song_name, ar, od, mode, rating, "
            "max_combo, hit_length, bpm, playcount, passcount, ranked, latest_update, ranked_status_freezed, "
            "file_name) VALUES (:beatmap_id, :beatmapset_id, :beatmap_md5, :song_name, :ar, :od, :mode, "
            ":rating, :max_combo, :hit_length, :bpm, :playcount, :passcount, :ranked, :latest_update, "
            ":ranked_status_freezed, :file_name)"
        ),
        {
            "beatmap_id": beatmap.id,
            "beatmapset_id": beatmap.set_id,
            "beatmap_md5": beatmap.md5,
            "song_name": beatmap.song_name,
            "ar": beatmap.ar,
            "od": beatmap.od,
            "mode": beatmap.mode,
            "rating": beatmap.rating,
            "max_combo": beatmap.max_combo,
            "hit_length": beatmap.hit_length,
            "bpm": beatmap.bpm,
            "playcount": beatmap.plays,
            "passcount": beatmap.passes,
            "ranked": beatmap.status.value,
            "latest_update": beatmap.last_update,
            "ranked_status_freezed": beatmap.frozen,
            "file_name": beatmap.filename,
        },
    )


async def md5_from_api(md5: str, should_save: bool = True) -> Optional[Beatmap]:
    api_key = random.choice(settings.OSU_API_KEYS)

    response = await glob.http_client.get(
        GET_BEATMAP_URL,
        params={"k": api_key, "h": md5},
    )
    if response.status_code == 404:
        return None

    response.raise_for_status()

    response_json = response.json()
    if not response_json:
        return None

    beatmaps = parse_from_osu_api(response_json)

    if should_save:
        for beatmap in beatmaps:
            await save(beatmap)

    for beatmap in beatmaps:
        if beatmap.md5 == md5:
            return beatmap


async def id_from_api(id: int, should_save: bool = True) -> Optional[Beatmap]:
    api_key = random.choice(settings.OSU_API_KEYS)

    response = await glob.http_client.get(
        GET_BEATMAP_URL,
        params={"k": api_key, "b": id},
    )
    if response.status_code == 404:
        return None

    response.raise_for_status()

    response_json = response.json()
    if not response_json:
        return None

    beatmaps = parse_from_osu_api(response_json)

    if should_save:
        for beatmap in beatmaps:
            await save(beatmap)

    for beatmap in beatmaps:
        if beatmap.id == id:
            return beatmap


async def set_from_api(id: int, should_save: bool = True) -> Optional[list[Beatmap]]:
    api_key = random.choice(settings.OSU_API_KEYS)

    response = await glob.http_client.get(
        GET_BEATMAP_URL,
        params={"k": api_key, "s": id},
    )
    if response.status_code == 404:
        return None

    response.raise_for_status()

    response_json = response.json()
    if not response_json:
        return None

    beatmaps = parse_from_osu_api(response_json)

    if should_save:
        for beatmap in beatmaps:
            await save(beatmap)

    return beatmaps


IGNORED_BEATMAP_CHARS = dict.fromkeys(map(ord, r':\/*<>?"|'), None)

FROZEN_STATUSES = (RankedStatus.RANKED, RankedStatus.APPROVED, RankedStatus.LOVED)


def parse_from_osu_api(
    response_json_list: list[dict],
    frozen: bool = False,
) -> list[Beatmap]:
    maps = []

    for response_json in response_json_list:
        md5 = response_json["file_md5"]
        id = int(response_json["beatmap_id"])
        set_id = int(response_json["beatmapset_id"])

        filename = (
            ("{artist} - {title} ({creator}) [{version}].osu")
            .format(**response_json)
            .translate(IGNORED_BEATMAP_CHARS)
        )

        song_name = (
            ("{artist} - {title} [{version}]")
            .format(**response_json)
            .translate(IGNORED_BEATMAP_CHARS)
        )

        hit_length = int(response_json["hit_length"])

        if _max_combo := response_json.get("max_combo"):
            max_combo = int(_max_combo)
        else:
            max_combo = 0

        ranked_status = RankedStatus.from_osu_api(int(response_json["approved"]))
        if ranked_status in FROZEN_STATUSES:
            frozen = True  # beatmaps are always frozen when ranked/approved/loved

        mode = int(response_json["mode"])

        if _bpm := response_json.get("bpm"):
            bpm = round(float(_bpm))
        else:
            bpm = 0

        od = float(response_json["diff_overall"])
        ar = float(response_json["diff_approach"])

        maps.append(
            Beatmap(
                md5=md5,
                id=id,
                set_id=set_id,
                song_name=song_name,
                status=ranked_status,
                plays=0,
                passes=0,
                mode=mode,
                od=od,
                ar=ar,
                hit_length=hit_length,
                last_update=int(time.time()),
                max_combo=max_combo,
                bpm=bpm,
                filename=filename,
                frozen=frozen,
                rating=10.0,
            ),
        )

    return maps


async def increment_playcount(beatmap: Beatmap, passcount: bool = True) -> None:
    beatmap.plays += 1
    if passcount:
        beatmap.passes += 1

    await glob.db.execute(
        "UPDATE beatmaps SET passcount = :pass, playcount = :play WHERE beatmap_md5 = :md5",
        {"play": beatmap.plays, "pass": beatmap.passes, "md5": beatmap.md5},
    )
