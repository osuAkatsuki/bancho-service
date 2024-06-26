from __future__ import annotations


def get_client_name(name: str) -> str:
    if name.startswith("#spect_"):
        return "#spectator"
    elif name.startswith("#mp_"):
        return "#multiplayer"
    else:
        return name
