from __future__ import division

import os, sys, re, glob, urllib, httplib, warnings
from cStringIO import StringIO
from sets import Set
from matplotlib.cbook import mkdirs, listFiles

from scipy import array,  \
     arange, fromstring, take, sqrt, sum, zeros, resize,\
     transpose
from scipy import median
from utils import all_pairs_ij, all_pairs_eoi
import file_formats
import csv
import gtk

import math

import datetime

import servers

import scipy
import scipy.signal

import pickle

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
    """
    CLASS: Electrode
    DESCR:
    """
    def __init__(self, name, num, xyz=None):
        self.name = name
        self.num = num
        if xyz is None: self.xyz = array([0.0, 0.0, 0.0])
        else: self.xyz = xyz

    def set_xyz(self, xyz):
        try: xyz.shape
        except AttributeError: xyz = array(xyz, 'd')
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
    """
    CLASS: Grid
    DESCR:
    """
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
    """
    CLASS: AssociatedFile
    DESCR:
    """
    def __init__(self, dbaseFields=None, useFile=None):
        self.eeg = None
        self.filename = None
        self.fullpath = None

        if dbaseFields is None:
            import mx.DateTime
            now = mx.DateTime.now()
            dbaseFields = {'description': '',
                           'date': now, 
                           'type': self.filetype,
                           'filename': 'none.' + self.extension}
            self.existsWeb = 0
            self.__dict__.update(dbaseFields)

            if useFile is not None :
                basepath, fname = os.path.split(useFile)
                self.filename = fname
                self.fullpath = useFile
                self.load_data(useFile)
        else:
            self.__dict__.update(dbaseFields)
            self.set_exists_web(pid=dbaseFields['pid'],
                                filename=dbaseFields['filename'])
            self.load_data()

    def set_active_eeg(self, eeg) :
        self.eeg = eeg

        # Set default file name if necessary.
        if not self.is_web_file() and self.filename == 'none.' + self.extension :
            # Set path to eeg_root.ext.
            root, ext = os.path.splitext(eeg.fullpath)
            self.fullpath = root + '.' + self.extension
            basepath, fname = os.path.split(self.fullpath)
            self.filename = fname

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
        if self.is_web_file() :
            # xxx web save
            print "web save"
        else :
            if useFile is None :
                useFile = self.fullpath

            if useFile is not None :
                fh = None
                try :
                    if append :
                        fh = file(useFile, 'a')
                    else :
                        fh = file(useFile, 'w')
                except IOError :
                    raise ValueError('Failed to open %s for writing/appending' % useFile)
                self._save_data(fh, append)

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
    """
    CLASS: Loc3dJr
    DESCR:
    """
    extension = 'csv'
    filetype = 8
    def __init__(self, dbaseFields=None, useFile=None):
        AssociatedFile.__init__(self, dbaseFields, useFile)

    def _load_data(self, fh):
        self.fh = StringIO(fh.read())

class Info(AssociatedFile):        
    """
    CLASS: Info
    DESCR:
    """
    extension = 'info'
    filetype = 12
    def __init__(self, dbaseFields=None, useFile=None):
        AssociatedFile.__init__(self, dbaseFields, useFile)

    def _load_data(self, fh):
        self.fh = StringIO(fh.read())
        
