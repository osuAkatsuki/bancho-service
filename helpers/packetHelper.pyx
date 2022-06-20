import struct

from constants import dataTypes

# pp -m timeit -s 'from helpers.packetHelper import readPacketData,buildPacket;from constants import dataTypes' 'readPacketData(buildPacket(11,((1001,dataTypes.UINT32),(0,dataTypes.BYTE),("",dataTypes.STRING),("sdfudasgfuidasjfuisadf",dataTypes.STRING),(128,dataTypes.SINT32),(0,dataTypes.BYTE),(1234131,dataTypes.SINT32),(2347123842,dataTypes.UINT64),(1.0,dataTypes.FFLOAT),(3223,dataTypes.UINT32),(23452345235,dataTypes.UINT64),(69,dataTypes.UINT32),(31124,dataTypes.UINT16))),(("userID",dataTypes.UINT32),("actionID",dataTypes.BYTE),("actionText",dataTypes.STRING),("actionMd5",dataTypes.STRING),("actionMods",dataTypes.SINT32),("gameMode",dataTypes.BYTE),("beatmapID",dataTypes.SINT32),("rankedScore",dataTypes.UINT64),("accuracy",dataTypes.FFLOAT),("playcount",dataTypes.UINT32),("totalScore",dataTypes.UINT64),("gameRank",dataTypes.UINT32),("pp",dataTypes.UINT16)))'

cpdef bytearray uleb128Encode(int num):
    """
    Encode an int to uleb128

    :param num: int to encode
    :return: bytearray with encoded number
    """
    if num == 0:
        return bytearray(b"\x00")

    cdef bytearray arr = bytearray()
    cdef int length = 0

    while num > 0:
        arr.append(num & 0b01111111)
        num >>= 7
        if num != 0:
            arr[length] |= 0b10000000
        length += 1

    return arr

cpdef list uleb128Decode(bytes num):
    """
    Decode a uleb128 to int

    :param num: encoded uleb128 int
    :return: (total, length)
    """
    cdef int shift = 0
    cdef list arr = [0,0] # total, length
    cdef int b

    while True:
        b = num[arr[1]]
        arr[0] |= (b & 0b01111111) << shift
        arr[1] += 1

        if (b & 0b10000000) == 0:
            break

        shift += 7

    return arr

cdef dict _default_packs
_default_packs = {
    dataTypes.UINT16: struct.Struct('<H'),
    dataTypes.SINT16: struct.Struct('<h'),
    dataTypes.UINT32: struct.Struct('<L'),
    dataTypes.SINT32: struct.Struct('<l'),
    dataTypes.UINT64: struct.Struct('<Q'),
    dataTypes.SINT64: struct.Struct('<q'),
    dataTypes.STRING: struct.Struct('<s'),
    dataTypes.FFLOAT: struct.Struct('<f'),
    dataTypes.BYTE:   struct.Struct('<B')
}

cpdef unpackData(bytes data, int dataType):
    """
    Unpacks a single section of a packet.

    :param data: bytes to unpack
    :param dataType: data type
    :return: unpacked bytes
    """
    return _default_packs[dataType].unpack(data)[0]

cpdef bytes packData(__data, int dataType):
    """
    Packs a single section of a packet.

    :param __data: data to pack
    :param dataType: data type
    :return: packed bytes
    """
    if dataType == dataTypes.BBYTES: # current mood
        return __data

    cdef bytearray data = bytearray() # data to return

    # Get right pack Type
    if dataType == dataTypes.INT_LIST:
        # 2 bytes length, 4 bytes each element
        data += len(__data).to_bytes(2, 'little')
        for i in __data:
            data += i.to_bytes(4, 'little', signed=True)
    elif dataType == dataTypes.STRING:
        if __data:
            # real string; \x0b[uleb][string]
            encoded = __data.encode()
            data += b'\x0b'
            data += uleb128Encode(len(encoded))
            data += encoded
        else:
            # empty string; \x00
            data += b'\x00'
    else:
        # default types, use struct pack.
        data += _default_packs[dataType].pack(__data)

    return bytes(data)

PKT_HDR_START = struct.Struct('<Hx')
PKT_HDR_END = struct.Struct('<I')

cpdef bytes buildPacket(int __packet, tuple __packetData = ()):
    """
    Builds a packet

    :param __packet: packet ID
    :param __packetData: packet structure [[data, dataType], [data, dataType], ...]
    :return: packet bytes
    """
    cpdef bytearray packetData = bytearray(PKT_HDR_START.pack(__packet))

    cdef tuple i
    for i in __packetData:
        packetData += packData(i[0], i[1])

    packetData[3:3] = PKT_HDR_END.pack(len(packetData) - 3)
    return bytes(packetData)

cpdef readPacketData(bytes stream, tuple structure = (), bint hasFirstBytes = True):
    """
    Read packet data from `stream` according to `structure`
    :param stream: packet bytes
    :param structure: packet structure: [[name, dataType], [name, dataType], ...]
    :param hasFirstBytes: 	if True, `stream` has packetID and length bytes.
                            if False, `stream` has only packet data. Default: True
    :return: {data, end}
    """
    # Read packet ID (first 2 bytes)
    cdef dict data = {}

    # Skip packet ID and packet length if needed
    cdef int start, end
    start = end = 7 if hasFirstBytes else 0

    # Read packet
    cdef int j, offs # lol imagine if we had a class.,.,,,.,,.
    cdef tuple i

    for i in structure:
        start = end
        if i[1] == dataTypes.INT_LIST:
            # 2 bytes length, 4 bytes each element
            length = int.from_bytes(stream[start:start+2], 'little')

            data[i[0]] = []
            for j in range(length):
                offs = start + 2 + (4 * j)
                data[i[0]].append(int.from_bytes(stream[offs:offs+4], 'little'))

            # Update end
            end = start + 2 + (4 * length)
        elif i[1] == dataTypes.STRING:
            # Check empty string
            if stream[start] != 0:
                # real string; \x0b[uleb][string]
                length = uleb128Decode(stream[start + 1:])
                end = start + length[0] + length[1] + 1

                data[i[0]] = stream[start + 1 + length[1]:end].decode()
            else:
                # empty string; \x00
                data[i[0]] = ""
                end = start + 1
        else:
            fmt = _default_packs[i[1]]
            end = start + fmt.size
            data[i[0]] = fmt.unpack(stream[start:end])[0]

    return {"data": data, "end": end}
