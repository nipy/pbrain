# 7.13.05 jwaxma2@uic.edu
#   Added .ann annotation file.
from __future__ import division

import os, sys, re, glob, urllib, httplib
from cStringIO import StringIO
from sets import Set
from matplotlib.cbook import mkdirs, listFiles

from Numeric import array, Int16, Float, Float16, \
     arange, fromstring, take, sqrt, sum, zeros, resize,\
     transpose
from MLab import median
from utils import all_pairs_ij, all_pairs_eoi
import file_formats
import csv
import gtk


import servers
e1020 = Set([
    'cz', 'c3', 'c4',
    't3', 't4', 't5', 't6',
    'o1', 'o2',
    'pz', 'p3', 'p4',
    'fz', 'f3', 'f4', 'f7', 'f8',
    'fp1', 'fp2',
    'a1', 'a2',
    ])

 
class Electrode:
    def __init__(self, name, num, xyz=None):
        self.name = name
        self.num = num
        if xyz is None: self.xyz = array([0.0, 0.0, 0.0])
        else: self.xyz = xyz

    def set_xyz(self, xyz):
        try: xyz.shape
        except AttributeError: xyz = array(xyz, Float)
        self.xyz = xyz

    def get_xyz(self):
        return self.xyz

    def get_name(self):
        return self.name

    def get_num(self):
        return self.num

    def get_label(self):
        return '%s%d' % (self.get_name(), self.get_num())

class Grid(dict):
    def __init__(self, name, dim, rgb=None, spacing=1.0):
        self.name = name
        self.dim = dim    # (dim1, dim2) as integers
        self.rgb = rgb    # (red, green, blue) as floats
        self.spacing = spacing  # a single float
        
    def set_electrode(self, num, electrode):
        self[num] = electrode

    def get_electrode(self, num):
        return self[num]

    def get_electrodes(self):
        return self.values()

    def has_electrode(self, num):
        self.has_key(num)

    def get_dimensions(self):
        return self.dim

    def get_spacing(self):
        return self.spacing

    def get_rgb(self):
        return self.rgb
    
    def get_name(self):
        return self.name

    def get_number_electrodes(self):
        return len(self.keys())
    
class AssociatedFile:
    def __init__(self, dbaseFields=None, useFile=None):
        if dbaseFields is None:
            import mx.DateTime
            now = mx.DateTime.now()
            dbaseFields = {'description': '',
                           'date': now, 
                           'type': self.filetype,
                           'filename': 'none.' + self.extension}
            self.existsWeb = 0
            self.__dict__.update(dbaseFields)
            if useFile is not None:
                basepath, fname = os.path.split(useFile)
                self.filename = fname
                self.fullpath = useFile
                self.load_data(useFile)
        else:
            self.__dict__.update(dbaseFields)
            self.set_exists_web(pid=dbaseFields['pid'],
                                filename=dbaseFields['filename'])
            self.load_data()

    def set_exists_web(self, pid, filename):
        self.dbaseFilename = filename
        self.filename = filename        
        self.pid = pid
        self.existsWeb = 1
        #todo: verify existence with sql query?

    def is_web_file(self):
        return self.existsWeb

    def to_conf_file(self):
        "Convert self to a config file string"
        raise NotImplementedError, 'Derved class must override'

    def load_data(self, useFile=None):
        if useFile is not None:
            try: fh = file(useFile, 'r')
            except IOError:
                raise ValueError('Failed to open %s for reading' % useFile)
            self._load_data(fh)
        else:
            dm = servers.datamanager
            url = dm.get_data_url(self.pid, 'assoc', self.filename)
            fh = urllib.urlopen(url)
            self._load_data(fh)

    def save_data(self, useFile=None, append=False) :
        if useFile is None and not self.is_web_file() :
            try : self.fullpath
            except :
                useFile = ''
            else :
                useFile = self.fullpath

        if useFile is not None :
            fh = None
            try :
                if append :
                    fh = file(useFile, 'a')
                else :