class EOI(list, AssociatedFile):
    """
    CLASS: EOI
    DESCR:
    """
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
        Return value is a list of indicies into the data array for the channels
        in the eoi

        Raises a KeyError if an eoi channel cannot be found in the amp
        struct and returns an error string indicating the problem EOI
        """

        d = amp.get_electrode_to_indices_dict()
        indices = [d[key] for key in self]

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
    CLASS: Amp
    DESCR:
    """
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
            #print "Amp._load_data(): line='%s'" % line
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

        mcc XXX: what did I write the below comments for?
        
        amp = eeg.get_amp()
        cnumd = amp.get_channelnum_dict()
        electrode = cnumd[56]

        ...in gridmanager....
        marker = gridManager.markerd[electrode]
        marker.set_center(xyz)
        marker.set_color(vtkColor)

        ....
        for e1,e2 in mypairs:
            e1, e2 = some_electrodes()
            corr = corrdist(e1,e2)
            def func(x): return corr
            gridManager.connect_markers(e1, e2, scalarfunc=func)
        
        """

        return dict([ ( ind, (name,num) ) for ind, name, num in self])        

class Grids(AssociatedFile, dict):
    """
    CLASS: Grids
    DESCR:
    """
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
    """
    CLASS: Ann
    DESCR:
    """
    extension = 'ann.csv'
    filetype  = 13
    currVersion = 1.0

    def __init__(self, dbaseFields=None, useFile=None, message=None) :
        self.eois = {}

        AssociatedFile.__init__(self, dbaseFields, useFile)
        self.message = message

    # xxx error checking of file format
    def _load_data(self, fh) :
        reader = csv.reader(fh)
        for line in reader :
            if not line : continue

            version = float(line[0])
            if version == 1.0 :
                # Get electrodes in eoi
                trodes = []
                description = line[5]
                eoiLine = line[6]
                r = re.compile(';\s*')
                for trode in r.split(eoiLine) :
                    grid, num = trode.split('-')
                    trodes.append((grid, int(num)))

                # Check for EOIs with the same name but different electrodes.
                # Create a new EOI or use previously created one.
                if self.eois.get(description) :
                    if self.eois[description] <> trodes :
                        print 'WARNING: EOIs with description, %s, have different electrodes; using first set of electrodes.' % description
                    eoi = self.eois[description]
                else :
                    eoi = EOI(electrodes=trodes)
                    eoi.set_description(description)
                    self.eois[description] = eoi

                self['%1.1f' % float(line[1]), '%1.1f' % float(line[2]), line[3]] = {
                    'version'		: float(line[0]),
                    'startTime'		: float(line[1]),
                    'endTime'		: float(line[2]),
                    'created'		: line[3],
                    'edited'		: line[4],
                    'eoi'		: eoi,
                    'username'		: line[7],
                    'color'		: line[8],
                    'alpha'		: float(line[9]),
                    'code'		: line[10],
                    'state'		: line[11],
                    'visible'		: bool(int(line[12])),
                    'shrink'		: bool(int(line[13])),
                    'annotation'	: line[14]}
            else :
                print "WARNING: Unsupported annotation version: ", line
                # XXX what to do - don't lost the entry!

    def _save_data(self, fh, append = False) :
        writer = csv.writer(fh)
        keys = self.keys()
        keys.sort()
        for key in keys :
            eoi = self[key]['eoi']
            trodes = ';'.join(['%s-%s' % (grid, num) for grid, num in eoi])

            line = [self.currVersion,
                    self[key]['startTime'],
                    self[key]['endTime'],
                    self[key]['created'],
                    self[key]['edited'],
                    eoi.description,
                    trodes,
                    self[key]['username'],
                    self[key]['color'],
                    self[key]['alpha'],
                    self[key]['code'],
                    self[key]['state'],
                    int(self[key]['visible']),
                    int(self[key]['shrink']),
                    self[key]['annotation']]
            writer.writerow(line)

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

EDF, BMSI, NSASCII, NSCNT, FLOATARRAY, W18, AXONASCII, NEUROSCANASCII, ALPHAOMEGAASCII = range(9)
EPOCH = 14

class EEGBase:               
    """
    CLASS: EEGBase
    DESCR:
    """
    def __init__(self, amp):
        #print "EEGBase(amp=", amp, ")"
        
        self.readmap = {BMSI : self._read_nicolet,
                        W18  : self._read_w18,
                        EPOCH : self._read_epoch,
                        AXONASCII: self._read_axonascii,
                        NEUROSCANASCII: self._read_neuroscanascii,
                        ALPHAOMEGAASCII: self._read_neuroscanascii
                       }

        self.scale= None

        # store the last get_data query so repeated calls will use the
        # cached version.  lastDataQuery is a
        # ( (tmin, tmax), (t, data) ) tuple
        self.lastDataQuery = None

        self.amp = amp


        self.rectifiedChannels = {}
        self.hilbertedChannels = {}

        for (cnum, cname, gnum) in amp:
            self.rectifiedChannels[(cname,gnum)] = False
            self.hilbertedChannels[(cname,gnum)] = False

    def load_data(self):
        raise NotImplementedError('Derived must override')

    def get_eois(self):
        return self.get_associated_files(5, mapped=1)

    def set_rectified(self, rectifiedChannels):
        #print "mcc XXX: EEGBase.set_rectified( ", rectifiedChannels, ")"

        for i,j in rectifiedChannels.iteritems():
            self.rectifiedChannels[i] = j
            
        d = self.amp.get_electrode_to_indices_dict()
        print "set_rectified: get_electrode_to_indices_dict is " , d

        self.lastDataQuery = None

    def set_hilberted(self, hilbertedChannels):
        #print "mcc XXX: EEGBase.set_hilberted( ", hilbertedChannels, ")"

        for i,j in hilbertedChannels.iteritems():
            self.hilbertedChannels[i] = j
            
        d = self.amp.get_electrode_to_indices_dict()
        print "set_hilberted: get_electrode_to_indices_dict is " , d

        self.lastDataQuery = None

    def get_rectified(self):
        #print "mcc XXX: EEGBase.get_rectified()"
        return self.rectifiedChannels

    def get_hilberted(self):
        #print "mcc XXX: EEGBase.get_hilberted()"
        return self.hilbertedChannels

    def get_eoi(self, fname):
        eois =  self.get_associated_files(5, mapped=0, fname=fname)
        if len(eois)==0:
            raise ValueError, 'No EOI for patient %d with filename %s' % \
                  (self.pid, fname)
        elif len(eois)>1:
            raise ValueError, 'Found multiple EOIS %d with filename %s' % \
                  (self.pid, fname)
        else:
            eois[0].set_active_eeg(eeg)
            return eois[0]

    def get_amp(self, name=None):

        if name is not None:
            amps = self.get_associated_files(3, mapped=1)
            for amp in amps:
                if amp.filename == name:
                    amp.set_active_eeg(self)
                    self.amp = amp
                    break
            else:
                raise ValueError('Could not find amp file with name %s' % name)

        try: return self.amp
        except AttributeError:
            amps = self.get_associated_files(3, mapped=1)
            for amp in amps :
                amp.set_active_eeg(self)
            if len(amps)==1:
                amp = amps[0]
            elif len(amps)>1:
                amp = amps[0]
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

        amp.set_active_eeg(self)
        self.amp = amp
        return amp

    def get_grd(self):
        try: return self.grd
        except AttributeError:
            grds = self.get_associated_files(4, mapped=1)
            if len(grds)==1:
                grd = grds[0]
            elif len(grds)>1:
                grd = grds[0]
                # xxx popup select dialog
                print 'Warning: %s has more than one grd file; using %s' %\
                      (self.filename, grd.filename)
            elif len(grds)==0:
                return None

        grd.set_active_eeg(self)
        self.grd = grd
        return grd

    def get_loc3djr(self):
        try: return self.loc3djr
        except AttributeError: pass
        
        loc3djrs = self.get_associated_files(8, mapped=0)
        if not len(loc3djrs):
            return None
        self.loc3djr = loc3djrs[0]

        self.loc3djr.set_active_eeg(self)
        return self.loc3djr

    def get_ann(self, name=None) :
        if name is not None :
            anns = self.get_associated_files(13, mapped=1)
            for ann in anns :
                if ann.filename == name :
                    ann.set_active_eeg(self)
                    self.ann = ann
                    break
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

        ann.set_active_eeg(self)
        self.ann = ann
        return ann

    def get_num_samples(self):
        print "get_num_samples: self.file_type is ",  self.file_type
        self.load_data()
        if self.file_type==BMSI: # nicolet bmsi
            return os.path.getsize(self.fullpath)/(self.channels*2)
        elif self.file_type==W18:
            return os.path.getsize(self.fullpath)/18432*1000
        elif self.file_type==AXONASCII:
            raw_data = self.get_raw_data()
            print "raw_data.shape is ", raw_data.shape
            (rows, cols) = raw_data.shape
            num_entries_per_channel = int(rows / self.get_channels())
            #print "num_entries_per_channel=", num_entries_per_channel
            num_samples = num_entries_per_channel * self.get_freq()
            #print "num_samples=", num_samples
            return(math.floor(num_samples))
        elif self.file_type==NEUROSCANASCII:
            raw_data = self.get_raw_data()
            #print "raw_data.shape is ", raw_data.shape
            (rows, cols) = raw_data.shape
            return cols
        else: raise ValueError('Can only handle certain file types currently')
        

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
        # mcc XXX: removed this (probably speed-improving)
        # lastDataQuery optimisation as we may be requerying with new
        # prefiltering. maybe bring this back somehow.
        
#        if (self.lastDataQuery is not None and
#            self.lastDataQuery[0] == (tmin, tmax) ):
#            return self.lastDataQuery[1]
        assert(tmax>tmin)

        #print 'filetype', type(self.file_type), self.file_type

        #print self.file_type, self.readmap[self.file_type]
        try: t, data = self.readmap[self.file_type](tmin, tmax)
        except KeyError:
            raise KeyError('Do not know how to handle file type %s'%self.file_type)
#        self.lastDataQuery = ( (tmin, tmax), (t, data) )

        # OK, now possibly modify the data as specified in the
        # "filter electrode" view!
        d = self.amp.get_electrode_to_indices_dict()
        #print "EEGBase.get_data(): d=", d
        for name, index in d.iteritems(): 
            if (self.rectifiedChannels[name]):
                x = data[:,index]
                data[:,index] = abs(data[:,index])
                 
            if (self.hilbertedChannels[name]):
                x = data[:,index]
                # now get the hilbert of this
                hilberted_data = scipy.signal.hilbert(x)
                #print "len/type of x is ", len(x), type(x), x.typecode(), "len/type of hilberted data is " , len(hilberted_data), type(hilberted_data), hilberted_data.typecode()
                data[:,index] = abs(hilberted_data)
                
        #print "EEGBase.get_data(): t.shape=", t.shape, ", data.shape=", data.shape
        return t, data

    def _read_epoch(self, tmin, tmax):

        indmin = int(self.freq*tmin)
        indmax = int(self.freq*tmax)
        indmax = min(self.epochdata.shape[0], indmax)
        indmin = max(0, indmin)
        #print 'ind min/max', indmin, indmax
        t = (1/self.freq)*arange(indmin, indmax)
        data = self.epochdata[indmin:indmax]
        #print indmin, indmax, t.shape, data.shape
        return t, self.epochdata[indmin:indmax]

    def _read_w18(self, tmin, tmax):
        return file_formats.get_w18_data(self.fh, indmin, indmax)

    def _read_nicolet(self, tmin, tmax):
        """Load Nicolet BMSI data."""

        #print "_read_nicolet: tmin=", tmin, "tmax=", tmax

        if tmin<0: tmin=0

        BYTES_PER_SAMPLE = self.channels*2
        indmin = int(self.freq*tmin)
        NUMSAMPLES = os.path.getsize(self.fullpath)//BYTES_PER_SAMPLE
        
        indmax = min(NUMSAMPLES, int(self.freq*tmax))

        byte0 = indmin*BYTES_PER_SAMPLE
        numbytes = (indmax-indmin)*BYTES_PER_SAMPLE

        self.fh.seek(byte0)
        data = fromstring(self.fh.read(numbytes), 'h')
        if sys.byteorder=='big': data = data.byteswapped()
        data = data.astype('d')
        data.shape = -1, self.channels

        if self.scale is not None:
            data = self.scale*data

        t = (1/self.freq)*arange(indmin, indmax)
        #print 'nic', data.shape

        #print "_read_nicolet: t is " , t
        
        return t, data

    def time_to_raw_indices(self, tmin, tmax, raw_data_shape, n_channels, sampling_rate):
        # sampling rate = e.g. 250
        #print "time_to_raw_indices(tmin=%f, tmax=%f, raw_data_shape=" % (tmin, tmax), raw_data_shape, "n_channels=%d, sampling_rate=%d" % (n_channels, sampling_rate)

        # rows = 12 channels, 12 channels, 12 channels, etc.
        # cols = # of datapoints per segment: 500
        (raw_data_rows, raw_data_cols) = raw_data_shape

        #if (tmin < 0.0):
        #    return None
        # actually, allow this to occur... and return zeros magically for period before 0.0

        if (tmin > tmax):
            return None

        raw_x1 = (tmin * sampling_rate)
        raw_x2 = (tmax * sampling_rate)

        # now mod by raw_data_cols

        raw_index1 = math.floor(raw_x1 / raw_data_cols) 
        raw_index2 = math.floor(raw_x2 / raw_data_cols)

        raw_offset1 = math.floor(((raw_x1 / raw_data_cols) - raw_index1) * raw_data_cols)
        raw_offset2 = math.floor(((raw_x2 / raw_data_cols) - raw_index2) * raw_data_cols)
        
        # multiply by n_channels because the data is organized that way...
        #raw_index1 = raw_index1 * n_channels
        #raw_index2 = raw_index2 * n_channels
        
        #print "time_to_raw_indices: calculated raw_index1=%d, raw_offset1=%d, raw_index2=%d, raw_offset2=%d" % (raw_index1, raw_offset1, raw_index2, raw_offset2)
       
        return raw_index1, int(raw_offset1), raw_index2, int(raw_offset2)

    def _read_neuroscanascii(self, tmin, tmax):
        print "_read_neuroscanascii(", tmin, ",", tmax,")"
        raw_data = self.get_raw_data()
        print "_read_neuroscanascii(): raw data has shape ", raw_data.shape
        print "_read_neuroscanascii(): raw data[0,0:10]=", raw_data[0,0:10]
        (raw_data_rows, raw_data_cols) = raw_data.shape
        freq = self.get_freq()
        print "_read_neuroscanascii(): freq=" ,freq
        raw_x1 = int(round(tmin * freq))
        raw_x2 = int(round(tmax * freq))

        t = arange(tmin, tmax , 1.0/freq)
        print "t[-1] is" , t[-1]
        print "_read_neuroscanascii(): t[0:10] is ", t[0:10]

        print "_read_neuroscanascii(): len(t)=", len(t)

        print "_read_neuroscanascii(): raw_x1, raw_x2 = ", raw_x1, raw_x2


        if (raw_x2 > raw_data_cols):
            print "asking for too much data!!!"
            print "pad data with zeros here"
            data = raw_data[:, raw_x1:raw_data_cols]
            print "raw_data_cols/freq is ", raw_data_cols/freq
            print "tmin =", tmin
            print "(raw_data_cols-raw_x1)/freq = ",  (raw_data_cols-raw_x1)/freq
            print "1.0/freq=", 1.0/freq
            t = arange(tmin, tmin+(raw_data_cols-raw_x1)/freq , 1.0/freq)
            print "len(t) is ", len(t)
            print "len(data) is ", len(data)
            print "type(data) is ", type(data)
        else:
            data = raw_data[:, raw_x1:raw_x2]
        print "_read_neuroscanascii(): t.shape=", t.shape
        data2 = transpose(data)
        print "_read_neuroscanascii(): data2.shape=", data2.shape
        return t, data2
        
    
    def _read_axonascii(self, tmin, tmax):
        """
        This is marginally horrendous, but so is the file format it is parsing.
        """
        #print "_read_axonascii: tmin=", tmin, "tmax=", tmax
        #print "_read_axonascii: date_start = ", self.get_date() + datetime.timedelta(0,tmin) , "date_end = " , self.get_date() + datetime.timedelta(0,tmax)

        raw_data = self.get_raw_data()
        #print "_read_axonascii(): raw data has shape ", raw_data.shape
        (raw_data_rows, raw_data_cols) = raw_data.shape
        n_channels = self.get_channels()
        freq = self.get_freq()
        #print "_read_axonascii: freq = ", freq
        channel_length = math.floor((tmax-tmin)*self.get_freq())
        data = zeros((channel_length, n_channels, ), 'd')
        #print "created data array of size ", data.shape

        # given tmin find the appropriate array .. in seconds, just divide by 2 then multiply by n_channels

        raw_index1, raw_offset1, raw_index2, raw_offset2 = self.time_to_raw_indices(tmin, tmax, raw_data.shape, n_channels, freq)

        data_index = 0
        #print "raw_index1=", raw_index1, "raw_index2=", raw_index2
        raw_index1 = int(raw_index1)
        raw_index2 = int(raw_index2)
        #print "raw_index1=", raw_index1, "raw_index2=", raw_index2
        for raw_index in range(raw_index1, raw_index2):
            #print "doing raw_data index=%d, data index =%d" % (raw_index, data_index)
            for c in range(0, n_channels):
                # do a general for loop using information about offsets...
                data_offset = 0
                for raw_offset in range (raw_offset1, raw_data_cols):
                    #print "setting data[%d][%d] to raw_data[%d][%d]=%f" % \
                    #      ((data_index*500)+data_offset, c ,raw_index*n_channels + c,raw_offset, raw_data[raw_index*n_channels+c][raw_offset])

                    if ((raw_offset == raw_offset1) | (raw_offset == raw_data_cols)):
                        pass
                        
                    data[(data_index*500)+data_offset][c] = raw_data[raw_index*n_channels + c][raw_offset]
                    data_offset = data_offset + 1
                                            
                # now copy from next major index
                for raw_offset in range (0, raw_offset2):
                    #print "setting data[%d][%d] to raw_data[%d][%d]=%f" % \
                    #      ((data_index*500)+data_offset, c ,raw_index*n_channels + c,raw_offset, raw_data[raw_index*n_channels+c][raw_offset])


                    if ((raw_offset == 0) | (raw_offset == raw_offset2)):
                        pass

                    data[(data_index*500)+data_offset][c] = raw_data[(raw_index+1)*n_channels + c][raw_offset]
                    data_offset = data_offset + 1

            data_index = data_index + 1

        # we also want to build t. t will be , in this case, an array of (tmax-tmin) * 250 elements
        t = arange(tmin, tmax , 1.0/freq)

        print "_read_axonascii(): size of t is " , t.shape
        print "_read_axonascii(): size of data is " , data.shape

        return t, data
        
        
    def _read_float_array(self, fname):
        """Load an array of C floats."""

        fh = file(fname, 'rb')
        data = fromstring(fh.read(), 'f')
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
    """
    CLASS: EEGWeb
    DESCR: Not currently used
    """
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
    """
    CLASS: EEGFileSystem
    DESCR:
    """
    def __init__(self, fullpath, amp, params=None, get_params=None):
        #print "EEGFileSystem(fullpath=", fullpath, ", amp=", amp, ")"
        """
        params is a dict
        get_params has dict signature dict = get_params(fullpath)
        """

        EEGBase.__init__(self, amp)
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
    FUNC: submit_form
    DESCR: host is the base host, eg www.yahoo.com or someserver.com:8080

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
