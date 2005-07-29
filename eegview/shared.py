import os, sys

from pbrainlib.gtkutils import FileManager
import distutils.sysconfig

class RC:
    # provides attributes attrs
    if os.environ.has_key('HOME'):
        path = os.environ['HOME']
    elif sys.platform=='win32':
        path = os.path.join(distutils.sysconfig.PREFIX, 'share', 'pbrain')
    elif sys.platform=='linux':
        path  = '/tmp/'
    else:
        path = None

    def join_ints(seq):
        return ' '.join(['%d'%val for val in seq])

    def split_ints(ints):
        return [int(val) for val in ints.split()]
    
    convertToFile = {'figsize':join_ints,}
    convertFromFile = {'figsize':split_ints,'sqlport':int}
    attrs = (
        'lastdir',
        'figsize',
        'httpuser',
        'httppasswd',
        'httpurl',
        'httpcachedir',
        'sqluser',
        'sqlpasswd',
        'sqlhost',
        'sqlport',
        'sqldatabase',
        'horizcursor',
        'vertcursor'
        )

    def __init__(self):
        self.load_defaults()
        if self.path is not None:
            self.filename = os.path.join(self.path, '.eegviewrc')
            try: self.loadrc()
            except IOError: pass
            

        for attr in self.attrs:
            if not hasattr(self, attr):
                raise AttributeError('Unknown property: %s'%attr)
            
    def load_defaults(self):
        if sys.platform=='win32':
            self.lastdir = 'C:\\'
        else: 
            self.lastdir = os.getcwd()

        self.figsize = 8, 6

        self.httpuser = 'username'
        self.httppasswd = 'passwd'
        self.httpurl = 'localhost'
        self.httpcachedir = 'tempdir'        

        self.sqluser = 'username'
        self.sqlpasswd = 'passwd'
        self.sqlhost = 'localhost'
        self.sqldatabase = 'seizure'        
        self.sqlport = 3306

        self.horizcursor = True
        self.vertcursor = True

    def loadrc(self):
        
        for line in file(self.filename):
            key, val = line.split(':', 1)
            key = key.strip()
            val = val.strip()
            func = self.convertFromFile.get(key, str)
            self.__dict__[key] = func(val)

    def save(self):
        try:
            fh = file(self.filename, 'w')
            
            for attr in self.attrs:
                func = self.convertToFile.get(attr, str)
                val = func(self.__dict__[attr])
                fh.write('%s : %s\n' % (attr, val))
            print 'Updated RC file', self.filename
        except IOError:
            print >>sys.stderr, 'Failed to write to', self.filename
        
    def __del__(self):
        self.save()
        
eegviewrc = RC()        

fmanager = FileManager()
fmanager.set_lastdir(eegviewrc.lastdir)
                