#                    fh = file(useFile, 'w')
                    print "write", useFile
            except IOError :
                raise ValueError('Failed to open %s for writing/appending' % useFile)
            self._save_data(fh, append)
              
        else :
            # xxx Web save
            print "web save"

    def update_web(self, fname=None):
        "Update the web version of the file and database"
        if not self.is_web_file():
            raise RuntimeError, 'Not a web file'

        updateName = 0
        if fname is None:
            fname = self.filename
            updateName = 1
            
        fields = {'description': self.description,
                  'date': self.date,
                  'pid' : self.pid,
                  'type:int': self.filetype,
                  'old_filename' : self.dbaseFilename,
                  }

        fileInfo = {'formvar' : 'filename',
                    'filename' : fname,
                    'content' : self.to_conf_file()}

        
        dm = servers.datamanager
        auth = dm.get_base64_authorization().replace('\n', '\\n')
        headers = {'Authorization' : 'Basic ' + auth}

        submit_form(host=dm.host,
                    path=sm.relpath + '/editedAssocFile',
                    fields=fields,
                    headers=headers,
                    fileInfo=fileInfo )

        # if we made it to here, we successfully update the internet
        if updateName:
            self.dbaseFileName = fname
            self.filename = fname

    def new_web(self, pid, fname):
        """
        Add the file to the web server and database.  Raises a NameError if
        there is already a file in the assocfile table with primary key
        (pid, dname).
        """

        if self.is_web_file(): raise RuntimeError, 'This is a web file'

        #check for existing file with same name
        table = servers.sql.assocfile
        result = table.selectone(
            where='pid=%s and filename="%s"' % (pid, fname))
        if result is not None:
            raise NameError, 'assocfile alreay has entry\n%s' % result

        fields = {'description': self.description,
                  'date': self.date,
                  'pid' : pid,
                  'type:int': self.filetype,
                  }

        fileInfo = {'formvar' : 'filename',
                    'filename' : fname,
                    'content' : self.to_conf_file()}

        dm = servers.datamanager
        auth = dm.get_base64_authorization().replace('\n', '\\n')
        headers = {'Authorization' : 'Basic ' + auth}

        submit_form(host=dm.host,
                    path=dm.relpath+'/addedAssocFile',
                    fields=fields,
                    headers=headers,
                    fileInfo=fileInfo )

        # if we made it to here, we successfully update the internet        
        self.set_exists_web(pid=pid, filename=fname)

    def update_map(self, eegFilename):
        if not self.is_web_file():
            msg = 'EOI must be a web file to map to %s' % eegFilename
            raise RuntimeError, msg

        # Check to see if the association already exists; if so, just return
        cursor = servers.sql.cursor
        sql = 'SELECT pid FROM assocmap WHERE ' +\
              'filename=%s AND assocfile=%s'
        cursor.execute(sql,
                       (eegFilename, self.filename))
        results = cursor.fetchall()
        if len(results)>0: return  #already mapped
        
        # Do the mapping
        sql = 'INSERT INTO assocmap VALUES (%s, %s, %s, %s)'
        cursor.execute(sql,
                       (self.pid, eegFilename, self.filename, 'eeg'))

class Loc3dJr(AssociatedFile):        
    extension = 'csv'
    filetype = 8
    def __init__(self, dbaseFields=None, useFile=None):
        AssociatedFile.__init__(self, dbaseFields, useFile)

    def _load_data(self, fh):
        self.fh = StringIO(fh.read())

class Info(AssociatedFile):        
    extension = 'info'
    filetype = 12
    def __init__(self, dbaseFields=None, useFile=None):
        AssociatedFile.__init__(self, dbaseFields, useFile)

    def _load_data(self, fh):
        self.fh = StringIO(fh.read())
        
