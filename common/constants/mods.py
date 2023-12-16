from __future__ import annotations


class Mods:
    NOMOD = 0
    NOFAIL = 1 << 0
    EASY = 1 << 1
    TOUCHSCREEN = 1 << 2  # FKA NoVideo
    HIDDEN = 1 << 3
    HARDROCK = 1 << 4
    SUDDENDEATH = 1 << 5
    DOUBLETIME = 1 << 6
    RELAX = 1 << 7
    HALFTIME = 1 << 8
    NIGHTCORE = 1 << 9
    FLASHLIGHT = 1 << 10
    AUTOPLAY = 1 << 11
    SPUNOUT = 1 << 12
    AUTOPILOT = 1 << 13
    PERFECT = 1 << 14
    KEY4 = 1 << 15
    KEY5 = 1 << 16
    KEY6 = 1 << 17
    KEY7 = 1 << 18
    KEY8 = 1 << 19
    KEYMOD = KEY4 | KEY5 | KEY6 | KEY7 | KEY8
    FADEIN = 1 << 20
    RANDOM = 1 << 21
    CINEMA = 1 << 22  # FKA LastMod
    TARGET_PRACTICE = 1 << 23
    KEY9 = 1 << 24
    KEY_COOP = 1 << 25
    KEY1 = 1 << 26
    KEY3 = 1 << 27
    KEY2 = 1 << 28
    SCOREV2 = 1 << 29
    MIRROR = 1 << 30

    SPEED_CHANGING = DOUBLETIME | NIGHTCORE | HALFTIME


NP_MAPPING_TO_INTS = {
    "-NoFail": Mods.NOFAIL,
    "-Easy": Mods.EASY,
    "+Hidden": Mods.HIDDEN,
    "+HardRock": Mods.HARDROCK,
    "+SuddenDeath": Mods.SUDDENDEATH,
    "+DoubleTime": Mods.DOUBLETIME,
    "~Relax~": Mods.RELAX,
    "-HalfTime": Mods.HALFTIME,
    "+Nightcore": Mods.NIGHTCORE | Mods.DOUBLETIME,
    "+Flashlight": Mods.FLASHLIGHT,
    "|Autoplay|": Mods.AUTOPLAY,
    "-SpunOut": Mods.SPUNOUT,
    "~Autopilot~": Mods.AUTOPILOT,
    "+Perfect": Mods.PERFECT,
    "|Cinema|": Mods.CINEMA,
    "~Target~": Mods.TARGET_PRACTICE,
    # perhaps could modify regex
    # to only allow these once,
    # and only at the end of str?
    "|1K|": Mods.KEY1,
    "|2K|": Mods.KEY2,
    "|3K|": Mods.KEY3,
    "|4K|": Mods.KEY4,
    "|5K|": Mods.KEY5,
    "|6K|": Mods.KEY6,
    "|7K|": Mods.KEY7,
    "|8K|": Mods.KEY8,
    "|9K|": Mods.KEY9,
    # XXX: kinda mood that there's no way
    # to tell K1-K4 co-op from /np, but
    # scores won't submit or anything, so
    # it's not ultimately a problem.
    "|10K|": Mods.KEY5 | Mods.KEY_COOP,
    "|12K|": Mods.KEY6 | Mods.KEY_COOP,
    "|14K|": Mods.KEY7 | Mods.KEY_COOP,
    "|16K|": Mods.KEY8 | Mods.KEY_COOP,
    "|18K|": Mods.KEY9 | Mods.KEY_COOP,
}
