from struct import pack, unpack
from .types import WLObject, objects

LITTLE_UINT = "<I"
WORD_SIZE = 4 # in bytes
HEADER_SIZE = 2 * WORD_SIZE


def wl_fmt(*vals) -> bytes:
    """
    Pack arguments into byte arrays.
    
    See https://wayland.freedesktop.org/docs/html/ch04.html#sect-Protocol-Wire-Format

    :param vals: values to be packed.
    :return:
    """
    ret = bytearray()
    for val in vals:
        val_type = type(val)
        if val_type is int:
            ret += pack(LITTLE_UINT, val)
        elif val_type is str:
            val += '\0'
            s = pack(LITTLE_UINT, len(val)) + val.encode("utf8")
            mod = len(s) % WORD_SIZE
            if mod != 0:
                ret += s + bytearray(WORD_SIZE - mod)
            else:
                ret += s
        elif isinstance(val, WLObject):
            ret += pack(LITTLE_UINT, val.id)
        else:
            raise Exception('Unsupported type %s' % val_type)
    return ret


def wl_msg(obj_id, opcode, msg) -> bytes:
    """
    Create Wayland message.
    
    See https://wayland.freedesktop.org/docs/html/ch04.html#sect-Protocol-Wire-Format
    """
    msg_len = len(msg)
    if msg_len % WORD_SIZE != 0:
        raise Exception('Invalid message length')
    header = pack(LITTLE_UINT, obj_id)
    header += pack(LITTLE_UINT, (msg_len + HEADER_SIZE) << 16 | (opcode & 0x0000ffff))
    return header + msg


def read_msg(con):
    """
    Read and unpack message.
    """
    raw1 = con.recv(6)
    if len(raw1) == 0:
        return None
    raw2 = con.recv(2)
    msg_len = unpack('<H', raw2)[0]
    return unpack('<IH', raw1) + (con.recv(msg_len - 8),)


def invoke(msg: tuple) -> False:
    """
    """
    if msg == None:
        return False
    obj_id, opcode, raw_args = msg
    obj = objects[obj_id]
    name, arg_ts = obj.events[opcode]
    args = []
    i = 0
    for t in arg_ts:
        if t in 'iu': # int or unsinged int
            fmt = '<i' if t == 'i' else '<I'
            args.append(unpack(fmt, raw_args[i:i+WORD_SIZE])[0])
            i += WORD_SIZE
        elif t == 's': # string
            n = unpack(LITTLE_UINT, raw_args[i:i+WORD_SIZE])[0]
            i += WORD_SIZE
            args.append(raw_args[i:i+n-1].decode('utf8'))
            i += n
            mod = n % WORD_SIZE
            if mod % WORD_SIZE != 0:
                i += WORD_SIZE - mod
        elif t == 'o': # object
            o_id = unpack(LITTLE_UINT, raw_args[i:i+WORD_SIZE])[0]
            i += WORD_SIZE
            args.append(objects[o_id])
    if not hasattr(obj, 'listener'):
        print("waiting listener for %s@%d.%s" % (type(obj).__name__,
                                                 obj_id, name))
        while not hasattr(obj, 'listener'):
            continue
    if len(obj.listener) == opcode:
        return False
    obj.listener[opcode](obj, obj.user_data, *args)
    return True


def invoke_message(con) -> bool:
    """
    Read Wayland message from connection and execute.

    :param con: the connection socket.
    :return:
    """
    return invoke(read_msg(con))
