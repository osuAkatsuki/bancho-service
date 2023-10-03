from __future__ import annotations

import struct
from typing import Any
from typing import Mapping
from typing import TypedDict

from constants import dataTypes

# NOTE: removed cython 2022-06-26


def uleb128Encode(num: int) -> bytearray:
    """
    Encode an int to uleb128

    :param num: int to encode
    :return: bytearray with encoded number
    """
    if num == 0:
        return bytearray(b"\x00")

    arr = bytearray()
    length = 0

    while num > 0:
        arr.append(num & 0b01111111)
        num >>= 7
        if num != 0:
            arr[length] |= 0b10000000
        length += 1

    return arr


def uleb128Decode(num: bytes) -> list[int]:
    """
    Decode a uleb128 to int

    :param num: encoded uleb128 int
    :return: (total, length)
    """
    shift = 0
    arr = [0, 0]  # total, length

    while True:
        b = num[arr[1]]
        arr[0] |= (b & 0b01111111) << shift
        arr[1] += 1

        if (b & 0b10000000) == 0:
            break

        shift += 7

    return arr


_default_packs = {
    dataTypes.UINT16: struct.Struct("<H"),
    dataTypes.SINT16: struct.Struct("<h"),
    dataTypes.UINT32: struct.Struct("<L"),
    dataTypes.SINT32: struct.Struct("<l"),
    dataTypes.UINT64: struct.Struct("<Q"),
    dataTypes.SINT64: struct.Struct("<q"),
    dataTypes.STRING: struct.Struct("<s"),
    dataTypes.FFLOAT: struct.Struct("<f"),
    dataTypes.BYTE: struct.Struct("<B"),
}


def packData(__data: Any, dataType: int) -> bytes:
    """
    Packs a single section of a packet.

    :param __data: data to pack
    :param dataType: data type
    :return: packed bytes
    """
    if dataType == dataTypes.BBYTES:  # current mood
        return __data

    data = bytearray()  # data to return

    # Get right pack Type
    if dataType == dataTypes.INT_LIST:
        # 2 bytes length, 4 bytes each element
        data += len(__data).to_bytes(2, "little")
        for i in __data:
            data += i.to_bytes(4, "little", signed=True)
    elif dataType == dataTypes.STRING:
        if __data:
            # real string; \x0b[uleb][string]
            encoded = __data.encode()
            data += b"\x0b"
            data += uleb128Encode(len(encoded))
            data += encoded
        else:
            # empty string; \x00
            data += b"\x00"
    else:
        # default types, use struct pack.
        data += _default_packs[dataType].pack(__data)

    return bytes(data)


PKT_HDR_START = struct.Struct("<Hx")
PKT_HDR_END = struct.Struct("<I")


def buildPacket(__packet: int, __packetData: tuple = ()) -> bytes:
    """
    Builds a packet

    :param __packet: packet ID
    :param __packetData: packet structure [[data, dataType], [data, dataType], ...]
    :return: packet bytes
    """
    packetData = bytearray(PKT_HDR_START.pack(__packet))

    for i in __packetData:
        packetData += packData(i[0], i[1])

    packetData[3:3] = PKT_HDR_END.pack(len(packetData) - 3)
    return bytes(packetData)


class PacketData(TypedDict):
    data: Mapping[str, Any]
    end: int


def readPacketData(
    stream: bytes,
    structure: tuple = (),
    hasFirstBytes: bool = True,
) -> PacketData:
    """
    Read packet data from `stream` according to `structure`
    :param stream: packet bytes
    :param structure: packet structure: [[name, dataType], [name, dataType], ...]
    :param hasFirstBytes: 	if True, `stream` has packetID and length bytes.
                            if False, `stream` has only packet data. Default: True
    :return: {data, end}
    """
    # Read packet ID (first 2 bytes)
    data = {}

    # Skip packet ID and packet length if needed
    start = end = 7 if hasFirstBytes else 0

    # Read packet
    for i in structure:
        start = end
        if i[1] == dataTypes.INT_LIST:
            # 2 bytes length, 4 bytes each element
            length = int.from_bytes(stream[start : start + 2], "little")

            data[i[0]] = []
            for j in range(length):
                offs = start + 2 + (4 * j)
                data[i[0]].append(int.from_bytes(stream[offs : offs + 4], "little"))

            # Update end
            end = start + 2 + (4 * length)
        elif i[1] == dataTypes.STRING:
            # Check empty string
            if stream[start] != 0:
                # real string; \x0b[uleb][string]
                length = uleb128Decode(stream[start + 1 :])
                end = start + length[0] + length[1] + 1

                data[i[0]] = stream[start + 1 + length[1] : end].decode()
            else:
                # empty string; \x00
                data[i[0]] = ""
                end = start + 1
        else:
            fmt = _default_packs[i[1]]
            end = start + fmt.size
            data[i[0]] = fmt.unpack(stream[start:end])[0]

    return {"data": data, "end": end}
