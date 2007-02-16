# Module level globals to store http and mysql server information
import os, sys, urllib, base64, httplib, glob
import tempfile
from matplotlib.cbook import mkdirs, listFiles
from MySQLTable import MySQLTable
import MySQLdb, MySQLdb.cursors




class SQL:
    """
    CLASS: SQL
    DESCR: 
    """
    def init(self, dbname, host, user, passwd, port):
        db = MySQLdb.connect(db=dbname,
                             host=host,
                             user=user,
                             passwd=passwd,
                             port=port,
                             cursorclass=MySQLdb.cursors.DictCursor)


        self.db = db
        self.cursor = db.cursor()
        self.patients = MySQLTable(table_name='patient', cursor=self.cursor)
        self.eeg = MySQLTable(table_name='eeg', cursor=self.cursor)        
        self.assocfile = MySQLTable(table_name='assocfile', cursor=self.cursor)        


class DataManager:
    """
    CLASS: DataManager
    DESCR: Handles retrieval from web and cacheing to local machine in the cachedir
    """
    def init(self, url, user, passwd, cachedir):
        "if cachedir is 'tempdir', use tempfile.gettempdir"
        if cachedir == 'tempdir':
            cachedir = tempfile.gettempdir()
        if url.startswith('http://'):
            url = url[7:]
        self._urlBase = 'http://%s:%s@%s/Patients/' %\
                   (user, passwd, url)
        self._local = 0

        if not os.path.exists(cachedir):
            os.makedirs(cachedir)
            # make sure we can write and remove from this dir
            testname = os.path.join(cachedir, '_tmp.dat')
            file(testname, 'w')
            os.remove(testname)


        if not url.startswith('//'): tmp = '//'+url
        else: tmp = url
        base, rel = urllib.splithost(tmp)

        self.host = base
        self.relpath = rel
        self.cachedir = cachedir
        self.url = url
        self.user = user
        self.passwd = passwd
        
    def islocal(self):
        return self._local

    def get_rel_path(self, pid, subdir, fname):
        return os.path.join( '%d' % pid, subdir, fname) 

    def get_local_basepath(self):
        return self.cachedir
        
    def get_local_filename(self, pid, subdir, fname ):
        localname = os.path.join( self.get_local_basepath(),
                	         self.get_rel_path(pid, subdir, fname) )
        if not os.path.exists(localname):
            self._cache_data_to_local(pid, subdir, fname, localname)
        return localname        

    def get_data_url(self, pid, subdir, fname):
        return self._urlBase + '%d/%s/%s' % (pid, subdir, fname)

    def get_url_base(self):
        return self._urlBase


    def _cache_data_to_local(self, pid, subdir, fname, localname):
        if self.islocal(): return

        url = self.get_data_url(pid, subdir, fname)

        mkdirs(os.path.split(localname)[0], 0755)
        name, msg = urllib.urlretrieve(url, localname)
        

    def get_base64_authorization(self):
        return base64.encodestring('%s:%s' % (self.user, self.passwd))


sql = SQL()
datamanager = DataManager()