class EOI(list, AssociatedFile):
    extension = 'eoi'
    filetype = 5

    def __init__(self, dbaseFields=None, useFile=None, electrodes=None):
        AssociatedFile.__init__(self, dbaseFields, useFile)
        if electrodes is not None:
            self.set_electrodes(electrodes)
        self._update_seen()

    def clear_electrodes(self):
        self[:] = []

    def set_electrodes(self, trodes):
        # The problem is that trodes is self! and we clear it before setting it
        if trodes is self: return
        self.clear_electrodes()
        self.extend(trodes)

    def _update_seen(self):
        self._seen = {}
        for (grdName, grdNum) in self:
            self._seen[grdName + str(grdNum)]=1

    def contains(self, grdName, grdNum):
        return self._seen(grdName + str(grdNum))
        
    def set_description(self, desc):
        self.description = desc

    def get_description(self):
        return self.description

    def _load_data(self, fh):
        fh.readline()  # slurp the header

        desc = fh.readline()  # slurp the description

        while 1:
            line = fh.readline().strip()
            if len(line)==0: break
            desc+=line

        trodes = []
        for line in fh.readlines():
            line = line.strip()
            if len(line)==0: continue
            vals = line.split()
            if len(vals)!=2: break
            trodes.append(
                (vals[0], int(vals[1])))

        self.set_electrodes(trodes)
        self.set_description(desc)

    def get_data(self, amp, eeg):
        """
        Given and Amp instance and an EEG instance, return the data
        for this EOI
        """
        
        data = eeg.get_data()
        ind = self.to_data_indices(amp)
        return take(data, ind, 1)
            
    def to_data_indices(self, amp):
        """
        Return value is a list of indicies into amp for the channels
        in the eoi

        Raises a KeyError if an eoi channel cannot be found in the amp
        struct and returns an error string indicating the problem EOI
        """

        # First invert the amp struct into a map from [name][num] to index
        ampdict = {}
        for (cnum, ename, enum) in amp:
            ampdict.setdefault(ename,{})[enum] = cnum-1

        indices = []
        for name, num in self:
            try:
                indices.append(ampdict[name][num])
            except KeyError:
                msg = 'Could not find an amplifier channel ' +\
                      'for %s %d\n' % (name, num) +\
                      'Please check the amp file associated with this eeg'
                raise KeyError(msg)

        return indices

    def to_conf_file(self):
        "Convert self to a config file string"
        lines = []
        lines.append('EOI : Version 1.0')
        lines.append(self.get_description())
        lines.append('')
        for tup in self:
            lines.append('%s %d' % tup)
        return '\n'.join(lines)

class Amp(list, AssociatedFile):
    """
    An amplifier config file.  iterable as a list of (ampNum, grdName,
    grdNum) tuples
    """
    
    extension = 'amp'
    filetype = 3

    def __init__(self, dbaseFields=None, useFile=None):
        AssociatedFile.__init__(self, dbaseFields, useFile)
        self.message = None

    def to_eoi(self):
        eoi = EOI()
        eoi.filename = self.filename + '.' + EOI.extension
        electrodes = []
        for (cnum, gname, gnum ) in self:
            electrodes.append( (gname, gnum) )
        eoi.set_electrodes(electrodes)
        return eoi

    def _load_data(self, fh):
        """
        Load the amp data file.  Raise a ValueError on illegal file
        format
        """
        fh.readline()  # slurp the header
        ampChannels = []
        seen = {}
        seengrid = {}
        count = 0
        for line in fh.readlines():
            count += 1
            vals = line.split()
            if len(vals)!=3: break
            cnum, gname, gnum = int(vals[0]), vals[1], int(vals[2])
            if seen.has_key(cnum):
                raise ValueError('Duplicate channel num %d on line %s reading\n\t%s' % (cnum, count, line) )
            if seengrid.has_key((gname,gnum)):
                raise ValueError('Duplicate grid channel %s %d on line %s reading\n\t%s' % (gname, gnum, count, line))
            
            seen[cnum] = 1
            seengrid[(gname, gnum)] = 1
            ampChannels.append( (cnum, gname, gnum))

        # flush the old list and set the new
        self.set_channels(ampChannels)
        
    def clear_channels(self):
        self[:] = []

    def set_channels(self, channels):
        "channels is a list of (channelNum, gridName, gridNum) tuples"
        if channels is self: return
        self.clear_channels()
        self.extend(channels)

    def to_conf_file(self):
        "Convert self to a config file string"
        lines = []
        lines.append('AMP : Version 1.0')
        for tup in self:
            lines.append('%d %s %d' % tup)
        return '\n'.join(lines)

    def get_channel_num_dict(self):
        "return a dict from electrodes to channel num"
        return dict([ ( (name,num), ind ) for ind, name, num in self])

    def get_electrode_to_indices_dict(self):
        "return a dict from electrodes to index into the data array"

        return dict([ ( (name,num), ind-1 ) for ind, name, num in self])

    def get_dataind_dict(self):
        """
        Return a dict mapping data structure index (which is not
        necessarily the same as an index into the amp structure)
        to gname, gnum tuples        
        """

        return dict([ ( ind-1, (name,num) ) for ind, name, num in self])        

    def get_channelnum_dict(self):
        """
        Return a dict mapping channel num gname, gnum tuples
        """

        return dict([ ( ind, (name,num) ) for ind, name, num in self])        

