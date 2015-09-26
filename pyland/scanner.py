import array
import socket
import xml.etree.ElementTree as ET
from .util import wl_fmt, wl_msg
from .types import WLObject, Protocol

debug = False

def new_method(protocol, opcode, elem):
    name = elem.get('name')
    signatures = []
    interface = None
    offset = 0
    doc = ''
    arguments = []
    returntype = None
    for child in elem:
        if child.tag == 'arg':
            t = child.get('type')
            if t == 'new_id':
                if offset != 0:
                    signatures += 'su'
                    arguments.append(('interface', 'type', None))
                    arguments.append(('version', 'uint', None))
                signatures += 'n'
                returntype = child.get('interface') or 'WLObject'
            else:
                if t == 'fd':
                    signatures += 'h'
                else:
                    signatures += t[0]
                arguments.append((child.get('name'), t, child.get('summary')))
            offset += 1
        elif child.tag == 'description':
            doc = child.text
    if len(arguments) > 0 or returntype:
        argstr = ', '.join(('%s: %s' % (n,t)) for n,t,s in arguments)
        retstr = (' -> %s' % returntype) or ''
        doc = "%s(%s)%s\n%s" % (name, argstr, retstr, doc)
    def func(self, *args):
        n_args = len(args)
        new_args = []
        ret = None
        i = 0
        missing = []
        fds = []
        for child in elem:
            if child.tag == 'arg':
                t = child.get('type')
                if t == 'new_id':
                    interface = child.get('interface')
                    if i != 0 and interface == None:
                        ret = args[i](self)
                        new_args.append(args[i].__name__)
                        new_args.append(args[i + 1])
                        new_args.append(ret)
                    elif i == 0 and interface != None:
                        ret = protocol[interface](self)
                        new_args.append(ret)
                        continue
                    else:
                        raise RuntimeError(
                            "Don't know how to handle argument '%s' of function '%s'"
                            % (child.get('name'), name))
                elif t == 'fd':
                    fds.append(args[i])
                else:
                    new_args.append(args[i])
                i += 1
        if len(missing):
            raise TypeError("%s() missing required positional arguments: %s"
                            % (name, ", ".join("'%s'r" % m for m in missing)))
        msg = wl_msg(self.id, opcode, wl_fmt(*new_args))
        sock = self.display.connection
        if len(fds) != 0:
            sock.sendmsg([msg], [(socket.SOL_SOCKET,
                                  socket.SCM_RIGHTS,
                                  array.array('i', fds))])
        else:
            self.display.connection.sendall(msg)
        return ret
    func.__name__ = name
    func.__doc__ = doc
    return ((name, signatures), func)

def new_event(elem):
    signatures = ''
    for child in elem:
        if child.tag == 'arg':
            signatures += child.get('type')[0]
    return (elem.get('name'), signatures)

def new_enum(elem):
    name = elem.get('name').title()
    props = {}
    for child in elem:
        if child.tag == 'entry':
            svalue = child.get('value')
            if svalue.startswith('0x'):
                ivalue = int(svalue, 16)
            else:
                ivalue = int(svalue)
            props[child.get('name').upper()] = ivalue
    return (name, type(name, (), props))

def new_interface(protocol, elem):
    version = elem.get('version')
    methods = []
    events = []
    props = {'version': version}
    for child in elem:
        if child.tag == 'request':
            message, func = new_method(protocol, len(methods), child)
            methods.append(message)
            props[message[0]] = func
        elif child.tag == 'event':
            message = new_event(child)
            events.append(message)
        elif child.tag == 'enum':
            key, enum = new_enum(child)
            props[key] = enum
    props['methods'] = methods
    props['events'] = events
    return type(elem.get('name'), (WLObject,), props)

def scan(path='/usr/share/wayland/wayland.xml'):
    tree = ET.parse(path)
    root = tree.getroot()
    protocol = Protocol(root.get('name'))
    for elem in root:
        if elem.tag == 'interface':
            setattr(protocol, elem.get('name'), new_interface(protocol, elem))
    return protocol
