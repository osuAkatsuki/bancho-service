from __future__ import annotations

from collections import defaultdict
from json import JSONDecodeError
from json import loads

import requests
from requests import RequestException

import settings
from common.log import logger
from objects import glob


def cheesegullRequest(
    handler,
    requestType="GET",
    params=None,
    mustHave=None,
    wants=None,
):
    """
    Send a request to Cheesegull

    :param handler: name of the api handler (eg: `search` for `http://chesegu.ll/api/search`)
    :param requestType: `GET` or `POST`. Default: `GET`
    :param key: authorization key. Optional.
    :param params: dictionary containing get/post form parameters. Optional.
    :param mustHave: list or string containing the key(s) that must be contained in the json response. Optional.
    :param wants: can be a single string, or a list of strings.
    :return:    returns None if the result was invalid or if the request failed.
                if `wants` is a string, returns the key from the response.
                if `wants` is a list of strings, return a dictionary containing the wanted keys.
    """
    # Default values
    if mustHave is None:
        mustHave = []
    if wants is None:
        wants = []
    if params is None:
        params = {}

    # Params and function

    if requestType.lower() == "post":
        getParams = None
        postData = params
    else:
        getParams = params
        postData = None

    mirror_url: str = settings.MIRROR_URL  # type: ignore

    request_url = f"{mirror_url}/{handler}"
    logger.info(
        "Making request to 3rd party mirror",
        extra={
            "url": request_url,
            "params": getParams,
            "data": postData,
        },
    )
    # make a network call to the mirror
    response = requests.request(
        requestType,
        request_url,
        params=getParams,
        data=postData,
        # headers={"Authorization": key},
    )

    if response.status_code in range(500, 600):  # 5xx
        logger.error(
            "3rd party mirror returned mirror returned 5xx service code",
            extra={
                "url": request_url,
                "params": getParams,
                "data": postData,
                "status_code": response.status_code,
            },
        )

        if handler == "search":
            return "-1\nBeatmap mirror service currently unavailable."

        return None

    # support mino's "raw" parameter
    if "catboy.best" in mirror_url and getParams is not None and "raw" in getParams:
        return response.text

    if not response:
        return None

    try:
        data = loads(response.text)
    except (
        JSONDecodeError,
        KeyError,
    ) as exc:
        logger.error(
            "An exception occurred while decoding the response from the mirror",
            exc_info=exc,
            extra={
                "url": request_url,
                "params": getParams,
                "data": postData,
                "status_code": response.status_code,
            },
        )
        return response.text
    except (ValueError, RequestException) as exc:
        logger.error(
            "An exception occurred while making a request to the mirror",
            exc_info=exc,
            extra={
                "url": request_url,
                "params": getParams,
                "data": postData,
                "status_code": response.status_code,
            },
        )
        return None

    if not data:
        return None

    # Params and status check
    if response.status_code != 200:
        return None
    if mustHave:
        if isinstance(mustHave, str):
            mustHave = [mustHave]
        for i in mustHave:
            if i not in data:
                return None

    # Return what we want
    if isinstance(wants, str):
        if wants in data:
            return data[wants]
        return None
    elif len(wants) == 0:
        return data
    else:
        res = {}
        for i in data:
            if i in wants:
                res[i] = data[i]
        return res


def getListing(rankedStatus, page, gameMode, query):
    glob.dog.increment(
        f"{glob.DATADOG_PREFIX}.cheesegull_requests",
        tags=["cheesegull:listing"],
    )
    params = {"query": query, "offset": page, "amount": 100}
    if rankedStatus:
        params["status"] = rankedStatus
    if gameMode:
        params["mode"] = gameMode

    params["raw"] = 1
    return cheesegullRequest("search", params=params)


def getBeatmapSet(id):
    glob.dog.increment(
        f"{glob.DATADOG_PREFIX}.cheesegull_requests",
        tags=["cheesegull:set"],
    )
    return cheesegullRequest(f"s/{id}")


def getBeatmap(id):
    glob.dog.increment(
        f"{glob.DATADOG_PREFIX}.cheesegull_requests",
        tags=["cheesegull:beatmap"],
    )
    setID = cheesegullRequest(f"b/{id}", wants="ParentSetID")
    return getBeatmapSet(setID) if setID and setID > 0 else None


def toDirect(data):
    if "ChildrenBeatmaps" not in data or not data["ChildrenBeatmaps"]:
        raise ValueError("`data` doesn't contain a valid cheesegull response")
    s = [
        (
            "{SetID}.osz|{Artist}|{Title}|{Creator}|{RankedStatus}|0.00|{LastUpdate}|"
            "{SetID}|{SetID}|{HasVideo}|0|1337|{FileSizeNoVideo}|"
        ).format(**data, FileSizeNoVideo="7331" if data["HasVideo"] else ""),
    ]

    if len(data["ChildrenBeatmaps"]) > 0:
        for i in data["ChildrenBeatmaps"]:
            s.append(
                "{DiffNameSanitized} ({DifficultyRating:.2f}★~{BPM}♫"
                "~AR{AR}~OD{OD}~CS{CS}~HP{HP}~{ReadableLength})@{Mode},".format(
                    **i,
                    DiffNameSanitized=i["DiffName"].replace("@", ""),
                    ReadableLength=f"{i['TotalLength'] // 60}m{i['TotalLength'] % 60}s",
                ),
            )

    return f"{''.join(s).strip(',')}|"


def toDirectNp(data):
    return (
        "{SetID}.osz|{Artist}|{Title}|{Creator}|{RankedStatus}|10.00|"
        "{LastUpdate}|{SetID}|{SetID}|{HasVideo}|0|1337|{FileSizeNoVideo}"
    ).format(**data, FileSizeNoVideo="7331" if data["HasVideo"] else "")


def directToApiStatus(directStatus):
    mapping = defaultdict(
        lambda: 0,
        {
            0: 1,
            2: 0,
            3: 3,
            5: 0,
            7: 1,
            8: 4,
        },
    )
    return mapping[directStatus]
