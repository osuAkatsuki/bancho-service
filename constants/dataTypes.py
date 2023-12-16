"""Bancho packets data types"""
from __future__ import annotations


class DataTypes:
    BYTE = 0
    UINT16 = 1
    SINT16 = 2
    UINT32 = 3
    SINT32 = 4
    UINT64 = 5
    SINT64 = 6
    STRING = 7
    FFLOAT = 8  # because float is a keyword
    BBYTES = 9
    INT_LIST = 10  # TODO: Maybe there are some packets that still use uInt16 + uInt32 thing somewhere.