class Grids(AssociatedFile, dict):
    extension = 'grd'
    filetype = 4
    
    def __init__(self, dbaseFields=None, useFile=None):
        AssociatedFile.__init__(self, dbaseFields, useFile)

    def add_grid(self, grid):
        self[grid.get_name()] = grid

    def get_grid(self, name):
        return self[name]

    def get_grids(self):
        return self.values()

    def get_number_electrodes(self):
        num = 0
        for grid in self.get_grids():
            num += g.get_number_electrodes()
        return num

    def get_number_grids(self):
        return len(self.get_grids())

    def set_xyz_for_eoi(self, eoi):
        for e in eoi:
            name, num = g.get_name(), e.get_number()
            try:
                xyz = self[name][num].get_xyz()
            except KeyError, e:
                print "unrecognized key", name, num
                xyz = array([0.0,0.0,0.0])
            e.set_xyz(xyz)

    def get_dist_for_eoi(self, eoi):
        """
        Creates a dict of each pair with key (e1,e2) and the distance
        between them.
        """
        
        eoixyz = {}
        xyz = self.get_xyz_for_eoi(eoi)
        for e1, e2 in all_pairs_eoi(eoi):
            p1 = xyz[e1]
            p2 = xyz[e2]
            eoixyz[ (e1, e2) ] = sqrt(sum((p1-p2)**2))
        return eoixyz

    def get_xyz_for_eoi(self, eoi):
        "Get the xyz coords for an eoi as a dict from name, num to x,y,z"

        XYZ = {}
        for name, num in eoi:
            try:
                xyz = self[name][num].get_xyz()
            except KeyError, e:
                print "unrecognized key", name, num
                xyz = array([0.0,0.0,0.0])
            XYZ[ (name, num)] = array(xyz)
        return XYZ

    def _load_data(self, fh):
        fh.readline(), fh.readline()  # slurp the header

        # clear the current dictionary
        self.clear()

        numTrodesByDim = 0
        while 1:
            line = fh.readline()
            if len(line)<10: break
            vals = line.split()
            name=vals[0]
            rgb = map(float, vals[1:4])
            dim = [int(vals[4]), int(vals[5])]
            spacing = float(vals[6])  
            grid = Grid(name=name, dim=dim, rgb=rgb, spacing=spacing)
            self.add_grid(grid)
            
            numTrodesByDim += dim[0]*dim[1]

        line = fh.readline()
        numTrodesByCount = 0
        while 1:
            line = fh.readline()
            if len(line)<10: break
            vals = line.split()
            xyz = map(float, vals[2:])
            name, num = vals[0], int(vals[1])
            electrode = Electrode(name, num, xyz)
            grid = self.get_grid(name)
            grid.set_electrode(num, electrode)
            numTrodesByCount += 1

        #todo: check trode by dim vs trode count

    def to_conf_file(self):
        "Convert self to a config file string"
        lines = []
        lines.append('GRD : Version 1.0')
        lines.append('GrdName    R       G       B    dim1  dim2 spacing')

        for grid in self.get_grids():
            #RF 1.0000 0.0000 1.0000 1 8 1.0000
            name = grid.get_name()
            r,g,b = grid.get_rgb()
            dim1,dim2  = grid.get_dimensions()
            spacing = grid.get_spacing()
            lines.append('%s %1.4f %1.4f %1.4f %d %d %1.4f' %
                         (name, r, g, b, dim1, dim2, spacing))
        lines.append('')
        lines.append('GrdName GrdNum     X       Y      Z')
        for grid in self.get_grids():
            for e in grid.get_electrodes():
                x,y,z = e.get_xyz()
                lines.append('%s %d %1.4f %1.4f %1.4f' %
                             (e.get_name(), e.get_num(), x, y, z))
        return '\n'.join(lines)

    def to_eoi(self):
        """
        Get all the electrodes for every grid in the Grids instance as an
        EOI
        """

        eoi = EOI()
        eoi.set_electrodes([ (e.get_name(), e.get_num())
                             for aGrid in self.get_grids()
                             for e in aGrid.get_electrodes()])
        return eoi

