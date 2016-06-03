objects = {0: None} # list of object instances.

class Protocol:
    def __init__(self, name):
        self.name = name

    def __getitem__(self, key):
        if key != None and hasattr(self, key):
            return self.__getattribute__(key)
        return None

    def __setitem__(self, key, val):
        self.__setattr__(key, val)

class WLObject:
    def __init__(self, factory=None):
        self.id = max(objects.keys()) + 1
        objects[self.id] = self
        self.display = self if factory == None else factory.display

    def add_listener(self, listener, data=None):
        if hasattr(self, 'listener'):
            raise Exception('%s already has listener' % self)
        self.listener = listener
        self.user_data = data
