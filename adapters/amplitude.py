from __future__ import annotations


def format_mode(mode: int) -> str:
    mode_mapping: dict[int, str] = {
        0: "osu!std",
        1: "osu!taiko",
        2: "osu!catch",
        3: "osu!mania",
        4: "osu!std relax",
        5: "osu!taiko relax",
        6: "osu!catch relax",
        # no mania relax
        8: "osu!std autopilot",
        # no taiko autopilot
        # no catch autopilot
        # no mania autopilot
    }

    return mode_mapping[mode]