class Ann(dict, AssociatedFile) :
    extension = 'ann.csv'
    filetype  = 13

    def __init__(self, dbaseFields=None, useFile=None, message=None) :
        AssociatedFile.__init__(self, dbaseFields, useFile)
        self.message = message

    # xxx error checking of file format
    def _load_data(self, fh) :
        reader = csv.reader(fh)
        for line in reader :
            if not line : continue

            self[(float(line[0]), float(line[1]))] = {
                'startTime'     : float(line[0]),
                'endTime'       : float(line[1]),
                'created'       : line[2],
                'edited'        : line[3],
                'username'      : line[4],
                'color'         : line[5],
                'code'          : line[6],
                'annotation'    : line[7]}

    def _save_data(self, fh, append = False) :
#        writer = csv.writer(fh)
        startEndTimes = self.keys()
        startEndTimes.sort()
        for startEndTime in startEndTimes :
            print self[startEndTime]
          
def assoc_factory_web(entry):
    typeMap = { 3 : Amp,
                4 : Grids,
                5 : EOI,                
                8 : Loc3dJr,
                }
    return typeMap[entry.type](entry.get_orig_map())

def assoc_factory_filesystem(filetype, fname):
    typeMap = { 3 : Amp,
                4 : Grids,
                5 : EOI,
                8 : Loc3dJr,
                12 : Info,
                13 : Ann,
                }
    return typeMap[filetype](useFile=fname)

EDF, BMSI, NSASCII, NSCNT, FLOATARRAY, W18 = range(6)

