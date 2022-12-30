
from constants import slotStatuses
from constants import matchTeams
from typing import Optional

class Slot:
    def __init__(self) -> None:
        self.status = slotStatuses.FREE
        self.team = matchTeams.NO_TEAM
        self.userID = -1
        self.user: Optional[str] = None  # string of osutoken
        self.mods = 0
        self.loaded = False
        self.skip = False
        self.complete = False
        self.score = 0
        self.failed = False
        self.passed = True
