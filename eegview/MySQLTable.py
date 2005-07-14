# Author: John D. Hunter <jdhunter@ace.bsd.uchicago.edu> 6/13/2002
# Copyright: John D. Hunter 2002
# License: BSD

import string
import copy

class TableEntry: 
    def __init__(self, field_names, m, id): 
        """We pass 'fields_name' even though they are the keys to the
        hash so we can maintain the field order from the table.  m is
        a dictionary of field->value, id is a unique identifier for
        each table entry"""

        # the self.__dict__ assignment must be the first line or else
        # you'll overwrite the other attributes you set

        self.__dict__ = m.copy()
        self.__orig = m.copy()
        self._id = id
        self._field_names = field_names

    def get_obj(self):
        """
        return a class object with the attributes deep copied; lose
        all functions
        """
        
        m = {}
        for (key, val) in self.__dict__.items():
            if not callable(val) and key.find('_')!=0:
                m[key] = copy.deepcopy(val)
        class C:
            def __init__(self): self.__dict__ = m
        return C()
    
    def get_id(self):
        return self._id
        
    def __repr__(self):
        """Return a string with field name : value for all fields"""
        return self.repr_fields( self.get_field_names() )

    def __getitem__(self, key):
        """Table entry can act like a class or a dict"""
        return self.__dict__[key]

    def get_orig_map(self):
        return self.__orig
    
    def revert(self):
        """
        Revert the object to the state it was at after initialization
        or after last update, if update has been called.
        """

        self.__dict__ = self.__orig

    def update(self):
        """
        Commit the attribute changes to orig.  __orig is used to keep
        track of the objects values in the dbase table before the
        attribute changes so we can update tables which have no
        primary keys by identifying every column/value pair in the
        where clause
        """
        self.__orig = self.__dict__
        
    def get_field_names(self):
        """
        Get a list of field names as strings, in the order they appear
        in the MySQl table
        """        
        return self._field_names

    def get_items(self):
        "return a list of key, value pairs for the fields in the table"
        l = []
        for key in self.get_field_names():
            l.append((key, self.get_value(key)))
        return l
                   
    def get_value(self, field):
        """Get the value for the field 'Field'"""
        return self.__dict__[field]

    def repr_fields( self, fields):
        """Return a string with field name : field value for the field
        names isted in 'fields'"""

        s = ''
        for f in fields:
            s += '%s: %s\n' % (f, self.get_value(f))
        return s
        
class MySQLTable:

    def __init__(self, table_name, cursor):
        """Initialize the mysql table with table name in 'table_name'.
        Cursor is a DisctCursor instance returned from
        MySQLdb.cursor(), MySQLdb must ber initialized with the
        cursorclass=MySQLdb.cursors.DictCursor argument"""

        self._tblname = table_name
        self._cursor = cursor
        self._fields = []     # A list of dictionaries describing the table
        self._primaries = []  # The primary keys
        self._nextid = 0      # Assign unique ids to the entries
        self._pmaps = []      # A list of primary key/value pairs
                              #   indexed by _nextid
        self._field_names = []
        self._parse_table()
                       
    def insert(self, m):
        """m is a map from field names to values.  Insert the values
        into the table.  For fields which are not keys of m, use the
        mysql default"""

        keys = m.keys()
        values = m.values()
        fmts = map(lambda x: '%s', keys)
            
        s = 'INSERT into %s ( %s ) VALUES ( %s )\n' % \
            (self._tblname, string.join(keys, ','), string.join(fmts, ',') )
        #print s
        self._cursor.execute(s, values)

    def delete(self, where='1>0'):
        """Delete entries matching 'where'; use with caution!"""
        s = 'DELETE FROM %s WHERE %s;' % (self._tblname, where)
        #print s
        self._cursor.execute(s)
        
    def update(self, entry):
        """Update the mysql table with the TableEntry instance 'entry'"""

        values = []
        for name in self._field_names:
            values.append( getattr(entry, name) )

        if len(self._primaries)>0:
            # update the pmap
            oldpmap = self._pmaps[ entry.get_id() ]
            self._pmaps[ entry.get_id() ] = self._get_pmap( entry )
            for key in self._primaries:            
                values.append( oldpmap[key] )
            s = 'UPDATE %s SET %s WHERE %s;' % \
                (self._tblname,
                 string.join( self._field_names, '=%s,') + '=%s',
                 string.join( self._primaries, '=%s AND ') + '=%s')
        else:
            # no primries, identify row by value of all old keys
            origmap = entry.get_orig_map()
            for name in self._field_names:
                values.append( origmap[name] )
            s = 'UPDATE %s SET %s WHERE %s;' % \
                (self._tblname,
                 string.join( self._field_names, '=%s,') + '=%s',
                 string.join( self._field_names, '=%s AND ') + '=%s')
            entry.update() 
        self._cursor.execute(s, values)


    def select(self, where='1>0'):
        """Return a list of TableEntry instances matching the SELECT
        criteria in 'where'"""    
        s = 'SELECT * from %s WHERE %s;' % (self._tblname, where)
        self._cursor.execute( s);
        x = []
        for result in self._cursor.fetchall():
            x.append(TableEntry(self._field_names, result, self._nextid))
            self._nextid += 1        
            self._pmaps.append( self._get_pmap(result) )
        return x

    def selectone(self, where):
        results =  self.select(where)
        if len(results)==0: return None
        else: return results[0]
    
    def get_primary_keys(self):
        return self._primaries

    def get_field_names(self):
        return self._field_names

    def print_entries(self, where='1>0'):
        xs = self.select(where)
        for x in xs:
            print x
    
    def _parse_table(self):
        """Get the table info; types primary keys, etc..."""
        self._cursor.execute('describe %s;' % self._tblname)
        self._fields =  self._cursor.fetchall()
        
        for field in self._fields:
            self._field_names.append(field['Field'])
            if field['Key']=='PRI':
                self._primaries.append( field['Field'] )

    def _get_pmap(self, m):
        """Return a map of primary keys to value for the dict m"""
        pmap = {}
        for key in self._primaries:
            pmap[key] = m[key]
        return pmap
