# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
# 
# Copyright (c) 2014 Chris Luke <chrisy@flirble.org>
# 
"""PTP TLV Protocol"""

import struct, dpkt, exceptions, IPy, json
import bson_wrapper, bson
import sys

# Parameters
PTP_VERSION         = 1
PTP_MTU             = 1400
PTP_BLOB_SIZE       = 1024


# Protocol TLV types
# General
PTP_TYPE_PROTOVER   = 0
PTP_TYPE_SERVERVER  = 1
PTP_TYPE_CLIENTVER  = 2
PTP_TYPE_SEQUENCE   = 3
PTP_TYPE_UUID       = 4

PTP_TYPE_MYTS       = 8
PTP_TYPE_YOURTS     = 9

# Client-server
PTP_TYPE_PTPADDR    = 32
PTP_TYPE_INTADDR    = 33
PTP_TYPE_UPNP       = 34
PTP_TYPE_META       = 35
PTP_TYPE_SHUTDOWN   = 45

# Server-client
PTP_TYPE_CLIENTLIST_EXT = 64
PTP_TYPE_CLIENTLEN      = 65
PTP_TYPE_YOURADDR       = 66
PTP_TYPE_CLIENTLIST_INT = 67

# Client-client
PTP_TYPE_CC         = 96

PTP_NAMES = {
        -1: 'None',
        PTP_TYPE_PROTOVER: 'PTP_TYPE_PROTOVER',
        PTP_TYPE_SERVERVER: 'PTP_TYPE_SERVERVER',
        PTP_TYPE_CLIENTVER: 'PTP_TYPE_CLIENTVER',
        PTP_TYPE_SEQUENCE: 'PTP_TYPE_SEQUENCE',
        PTP_TYPE_UUID: 'PTP_TYPE_UUID',
        PTP_TYPE_MYTS: 'PTP_TYPE_MYTS',
        PTP_TYPE_YOURTS: 'PTP_TYPE_YOURTS',
        PTP_TYPE_PTPADDR: 'PTP_TYPE_PTPADDR',
        PTP_TYPE_INTADDR: 'PTP_TYPE_INTADDR',
        PTP_TYPE_UPNP: 'PTP_TYPE_UPNP',
        PTP_TYPE_META: 'PTP_TYPE_META',
        PTP_TYPE_SHUTDOWN: 'PTP_TYPE_SHUTDOWN',
        PTP_TYPE_CLIENTLIST_EXT: 'PTP_TYPE_CLIENTLIST_EXT',
        PTP_TYPE_CLIENTLEN: 'PTP_TYPE_CLIENTLEN',
        PTP_TYPE_YOURADDR: 'PTP_TYPE_YOURADDR',
        PTP_TYPE_CLIENTLIST_INT: 'PTP_TYPE_CLIENTLIST_INT',
        PTP_TYPE_CC: 'PTP_TYPE_CC',
}


class Base(dpkt.Packet):
    __hdr__ = (
    )

    ptp_type = None

    def __repr__(self):
        t = self.ptp_type if self.ptp_type else -1
        l = [ "ptp_type=%d(%s)" % (t, PTP_NAMES[t]) ]
        if self.data:
            l.append('data=%s' % repr(self.data))
        return "%s(%s)" % (self.__class__.__name__, ', '.join(l))

class UInt(Base):
    size = 4

    def _stof(self):
        if self.size == 1: return 'B'
        if self.size == 2: return 'H'
        if self.size == 4: return 'I'
        if self.size == 8: return 'Q'
        raise exceptions.RuntimeError('Unknown unsigned integer size %d', self.size)

    def unpack(self, buf):
        self.size = len(buf)
        super(UInt, self).unpack(buf)
        self.data = struct.unpack('!%s' % self._stof(), self.data)[0]

    def __len__(self):
        return self.size

    def __str__(self):
        return self.pack_hdr() + struct.pack('!%s' % self._stof(), int(self.data))


class Int(Base):
    size = 4

    def _stof(self):
        if self.size == 1: return 'b'
        if self.size == 2: return 'h'
        if self.size == 4: return 'i'
        if self.size == 8: return 'q'
        raise exceptions.RuntimeError('Unknown integer size %d', self.size)

    def unpack(self, buf):
        self.size = len(buf)
        super(UInt, self).unpack(buf)
        self.data = struct.unpack('!%s' % self._stof(), self.data)[0]

    def __len__(self):
        return self.size

    def __str__(self):
        return self.pack_hdr() + struct.pack('!%s' % self._stof(), int(self.data))


class String(Base):
    pass


