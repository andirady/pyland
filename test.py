import array
import mmap
import pyland
import tempfile
import os
import socket
import fcntl
from threading import Thread

XDG_RUNTIME_DIR = os.environ['XDG_RUNTIME_DIR']

wlproto = pyland.scan()
d = wlproto.wl_display()
d.inputs = []
d.outputs = []
d.connection = pyland.connect_to_display()

def error(self, data, *args):
    print("error! " + str(args))

def delete_id(self, data, id):
    print("delete_id! id=%d" % id)
    obj = pyland.objects.pop(id)
    del obj

d.add_listener((error, delete_id), d)

reg = d.get_registry()

def seat_capabilities_ev(seat, inp, capabilities):
    print('capabilities@%d! capabilities=%d' % (seat.id, capabilities))

def seat_name_ev(seat, inp, name):
    print('name@%d! name=%s' % (seat.id, name))

def dd_data_offer_event(dd, inp, id):
    print('data offer! %d' % id)

def dd_enter_event(dd, inp, serial, surface, x, y, id):
    print('enter@%d! serial=%d surface=%s x=%s y=%s, id=%s'
          % (dd.id, serial, surface, x,y, id))

def dd_leave_event(dd, inp):
    print('leave@%d!' % dd.id)

def dd_motion_event(dd, inp, time, x, y):
    print('motion@%d! time=%d x=%s y=%s' % (dd.id, time, x,y))

def dd_drop_event(dd, inp):
    print('drop@%d!' % dd.id)

def dd_selection_event(dd, inp, id):
    print('selection@%d! id=%s' % (dd.id, id)) 

def add_input(d, id):
    inp = type('Input', (), {
        'touch_focus':None, 
        'pointer_focus':None, 
        'keyboard_focus':None
    })()
    inp.display = d,
    inp.seat = reg.bind(id, wlproto.wl_seat, min(d.seat_version, 4))
    inp.seat.add_listener((seat_capabilities_ev,
                           seat_name_ev), inp)
    d.inputs.append(inp)
    if d.data_device_manager:
        inp.data_device = d.data_device_manager.get_data_device(inp.seat)
        inp.data_device.add_listener((dd_data_offer_event, 
                                      dd_enter_event,
                                      dd_leave_event,
                                      dd_motion_event,
                                      dd_drop_event,
                                      dd_selection_event), inp)

def display_handle_geometry(op, o, *args):
    print('handle_geometry! %s' % str(args))

def display_handle_mode(op, o, *args):
    print('handle_mode! %s' % str(args))

def display_handle_done(op, o, *args):
    print('handle_done! %s' % str(args))

def display_handle_scale(op, o, *args):
    print('handle_scale! %s' % str(args))

def add_output(d, id):
    output = reg.bind(id, wlproto.wl_output, 2)
    output.scale = 1
    output.server_output_id = id
    output.add_listener((display_handle_geometry,
                         display_handle_mode,
                         display_handle_done,
                         display_handle_scale), output)

def shm_listener(shm, data, fmt):
    if fmt == wlproto.wl_shm.Format.RGB565:
        data.has_rgb565 = True

def global_handler(reg, d, name, interface, version):
    print('global! (name=%d, interface="%s", version=%d)' % (name, interface, version))
    if interface == 'wl_compositor':
        d.compositor = reg.bind(name, wlproto.wl_compositor, 3)
    elif interface == 'wl_output':
        add_output(d, name)
    elif interface == 'wl_seat':
        d.seat_version = version
        add_input(d, name)
    elif interface == 'wl_shm':
        d.shm = reg.bind(name, wlproto.wl_shm, 1)
        d.shm.add_listener((shm_listener,), d)
    elif interface == 'wl_data_device_manager':
        d.data_device_manager_version = min(version, 2)
        d.data_device_manager = reg.bind(name, wlproto.wl_data_device_manager,
                                         d.data_device_manager_version)
    elif interface == 'wl_shell':
        d.shell = reg.bind(name, wlproto.wl_shell, 1)
    else:
        print("\t^-- UNHANDLED")

def global_remove(self, data, name):
    print('global! name=%d' % name)

reg.add_listener((global_handler, global_remove), d)

def done(self, data, callback_data):
    print('done! %s' % callback_data)
    self.isdone = True

