from sets import Set

class Observer:
    """
    CLASS: Observer
    DESCR: 
    """
    SET_TIME_LIM, SELECT_CHANNEL, SAVE_FRAME, COMPUTE_COHERENCE,\
                  GMTOGGLED, LOCK_TRODE_TOGGLED= range(6)
    observers = Set()

    def __init__(self):
        Observer.observers.add(self)

    def broadcast(self, event,  *args):
        for observer in Observer.observers:            
            if observer == self: continue
            observer.recieve(event, *args)

    def recieve(self, event,  *args): pass

    def __del__(self):
        print 'removing', self.__class__
        Observer.observers.remove(self)        

if __name__ == '__main__':

    class A(Observer):
        def __init__(self, name):
            Observer.__init__(self)
            self.name = name

        def recieve(self, event, *args):
            print 'A', self.name, event, args


    class B(Observer):
        def __init__(self, name):
            Observer.__init__(self)
            self.name = name

        def recieve(self, event, *args):
            print 'B', self.name, event, args
        

    a1 = A('John')
    a2 = A('Bill')
    b1 = B('Fred')
    b2 = B('Tom')

    a1.broadcast(Observer.SET_TIME_LIM, (1,2))
    