def pack_sin(sin):
    """Takes a sin tuple (addr, port) and packs it into a
    binary form. Resulting size depends on whether addr
    is IPv4 or IPv6."""
    (addr, port) = sin
    addr = IPy.IPint(addr)
    if addr.version() == 4:
        return struct.pack("!IH", addr.int(), port)
    else:
        a = addr.int()
        return struct.pack("!QQH", a >> 64, a % 2**64, port)
        #return struct.pack("!QQH", a >> 64, a & (2**64 - 1), port)

def unpack_sin(data):
    if len(data) == 6: # IPv4
        (a, port) = struct.unpack("!IH", data)
        addr = IPy.IPint(a)
    elif len(data) == 18: #IPv6
        (a, b, port) = struct.unpack("!QQH", data)
        addr = IPy.IPint(a << 64 + b)
    return (str(addr), port)


class Address(Base):
    def unpack(self, buf):
        dpkt.Packet.unpack(self, buf)
        self.data = unpack_sin(self.data)

    def __len__(self):
        if ':' in self.data[0]:
            return self.__hdr_len__ + 18
        return self.__hdr_len__ + 6

    def __str__(self):
        return self.pack_hdr() + pack_sin(self.data)


class JSON(Base):
    def unpack(self, buf):
        super(JSON, self).unpack(buf)
        self.data = json.loads(self.data)

    def __len__(self):
        return len(str(self))

    def __str__(self):
        return self.pack_hdr() + json.dumps(self.data)


class BSON(Base):
    def unpack(self, buf):
        super(BSON, self).unpack(buf)
        self.data = bson.loads(self.data)

    def __len__(self):
        return len(str(self))

    def __str__(self):
        return self.pack_hdr() + bson.dumps(self.data)


PTP_MAP = {
        PTP_TYPE_PROTOVER: UInt,
        PTP_TYPE_SERVERVER: UInt,
        PTP_TYPE_CLIENTVER: UInt,
        PTP_TYPE_SEQUENCE: UInt,
        PTP_TYPE_UUID: String,

        PTP_TYPE_MYTS: UInt,
        PTP_TYPE_YOURTS: UInt,

        PTP_TYPE_PTPADDR: Address,
        PTP_TYPE_INTADDR: Address,
        PTP_TYPE_UPNP: UInt,
        PTP_TYPE_META: JSON,
        PTP_TYPE_SHUTDOWN: UInt,

        PTP_TYPE_CLIENTLIST_EXT: Address,
        PTP_TYPE_CLIENTLEN: UInt,
        PTP_TYPE_YOURADDR: Address,
        PTP_TYPE_CLIENTLIST_INT: Address,

        PTP_TYPE_CC: String,
}


class TLV(dpkt.Packet):
    __hdr__ = (
        ('type', 'B', 0),
        ('len', 'B', 4)
    )

    def __init__(self, *args, **kwargs):
        super(TLV, self).__init__(*args, **kwargs)
        if hasattr(self.data, 'ptp_type'):
            self.data.ptp_type = self.type

    def unpack(self, buf):
        dpkt.Packet.unpack(self, buf)
        self.data = self.data[:self.len - 2]
        cls = Base
        if self.type in PTP_MAP:
            cls = PTP_MAP[self.type]
        else:
            raise exceptions.RuntimeError("Unknown TLV type %d" % self.type)

        self.data = cls(self.data, ptp_type=self.type)

    def __len__(self):
        return self.__hdr_len__ + len(self.data)
    
    def __str__(self):
        self.len = len(self)
        return self.pack_hdr() + str(self.data)


class PTP(dpkt.Packet):
    __hdr__ = (
        ('version', 'B', PTP_VERSION),
    )
    data = []
    buf_csum = None

    def unpack(self, buf):
        # Extract and remove the checksum from the end
        self.csum = struct.unpack('!H', buf[-2:])[0]
        buf = buf[:-2]

        # Check the checksum - someone else can complain if it's wrong
        self.buf_csum = dpkt.in_cksum(buf)

        # Unpack the header
        dpkt.Packet.unpack(self, buf)

        # Now process the TLV's
        buf = self.data
        l = []
        while buf:
            tlv = TLV(buf)
            l.append(tlv)
            buf = buf[len(tlv):]
        self.data = l

    def __len__(self):
        return self.__hdr_len__ + sum(map(len, self.data)) + 2

    def __str__(self):
        data = ''.join(map(str, self.data))
        csum = dpkt.in_cksum(self.pack_hdr() + data)
        return self.pack_hdr() + data + struct.pack('!H', csum)

