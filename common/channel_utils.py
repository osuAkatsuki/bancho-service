from __future__ import annotations


def is_special_channel(name: str) -> bool:
    return name.startswith("#spect_") or name.startswith("#multi_")


def get_client_name(name: str) -> str:
    if name.startswith("#spect_"):
        return "#spectator"
    elif name.startswith("#multi_"):
        return "#multiplayer"
    else:
        return name