class EEGBase:               
    def __init__(self):
        self.readmap = {BMSI : self._read_nicolet,
                        W18  : self._read_w18,
                       }

        self.scale= None

        # store the last get_data query so repeated calls will use the
        # cached version.  lastDataQuery is a
        # ( (tmin, tmax), (t, data) ) tuple
        self.lastDataQuery = None
        
    def load_data(self):
        raise NotImplementedError('Derived must override')

    def get_eois(self):
        return self.get_associated_files(5, mapped=1)

    def get_eoi(self, fname):
        eois =  self.get_associated_files(5, mapped=0, fname=fname)
        if len(eois)==0:
            raise ValueError, 'No EOI for patient %d with filename %s' % \
                  (self.pid, fname)
        elif len(eois)>1:
            raise ValueError, 'Found multiple EOIS %d with filename %s' % \
                  (self.pid, fname)
        else:
            return eois[0]

    def get_amp(self, name=None):
        if name is not None:
            amps = self.get_associated_files(3, mapped=1)
            for amp in amps:
                if amp.filename == name:
                    self.amp = amp
                    return amp
            else:
                raise ValueError('Could not find amp file with name %s' % name)

        try:
            return self.amp
        except AttributeError:
            amp = self.get_associated_files(3, mapped=1)
            if len(amp)==1:
                amp = amp[0]
            elif len(amp)>1:
                amp = amp[0]
                amp.message =  'Warning: %s has more than one amp file; using %s' %\
                      (self.filename, amp.filename)
            else:
                #make a default amp file
                amp = Amp()
                amp.message = 'No AMP file associated with this EEG; using default'
                channels = []
                for i in range(self.get_channels()):
                    channels.append((i+1, 'NA', i+1))
                amp.set_channels(channels)

        self.amp = amp
        return amp

    def get_grd(self):
        try: return self.grd
        except AttributeError:
            grd = self.get_associated_files(4, mapped=1)
            if len(grd)==1:
                grd = grd[0]
            elif len(grd)>1:
                grd = grd[0]
                # xxx popup select dialog
                print 'Warning: %s has more than one grd file; using %s' %\
                      (self.filename, grd.filename)
            elif len(grd)==0:
                return None
        self.grd = grd
        return grd

    def get_loc3djr(self):
        try: return self.loc3djr
        except AttributeError: pass
        
        loc3djr = self.get_associated_files(8, mapped=0)
        if not len(loc3djr):
            return None
        self.loc3djr = loc3djr[0]
        return self.loc3djr

    def get_ann(self, name=None) :
        if name is not None :
            anns = self.get_associated_files(13, mapped=1)
            for ann in anns :
                if ann.filename == name :
                    self.ann = ann
                    return ann
            else :
                raise ValueError('Could not file annotation file with name %s' % name)
            
        try : return self.ann
        except AttributeError :
            anns = self.get_associated_files(13, mapped=1)
            if len(anns) == 1 :
                ann = anns[0]
            elif len(anns) > 1 :
                ann = anns[0]
                ann.message = 'Warning: %s has more than one annotation file; using %s' % \
                              (self.filename, ann.filename)
            else :
                ann = Ann(message='No annotation file associated with this EEG; using default')

        self.ann = ann
        return ann

    def get_num_samples(self):
        self.load_data()
        if self.file_type==BMSI: # nicolet bmsi
            return os.path.getsize(self.fullpath)/(self.channels*2)
        elif self.file_type==W18:
            return os.path.getsize(self.fullpath)/18432*1000
        else: raise ValueError('Can only handle Nicolet BMSI file currently')

    def get_tmax(self):
        N = self.get_num_samples()
        return N/self.freq

    def set_baseline(self):
        t, data = self.get_data(0, 0.1)
        #self.baseline = resize(median(transpose(data)), (1, self.channels))
        self.baseline = median(data)
        #print self.baseline.shape, data.shape

    def get_baseline(self):
        try: return self.baseline
        except AttributeError:
            self.set_baseline()
            return self.baseline

    def get_data(self, tmin, tmax):
        if (self.lastDataQuery is not None and
            self.lastDataQuery[0] == (tmin, tmax) ):
            return self.lastDataQuery[1]
        assert(tmax>tmin)

        #print 'filetype', type(self.file_type), self.file_type
        
        try: t, data = self.readmap[self.file_type](tmin, tmax)
        except KeyError:
            raise KeyError('Do not know how to handle file type %s'%self.file_type)
        self.lastDataQuery = ( (tmin, tmax), (t, data) )

        return t, data

    def _read_w18(self, tmin, tmax):
        return file_formats.get_w18_data(self.fh, indmin, indmax)

    def _read_nicolet(self, tmin, tmax):
        """Load Nicolet BMSI data."""

        if tmin<0: tmin=0

        BYTES_PER_SAMPLE = self.channels*2
        indmin = int(self.freq*tmin)
        NUMSAMPLES = os.path.getsize(self.fullpath)//BYTES_PER_SAMPLE
        
        indmax = min(NUMSAMPLES, int(self.freq*tmax))

        byte0 = indmin*BYTES_PER_SAMPLE
        numbytes = (indmax-indmin)*BYTES_PER_SAMPLE

        self.fh.seek(byte0)
        data = fromstring(self.fh.read(numbytes), Int16)
        if sys.byteorder=='big': data = data.byteswapped()
        data = data.astype(Float)
        data.shape = -1, self.channels

        if self.scale is not None:
            data = self.scale*data

        t = (1/self.freq)*arange(indmin, indmax)
        return t, data

    def _read_float_array(self, fname):
        """Load an array of C floats."""

        fh = file(fname, 'rb')
        data = fromstring(fh.read(), Float16)
        data.shape = -1, self.channels
        return data

    def get_associated_files(self, atype, mapped=1, fname=None):
        """
        Return a list of AssociateFiles of type atype.  If mapped is
        true, only return files that are mapped to this eeg, else
        return all associated files of type for this patient
        """

        raise NotImplementedError('Derived must override')

