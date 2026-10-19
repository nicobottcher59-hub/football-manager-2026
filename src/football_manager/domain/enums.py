from __future__ import annotations

from enum import StrEnum


class Foot(StrEnum):
    LEFT = "left"
    RIGHT = "right"
    BOTH = "both"


class Position(StrEnum):
    GK = "GK"
    RB = "RB"
    RCB = "RCB"
    CB = "CB"
    LCB = "LCB"
    LB = "LB"
    RWB = "RWB"
    LWB = "LWB"
    DM = "DM"
    RCM = "RCM"
    CM = "CM"
    LCM = "LCM"
    AM = "AM"
    RW = "RW"
    LW = "LW"
    SS = "SS"
    ST = "ST"
