import MySQLdb
import mx.DateTime
import types
import CodeRegistry
from Code import Code
import servers
import re


class TableEntry:
    def __init__(self, result=None):
        """A table entry to a mysql database.  If result is a Tuple, construct entry from a MySQL result Tuple"""
        pass
    def  get_mapping(self):
        """Pure virtual, must be overridden by children"""
        raise RuntimeError, "get_mapping must be overridden by child class"



class DiagnosisEntry(TableEntry):
    def __init__(self, result=None):
        TableEntry.__init__(self, result)
        if isinstance(result, types.TupleType):
            self.pid = result[0]
            self.seizure_classification = result[1]
            self.info = result[2]
    def get_mapping(self):
            return  {
                'pid' : self.pid,
                'seizure_classification' : self.seizure_classification,
                'seizure_classification_desc' : CodeRegistry.get_description(
                'Seizure classification', self.seizure_classification ),
                'info' : self.info
                } 

class SurgeryEntry(TableEntry):
    def __init__(self, result=None):
        TableEntry.__init__(self, result)
        if isinstance(result, types.TupleType):
            self.pid = result[0]
            self.date = result[1]
            self.num_foc_resected = result[2]
            self.or_report = result[3]
    def get_mapping(self):
            return  {
                'pid' : self.pid,
                'date' : self.date,
                'num_foc_resected' : self.num_foc_resected,
                'or_report' : self.or_report
                } 

class FocusEntry(TableEntry):
    def __init__(self, result=None):
        TableEntry.__init__(self, result)
        if isinstance(result, types.TupleType):
            self.pid = result[0]
            self.surgery_date = result[1]
            self.focus_num = result[2]
            self.location = result[3]
            self.electrodes = result[4]
    def get_mapping(self):
            return  {
                'pid' : self.pid,
                'surgery_date' : self.surgery_date,
                'focus_num' : self.focus_num,
                'location' : self.location,
                'electrodes' : self.electrodes
                } 

class PatientEntry(TableEntry):
    def __init__(self, result=None):
        TableEntry.__init__(self, result)
        if isinstance(result, types.TupleType):
            self.pid = result[0]
            self.first = result[1]
            self.middle = result[2]
            self.last = result[3]
            self.dob = result[4]
            self.race = result[5]
            self.sex = result[6]
            self.employment = result[7]
            self.iq = result[8]
            self.consent = result[9]
            self.dbase_status = result[10]
            self.summary = result[11]
    def get_mapping(self):
        if self.dob==None:
            dob = '0000-00-0000 00:00:00.00'
            age = 0
        else:
            dob = '%s' % self.dob
            now = mx.DateTime.now()
            age = mx.DateTime.Age(now,self.dob).years
                
        return  {
            'pid' : self.pid,
            'first' : self.first,
            'middle' : self.middle,
            'last' : self.last,
            'dob' : dob,
            'age' : age,
            'race' : self.race,
            'race_desc' : CodeRegistry.get_description(
            'race', self.race ),
            'sex' : self.sex,
            'sex_desc' : CodeRegistry.get_description(
            'sex', self.sex ),
            'employment' : self.employment,
            'employment_desc' :  CodeRegistry.get_description(
            'Employment', self.employment ),
            'consent' : self.consent,
            'consent_desc' :  CodeRegistry.get_description(
            'consent', self.consent ),
            'iq' : self.iq,
            'dbase_status' : self.dbase_status,
            'summary' : self.summary
            
            } 

class DatafileEntry(TableEntry):
    def __init__(self, result=None):
        TableEntry.__init__(self, result)
        if isinstance(result, types.TupleType):
            #first 4 entries are pid, date, filename, description
            #print result
            self.pid = result[0]
            self.date = result[1]
            self.filename = result[2]
            self.description = result[3]
    def get_mapping(self):
        relpath = 'Patients/%d/%s/' % \
                  (self.pid, self.get_folder())
        if (self.date):
            ymd = self.date.strftime('%Y-%m-%d')
            hm = self.date.strftime('%H:%M')
            date = '%s' % self.date
            if len(date)>16:
                date=date[0:16]
        else:
            ymd = '0000-00-00'
            hm = '00:00'
            date = '0000-00-00 00:00'
        
        return  {
            'pid' : self.pid,
            'date' : date,
            'filename' : self.filename,
            'description' : self.description,
            'relpath' : relpath,
            'date_ymd' : ymd,
            'date_hm' : hm
            }
    def get_folder(self):
        """Get the folder in which the data is store on the URL filesystem.  Pure virtual method"""
        raise RuntimeError, 'get_folder must be overloaded by child class'

class MultifileEntry(TableEntry):
    def __init__(self, result=None):
        TableEntry.__init__(self, result)
        if isinstance(result, types.TupleType):
            #first 4 entries are pid, date, filename, description
            #print result
            self.pid = result[0]
            self.date = result[1]
            self.filename = result[2]
            self.file_type = result[3]
            self.spacing = result[4]
            self.tilt = result[5]
            self.width = result[6]

    def get_mapping(self):
        relpath = 'Patients/%d/%s/' % \
                  (self.pid, self.get_folder())
        return  {
            'pid' : self.pid,
            'date' : self.date,
            'filename' : self.filename,
            'file_type' : self.file_type,
            'file_type_desc' : CodeRegistry.get_description(
            'Multifile type', self.file_type ),
            'spacing' : self.spacing,
            'tilt' : self.tilt,
            'width' : self.width,
            'folder' : self.get_folder(),
            'relpath' : relpath
            }
    def get_folder(self):
        """Get the folder in which the data is store on the URL filesystem.  Pure virtual method"""
        return get_multifile_folder( self.file_type)