class EEGWeb(EEGBase):
    def __init__(self, fields):
        EEGBase.__init__(self)
        self.__dict__.update(fields)
        
        def make_get_set(name, val):
            def get_func(): return fields[name]
            def set_func(val): setattr(self, name, val)
            return get_func, set_func

        for name, val in fields.items():
            get_func, set_func = make_get_set(name, val)
            setattr(self, 'get_' + name, get_func)
            setattr(self, 'set_' + name, set_func)

    def load_data(self):
        try: self.fh
        except AttributeError: pass
        else: return
        
        dm = servers.datamanager
        fname =  dm.get_local_filename(
            self.pid, 'eegs', self.filename)
        self.fullpath = fname
        try: self.fh = file(fname, 'rb')
        except IOError, msg:
            raise ValueError('Could no open %s for reading' % fname)

    def get_associated_files(self, atype, mapped=1, fname=None):
        """
        Return a list of AssociateFiles of type atype.  If mapped is
        true, only return files that are mapped to this eeg, else
        return all associated files of type for this patient
        """

        # note, you are getting into issues of locking here, since the
        # mysql tables solution requires that the dbase has not
        # changed since the entry was checked out.  If multiple
        # objects contain entries within a single program, or multiple
        # users of the program run simultaneously, the dbase can get
        # out of whack
        if not mapped:
            if fname is None:
                # get all the associated files for this patient
                where = 'pid=%d and type=%d' % (self.pid, atype)
            else:
                where = 'pid=%d and type=%d and filename="%s"' % \
                        (self.pid, atype, fname)
        else:
            # get the names of the files associates with this EEG and
            # then return a list of AssociateFile objects for these
            # files
            cursor = servers.sql.cursor
            pid = self.pid
            sql = """        
            SELECT assocmap.assocfile FROM assocfile, assocmap 
            WHERE assocfile.pid=%s AND assocmap.pid=%s
            AND assocmap.filename=%s
            AND assocmap.assocfile=assocfile.filename
            AND assocfile.type=%s
            """ 

            cursor.execute(sql,
                           (pid, pid, self.filename, atype))
            results = cursor.fetchall()
            fnames = [r['assocfile'] for r in results]
            filelist = '", "'.join(fnames)
            where = 'pid=%d and type=%d and filename in ("%s")' % \
                    (pid, atype, filelist)
        entries = servers.sql.assocfile.select(where)

        l = []
        for entry in entries:
            l.append(assoc_factory_web(entry))

        return l

def read_eeg_params(fh):
    cfuncs = {
        'filename'        : str,
        'date'            : str,
        'description'     : str,
        'channels'        : int,
        'freq'            : int,
        'classification'  : int,
        'file_type'       : int,
        'behavior_state'  : int,
        }

    d = {}
    for line in fh:
        name, val = line.split(':',1)
        name = name.strip()
        val = val.strip()
        cfunc = cfuncs[name]
        d[name] = cfunc(val)
    return d

