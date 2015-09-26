from struct import pack, unpack
from .types import WLObject, objects

prev_msg = []

def wl_fmt(*vals):
    ret = bytearray()
    for val in vals:
        if type(val) is int:
            ret += pack('<I', val)
        elif type(val) is str:
            val += '\0'
            s = pack('<I', len(val)) + val.encode('utf8')
            mod = len(s) % 4
            if mod != 0:
                ret += s + bytearray(4 - mod)
            else:
                ret += s
        elif isinstance(val, WLObject):
            ret += pack('<I', val.id)
        else:
            raise Exception('Unsupported type %s' % type(val))
    return ret

def wl_msg(obj_id, opcode, msg):
    if len(msg) % 4 != 0:
        raise Exception('Invalid message length')
    ret = pack('<I', obj_id)
    ret += pack('<I', (len(msg) + 8) << 16 | (opcode & 0x0000ffff))
    ret += msg
    return ret

def read_msg(con):
    raw1 = con.recv(6)
    if len(raw1) == 0:
        return None
    raw2 = con.recv(2)
    msg_len = unpack('<H', raw2)[0]
    return unpack('<IH', raw1) + (con.recv(msg_len - 8),)

def invoke(msg):
    global prev_msg
    if len(prev_msg) > 0:
        prev_msg.pop(0)
    prev_msg.append(msg)
    if msg == None:
        return False
    obj_id, opcode, raw_args = msg
    obj = objects[obj_id]
    name, arg_ts = obj.events[opcode]
    args = []
    i = 0
    for t in arg_ts:
        if t in 'iu':
            fmt = '<%c' % ('i' if t == 'i' else 'I')
            args.append(unpack(fmt, raw_args[i:i+4])[0])
            i += 4
        elif t == 's':
            n = unpack('<I', raw_args[i:i+4])[0]
            i += 4
            args.append(raw_args[i:i+n-1].decode('utf8'))
            i += n
            mod = n % 4
            if mod % 4 != 0:
                i += 4 - mod
        elif t == 'o':
            o_id = unpack('<I', raw_args[i:i+4])[0]
            i += 4
            args.append(objects[o_id])
    if not hasattr(obj, 'listener'):
        print("waiting listener for %s@%d.%s" % (type(obj).__name__,
                                                 obj_id, name))
        while not hasattr(obj, 'listener'):
            continue
    obj.listener[opcode](obj, obj.user_data, *args)
    return True