# mysql table mapping files to assoc files
class AssocMapEntry(TableEntry):
    def __init__(self, result=None):
        TableEntry.__init__(self, result)
        if isinstance(result, types.TupleType):
            self.pid = result[0]
            self.filename = result[1]
            self.assocfile = result[2]

    def get_mapping(self):
        relpath = 'Patients/%d/assoc/' % self.pid
        return  {
            'pid' : self.pid,
            'filename' : self.filename,
            'assocfile' : self.assocfile,
            'relpath' : relpath
            }

class EEGEntry(DatafileEntry):
    def __init__(self, result=None):
        if isinstance(result, types.TupleType):
            DatafileEntry.__init__(self, result[0:4])
            
            self.channels = result[4]
            self.freq = result[5]
            self.classification = result[6]
            self.file_type = result[7]
            self.behavior_state = result[8]
    def get_mapping(self):
        s = DatafileEntry.get_mapping(self)
        s['channels'] = self.channels
        s['freq'] = self.freq
        s['classification'] = self.classification
        s['classification_desc'] = CodeRegistry.get_description(
            'EEG classification', self.classification)
        s['file_type'] = self.file_type
        s['file_type_desc'] = CodeRegistry.get_description(
            'EEG file type', self.file_type )
        s['behavior_state'] = self.behavior_state
        s['behavior_state_desc'] = CodeRegistry.get_description(
            'Behavioral State', self.behavior_state )

        return s

    def get_folder(self):
        return 'eegs'

class ImageEntry(DatafileEntry):
    def __init__(self, result=None):
        if isinstance(result, types.TupleType):
            DatafileEntry.__init__(self, result[0:4])
            self.classification = result[4]
    def get_mapping(self):
        s = DatafileEntry.get_mapping(self)
        s['classification'] = self.classification
        s['classification_desc'] = CodeRegistry.get_description(
            'Image classification', self.classification )
        return s
    def get_folder(self):
        return 'images'

class AssocFileEntry(DatafileEntry):
    def __init__(self, result=None):
        if isinstance(result, types.TupleType):
            DatafileEntry.__init__(self, result[0:4])
            self.type = result[4]
    def get_mapping(self):
        s = DatafileEntry.get_mapping(self)
        s['type'] = self.type
        s['type_desc'] = CodeRegistry.get_description(
            'Associated File', self.type )
        return s
    def get_folder(self):
        return 'assoc'


class SeizureDBaseTable:
    def __init__(self, cursor):
        self.cursor = cursor

    def get_select_sql( self, sql):
        """Execute the sql SELECT syntax and return the results in a mapping suitable for use with DTML"""
        self.cursor.execute(sql)
        results = self.cursor.fetchall()
        mapping = []
        for result in results:
            mapping.append( self.get_entry( result ).get_mapping() )
        return mapping

    def get_entry(self, result=None):
        """Get a TableEntry from a SELECT result tuple.  Pure virtual, must be overrdden by children"""
        raise RuntimeError, "get_entry must be overridden by child class"


class PatientDBase(SeizureDBaseTable):
    def get_entry(self, result):
        return PatientEntry(result)
    def get_pids(self):
        pids = []
        results = self.get_select_sql("SELECT * from patient;" )
        for result in results:
            pids.append( result['pid'] )
        return pids


class DiagnosisDBase(SeizureDBaseTable):
    def get_entry(self, result):
        return DiagnosisEntry(result)

class SurgeryDBase(SeizureDBaseTable):
    def get_entry(self, result):
        return SurgeryEntry(result)

class FocusDBase(SeizureDBaseTable):
    def get_entry(self, result):
        return FocusEntry(result)


class MultifileDBase(SeizureDBaseTable):
    def get_entry(self, result):
        return MultifileEntry(result)

class EEGDBase(SeizureDBaseTable):
    def get_entry(self, result):
        return EEGEntry(result)

class ImageDBase(SeizureDBaseTable):
    def get_entry(self, result):
        return ImageEntry(result)

class AssocFileDBase(SeizureDBaseTable):
    def get_entry(self, result):
        return AssocFileEntry(result)

class AssocMapDBase(SeizureDBaseTable):
    def get_entry(self, result):
        return AssocMapEntry(result)


def uniq(l):
    uniqs = {}
    #return a uniq list
    for val in l:
        uniqs[val] = 1
    x = uniqs.keys()
    x.sort()
    return x
    

def get_attributes( x ):
    return x.__dict__

    
def get_multifile_folder( file_type ):
        """Get the folder in which the data is store on the URL filesystem.  Pure virtual method"""
        if file_type==0 or file_type==1:
            return 'mris'
        elif file_type==2 or file_type==3:
            return 'cats'
        elif file_type==4:
            return 'pets'
        else:
            return 'multis'

def get_multitypes( sql ):
    multis = _multiFileDBase.get_select_sql(
        "SELECT * FROM multifile WHERE %s;" % sql)
    file_types = []
    for file in multis:
        file_types.append( file['file_type'] )

    return uniq(file_types)