class EEGFileSystem(EEGBase):
    def __init__(self, fullpath, params=None, get_params=None):
        """
        params is a dict
        get_params has dict signature dict = get_params(fullpath)
        """

        EEGBase.__init__(self)
        if not os.path.exists(fullpath):
            raise ValueError('%s does not exist' % fullpath)

        self.fh = file(fullpath, 'rb')
        self.path, self.filename = os.path.split(fullpath)
        self.fullpath = fullpath
        
        if params is None:
            params = self._get_params()

        if params is None and get_params is not None:
            params = get_params(fullpath)

        if params is None:
            raise ValueError('Cannot get eeg params')
            
        self.__dict__.update(params) # sets filename and other attrs

        def make_get_set(name, val):
            def get_func(): return params[name]
            def set_func(val): setattr(self, name, val)
            return get_func, set_func

        for name, val in params.items():
            get_func, set_func = make_get_set(name, val)
            setattr(self, 'get_' + name, get_func)
            setattr(self, 'set_' + name, set_func)

        self.eois = self._get_assocfiles('*.eoi')
        self.amps = self._get_assocfiles('*.amp')
        self.infos = self._get_assocfiles('*.info')
        self.grds = self._get_assocfiles('*.grd.csv')
        base, ext = os.path.splitext(self.filename)
        self.anns = self._get_assocfiles('%s.ann.csv' % base)

        # Warn if old-style CSV files found.
        csvs = self._get_assocfiles('*.csv')
        legit = Set(self.grds + self.anns)
        bad = []
        for csv in csvs:
            if csv not in legit:
                bad.append(csv)
        if bad :
            msg = "Found the following old-style CSV files:\n"
            for csv in bad :
                msg += "    %s\n" % csv
            msg += "\nRename to *.grd.csv or *.ann.csv."
            dlg = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                    buttons=gtk.BUTTONS_OK,
                                    message_format=msg)
            dlg.set_title('Old CSV Files Found')
            response = dlg.run()
            dlg.destroy()

    def _get_assocfiles(self, pattern):
        return glob.glob(os.path.join(self.path, pattern))

    def load_data(self):
        try: self.fh
        except AttributeError: pass
        else: return

        try: self.fh = file(self.fullpath, 'rb')
        except IOError, msg:
            raise ValueError('Could not open %s for reading' % self.fullpath)

    def get_associated_files(self, atype, mapped=1, fname=None):
        """
        Return a list of AssociateFiles of type atype.  If mapped is
        true, only return files that are mapped to this eeg, else
        return all associated files of type for this patient
        """

        BNI, AMP, EOI, GRD, INFO, ANN = 1, 3, 5, 8, 12, 13
        assocmap = {AMP : self.amps,
                    EOI : self.eois,
                    GRD : self.grds,
                    INFO : self.infos,
                    ANN : self.anns,
                    }

        fnames = assocmap.get(atype, None)
        if fnames is None: raise ValueError('Cannot handle assoc type %d' % atype)

        l = []
        for fname in fnames:
            fullpath = os.path.join(self.path, fname)
            l.append(assoc_factory_filesystem(atype, fullpath))

        return l

def submit_form(host, path, fields, headers=None, fileInfo=None):
    """
    host is the base host, eg www.yahoo.com or someserver.com:8080

    path is the absolute path to the form, eg /someDir/someForm
    
    fields is a dictionary from form variables to values.  The values
    must be convertible to string via str.  Do not include a file
    upload value here.  This should go in the fileInfo dictionary.

    headers is an optional dictionary of HTTP headers to include, eg,
    Authorization or Referer
        
    fileInfo is a dictionary for upload files with keys
      'name'     : the html form name
      'filename' : the upload file name
      'content'  : the data

    """

    if headers is None: headers = {}

    sep = '10252023621350490027783368690'

    h = httplib.HTTP(host)
    h.putrequest('POST', path)
    for key, val in headers.items():
        h.putheader(key, val)
    h.putheader('Content-Type', 'multipart/form-data; boundary=%s' % sep)
    h.putheader('User-Agent', 'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.3a) Gecko/20021212')
    h.putheader('Host', host)
    h.putheader('Accept', 'text/html, image/gif, image/jpeg, *; q=.2, */*; q=.2')
    h.putheader('Connection',  'keep-alive')
    body = []

    sep = '--' + sep
    if fileInfo is not None:
        body.append(sep)
        body.append(
            'Content-Disposition: form-data; name="%s"; filename="%s"' % 
            (fileInfo['formvar'], fileInfo['filename']))

        body.append('Content-Type: text/plain')
        
        body.append('')
        body.append(str(fileInfo['content']))
        body.append('')

    for key, val in fields.items():
        body.append(sep);
        body.append('Content-Disposition: form-data; name="%s"' % key)
        body.append('')
        body.append(str(val))

    body.append(sep+'--')
    s = '\n'.join(body)+'\n'
    h.putheader('Content-length', '%d' % len(s))
    h.endheaders()
    h.send(s)

    code, text, msg = h.getreply()

    if code != 200:
        raise RuntimeError, msg
