import socket
from .scanner import *
from .util import *

debug = False

def connect_to_display(path='/run/user/1000/wayland-0'):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(path)
    return sock
