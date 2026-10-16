"""Physical NIC byte counters through IP Helper; no subprocess per sample."""
import ctypes as c
import os

U32, U64 = c.c_uint32, c.c_uint64


class Row(c.Structure):
    _fields_ = [('luid', U64), ('index', U32), ('guid', c.c_byte * 16),
                ('alias', c.c_uint16 * 257), ('description', c.c_uint16 * 257),
                ('address_length', U32), ('address', c.c_byte * 32),
                ('permanent_address', c.c_byte * 32)] + [
        (name, U32) for name in ('mtu', 'type', 'tunnel', 'media', 'physical_media', 'access', 'direction')
    ] + [('flags', c.c_ubyte)] + [
        (name, U32) for name in ('oper', 'admin', 'media_state')
    ] + [('network_guid', c.c_byte * 16), ('connection_type', U32)] + [
        (name, U64) for name in ('tx_link', 'rx_link', 'in_octets', 'in_ucast', 'in_nucast',
        'in_discards', 'in_errors', 'in_unknown', 'in_ucast_octets', 'in_multicast', 'in_broadcast',
        'out_octets', 'out_ucast', 'out_nucast', 'out_discards', 'out_errors',
        'out_ucast_octets', 'out_multicast', 'out_broadcast', 'out_queue')]


class Table(c.Structure):
    _fields_ = [('count', U32), ('rows', Row * 1)]


def read_interfaces():
    if os.name != 'nt':
        raise OSError('Windows only')
    api = c.WinDLL('iphlpapi')
    api.GetIfTable2.argtypes = [c.POINTER(c.c_void_p)]
    api.GetIfTable2.restype = U32
    api.FreeMibTable.argtypes = [c.c_void_p]
    api.FreeMibTable.restype = None
    ptr = c.c_void_p()
    if api.GetIfTable2(c.byref(ptr)):
        raise OSError('Interface counters unavailable')
    try:
        count = c.cast(ptr, c.POINTER(U32)).contents.value
        if count > 4096:
            raise OSError('Invalid interface count')
        rows = (Row * count).from_address(ptr.value + Table.rows.offset)
        # Hardware, connected and operational; exclude filter/endpoint interfaces,
        # loopback and virtual tunnels to avoid counting the same packet twice.
        return {str(r.luid): (r.out_octets, r.in_octets) for r in rows
                if r.flags & 1 and not r.flags & (2 | 128) and r.oper == 1 and r.type in (6, 71)}
    finally:
        api.FreeMibTable(ptr)


class InterfaceRates:
    def __init__(self):
        self.previous = None
        self.at = None
        self.upload = self.download = 0

    def reset(self):
        self.previous = self.at = None

    def ingest(self, rows, now):
        up = down = 0
        elapsed = now - self.at if self.at is not None else 0
        baseline = self.previous is None or elapsed <= 0 or elapsed > 10
        if not baseline:
            for key, value in rows.items():
                old = self.previous.get(key)
                if old and all(value[i] >= old[i] for i in (0, 1)):
                    up += value[0] - old[0]
                    down += value[1] - old[1]
        self.previous, self.at = rows, now
        self.upload += up
        self.download += down
        return {'status': 'available' if rows and not baseline else 'baseline' if rows else 'unavailable',
                'up_speed': up / elapsed if elapsed and not baseline else None,
                'down_speed': down / elapsed if elapsed and not baseline else None,
                'upload': self.upload, 'download': self.download, 'interfaces': len(rows)}