class MyThread(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.more = True
        self.pause = False

    def run(self):
        while self.more:
            while self.pause:
                continue
            self.more = pyland.invoke(pyland.read_msg(d.connection))

mythread=MyThread()
mythread.start()

window = type('Window', (), {'width': 500, 'height': 300})()

def buffer_release(buff, d):
    buff.destroy()

def create_anon_file(sz):
    fd, fn = tempfile.mkstemp(dir=XDG_RUNTIME_DIR) # create temporary file
    flags = fcntl.fcntl(fd, fcntl.F_GETFD)
    fcntl.fcntl(fd, fcntl.F_SETFD, flags | fcntl.FD_CLOEXEC)
    os.unlink(fn) # make it anonymous
    os.ftruncate(fd, sz) # limit the size
    return fd

def create_buffer(width, height):
    stride = width * 4
    sz = stride * height
    fd = create_anon_file(sz)
    shm_data = mmap.mmap(fd, sz, mmap.MAP_SHARED,
                         mmap.PROT_READ | mmap.PROT_WRITE, offset=0)
    pool = d.shm.create_pool(fd, sz)
    buff = pool.create_buffer(0, width, height, stride,
                              wlproto.wl_shm.Format.ARGB8888)
    buff.add_listener((buffer_release,), d)
    pool.destroy()
    return (shm_data, buff)

def handle_ping(ss, d, serial):
    ss.pong(serial)
    print('Pinged and ponged')

def enter_event(ss, d, output):
    print('enter! output=%s' % output)
    seat = d.inputs[0].seat
    pointer = seat.get_pointer()
    pointer.mouse_down = False
    pointer.add_listener(pointer_listener, seat)
    keyboard = seat.get_keyboard()
    keyboard.add_listener(keyboard_listener, seat)

def leave_event(ss, d, output):
    print('leave! output=%s' % output)

def resize(width, height):
    window.width, window.height = width, height
    d.shm_data, d.buff = create_buffer(width, height)
    paint(d.shm_data, 0, width, height, d.color)
    d.surface.attach(d.buff, 0,0)
    d.surface.damage(0,0, width, height)
    d.surface.commit()

def paint(shmap, offset, w, h, color):
    shmap.seek(offset)
    for i in range(w * h):
        shmap.write(color)

def draw_box(shmap, x,y, w,h, color):
    W, H = window.width, window.height
    for i in range(h):
        shmap.seek(4*(x + W*(y + i)))
        shmap.write(color*w)
    updaterect(x,y,w,h)

def updaterect(x,y,w,h):
    d.surface.attach(d.buff,0,0)
    d.surface.damage(x,y,w,h)
    d.surface.commit()

def clear():
    paint(d.shm_data, 0, window.width,window.height, d.color)
    d.surface.attach(d.buff, 0,0)
    d.surface.damage(0,0, window.width,window.height)
    d.surface.commit()

def pointer_enter(ptr, d, *args):
    print('pointer_enter! %s' % str(args))

def pointer_leave(ptr, d, *args):
    print('pointer_leave! %s' % str(args))
    ptr.mouse_down = False

def pointer_motion(ptr, seat, *args):
    print('pointer_motion! %s' % str(args))
    
def pointer_button(ptr, seat, serial, time, button, state):
    global mythread
    print('pointer_button! %s' % str((serial, time, button, state)))
    if button == 272 and state == 1:
        pass

def pointer_axis(ptr, d, *args):
    print('pointer_axis! %s' % str(args))

pointer_listener = (pointer_enter, pointer_leave, pointer_motion,
                    pointer_button, pointer_axis)

def dummylistener(eventname):
    def f(obj, data, *args):
        print('%s@%d! %s' % (eventname, obj.id, str(args)))
    return f

keyboard_listener = (dummylistener('kb_keymap'),
                     dummylistener('kb_enter'),
                     dummylistener('kb_leave'),
                     dummylistener('kb_key'),
                     dummylistener('kb_modifiers'))

def ss_configure(ss, d, edges, width, height):
    resize(width, height)
                  
shell_surface_listener = (handle_ping, 
                          ss_configure,
                          dummylistener('ss_popup_done'))


WHITE  = b'\xff\xff\xff\xff'
BLACK  = b'\x00\x00\x00\xff'
RED    = b'\x00\x00\xff\xff'
GREEN  = b'\x00\xff\x00\xff'
BLUE   = b'\xff\x00\x00\xff'
YELLOW = b'\xff\xff\x00\xff'

def init():
    callback = d.sync()
    callback.isdone = False
    callback.add_listener((done,), callback)
    while not callback.isdone:
        continue
    d.surface = d.compositor.create_surface()
    d.surface.add_listener((enter_event, leave_event), d)
    d.shell_surface = d.shell.get_shell_surface(d.surface)
    d.shell_surface.set_toplevel()
    d.shell_surface.add_listener(shell_surface_listener, d)
    d.shm_data, d.buff = create_buffer(window.width, window.height)
    d.color = WHITE
    paint(d.shm_data, 0, window.width, window.height, d.color)
    d.surface.attach(d.buff, 0, 0)
    d.surface.commit()
    
init()

