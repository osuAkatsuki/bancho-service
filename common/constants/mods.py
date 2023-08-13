from __future__ import annotations

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
    "-NoFail": NOFAIL,
    "-Easy": EASY,
    "+Hidden": HIDDEN,
    "+HardRock": HARDROCK,
    "+SuddenDeath": SUDDENDEATH,
    "+DoubleTime": DOUBLETIME,
    "~Relax~": RELAX,
    "-HalfTime": HALFTIME,
    "+Nightcore": NIGHTCORE,
    "+Flashlight": FLASHLIGHT,
    "|Autoplay|": AUTOPLAY,
    "-SpunOut": SPUNOUT,
    "~Autopilot~": AUTOPILOT,
    "+Perfect": PERFECT,
    "|Cinema|": CINEMA,
    "~Target~": TARGET_PRACTICE,
    # perhaps could modify regex
    # to only allow these once,
    # and only at the end of str?
    "|1K|": KEY1,
    "|2K|": KEY2,
    "|3K|": KEY3,
    "|4K|": KEY4,
    "|5K|": KEY5,
    "|6K|": KEY6,
    "|7K|": KEY7,
    "|8K|": KEY8,
    "|9K|": KEY9,
    # XXX: kinda mood that there's no way
    # to tell K1-K4 co-op from /np, but
    # scores won't submit or anything, so
    # it's not ultimately a problem.
    "|10K|": KEY5 | KEY_COOP,
    "|12K|": KEY6 | KEY_COOP,
    "|14K|": KEY7 | KEY_COOP,
    "|16K|": KEY8 | KEY_COOP,
    "|18K|": KEY9 | KEY_COOP,
}
