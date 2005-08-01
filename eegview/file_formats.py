from __future__ import division

import math, re, os, sys
from sets import Set
from datetime import date, time
import data
from struct import unpack

from Numeric import arange, zeros, UInt8, fromstring, Float


class W18Header:
    def __init__(self, fh):

        self.name = unpack('19s', fh.read(19))[0].strip()
        self.oper = unpack('5s', fh.read(5))[0].strip()
        self.tapeno = unpack('7s', fh.read(7))[0].strip()
        self.eegno  = unpack('13s', fh.read(13))[0].strip()
        self.comment = unpack('16s', fh.read(16))[0].strip()

        self.starttime = unpack('l', fh.read(4))[0]
        self.endtime = unpack('l', fh.read(4))[0]
        self.reclength = unpack('l', fh.read(4))[0]
        self.currtime = unpack('l', fh.read(4))[0]

        self.rhythm = unpack('c', fh.read(1))[0]
        self.sigmodac = unpack('c', fh.read(1))[0]


        self.samplerate = unpack('B', fh.read(1))[0]
        self.numchannels = unpack('B', fh.read(1))[0]
        self.montagecode = unpack('B', fh.read(1))[0]
        self.dirty = unpack('B', fh.read(1))[0]
        self.online = unpack('B', fh.read(1))[0]
        self.recordlengthPnts = unpack('B', fh.read(1))[0]

        self.reserved = unpack('172s', fh.read(172))

class W18Record:
    def __init__(self, s):
        self.data = fromstring(s[:18000], UInt8)
        self.data.shape = -1, 18
        self.timestamp = unpack('8s', s[18000:18008])[0].strip()    # char [8]
        self.rec_no = unpack('L', s[18008:18012])[0]        # unsigned long
        self.ux_time = unpack('L', s[18012:18016])[0]       # unsigned long
        self.smimage = unpack('8s', s[18016:18024])[0].strip()      # char [8]
        self.ox_rec_ptr = unpack('B', s[18024])[0]          # unsigned char
        self.oxes= unpack('64B', s[18025:18089])         # unsigned char [64]
        self.rates = unpack('64B', s[18089:18153])       # unsigned char [64]
        self.ox_acq_time = unpack('64H', s[18153:18281]) # unsigned int [64] (ushort?)
        self.filstruct = unpack('150s', s[18281:18431])[0].strip()  # char [150]


def get_w18_data(fh, indmin, indmax):
    block0 = int(math.floor(indmin/1000))
    block1 = int(math.floor(indmax/1000))

    a = zeros( (indmax-indmin, 18), UInt8)
    ind=0
    for i in range(block0, block1+1):
        if i==0: pos = 256
        else: pos = i*18432
        fh.seek(pos)
        s = fh.read(18432)
        if not len(s): raise ValueError('passed the end of file')
        record = W18Record(s)

        if block0==block1:
            a = record.data[indmin-block0*1000:indmax-block0*1000]
        elif i==block0:
            N = (block0+1)*1000 - indmin 
            a[:N] = record.data[-N:]
            ind = N
        elif i==block1:
            N = indmax-i*1000
            a[ind:ind+N] = record.data[:N]
        else:
            a[ind:ind+1000] = record.data
            ind += 1000
    return a.astype(Float)
    #return a

def to_hertz(s):
    assert(s.find('Hz')>=0)
    val, hz = s.split()
    return float(val)

def parse_date(d):
    vals = d.split('/')
    assert(len(vals)==3)
    m,d,y = [int(val) for val in vals]
    return date(y,m,d)

def parse_time(t):
    vals = t.split(':')
    h = int(vals[0])
    m = int(math.floor(float(vals[1])))
    s = float(vals[1])
    seconds = int(s)
    micros = int((seconds%1)*1e6)
    return time(h, m, seconds, micros)

def int_or_none(s):
    try : return int(s)
    except ValueError: return None
    
def list_ints(s):

    return [int_or_none(val) for val in s.split(',')]

class FileFormat_BNI:

    keys = Set(['FileFormat', 'Filename', 'Comment', 'PatientName',
                'PatientId', 'PatientDob', 'Sex', 'Examiner', 'Date',
                'Time', 'Rate', 'EpochsPerSecond', 'NchanFile',
                'NchanCollected', 'UvPerBit', 'MontageGaped',
                'MontageRaw', 'DataOffset', 'eeg_number',
                'technician_name', 'last_meal', 'last_sleep',
                'patient_state', 'activations', 'sedation',
                'impressions', 'summary', 'age', 'medications',
                'diagnosis', 'interpretation', 'correlation',
                'medical_record_number', 'location',
                'referring_physician', 'technical_info', 'sleep',
                'indication', 'alertness', 'DCUvPerBit', 'NextFile'])

    converters = {
        'PatientDob' : parse_date,
        'Date':  parse_date,
        'Time':  parse_time,
        'Rate':  to_hertz,
        'EpochsPerSecond':  float,
        'NchanFile':  int,
        'NchanCollected':  int,
        'UvPerBit':  float,
        'MontageGaped':  list_ints,
        'MontageRaw':  list_ints,
        'DataOffset':  int,
        'DCUvPerBit':  float,
        }

    rgxTrode = re.compile('([a-zA-Z]+)-*(\d*)')

    def __init__(self, bnifile):
        "Parse a bni file; bnih is a bni filename"

        self.params = {}

        assert(os.path.exists(bnifile))

        self.bnipath, self.bnifname = os.path.split(bnifile)
        bnih = file(bnifile, 'r')
        seen = {}  # make sure there are no duplicate labels
        errors = []
        self.labeld = {} # a dict from cnum to label
        channeld = {} # mapping from anum->(gname, gnum)        

        seenanum = {}
        for line in bnih:
            vals = line.split('=',1)
            if len(vals)==2 and vals[0].strip() in self.keys:
                key = vals[0].strip()
                val = vals[1].strip()                
                if not len(val): continue
                #print 'converting', key
                converter =  self.converters.get(key, str)
                self.params[key] = converter(val)
                if key=='NextFile':
                    break

                
            line = line.strip()
            if len(line)==0: continue
            vals = line.split('=')
            if len(vals)==2:
                self.__dict__[vals[0].strip()] = vals[1].strip()
                continue
                
            vals = line.split(',') #113,FZ,30,70,1,60,1,MONITOR

            
            if len(vals)==8:
                anum = int(vals[0])
                if anum in seenanum.keys():
                    print 'duplicate amp num', anum
                    print '\tNew: ', line
                    print '\tOld: ', seenanum[anum]
                seenanum[anum] = line
                trode = vals[1]
                if len(trode) and trode[0]=='0':
                    trode = 'O' + trode[1:]
                self.labeld[anum] = trode
                m = self.rgxTrode.match(trode)
                if m is not None:
                    gname = m.group(1)
                    num = m.group(2)
                    if len(num): gnum = int(num)
                    elif gname[-1]=='Z': gnum = 0
                    else:
                        errors.append('Empty electrode num on line\n\t%s' % line)
                        continue
                    key = (gname, gnum)
                    
                    if seen.has_key(key):
                        if gname.find('empty')<0: # dupicate empty channels ok
                            errors.append('Duplicate label %s %d on line %s' %(gname, gnum, line))
                            continue
                    else: seen[key]=1
                    channeld[anum] = (gname, gnum) 
                else:
                    errors.append("Error parsing BNI file on line: %s\n  Electrode labeled '%s' doesn't match pattern" % (line, trode))
            elif len(channeld):
                # end of the first montage
                break
            
            if len(channeld)>=self.params['NchanFile']:
                print >> sys.stderr, 'Found more channels than indicated; bni file says %d'%self.params['NchanFile']
                break
        
        if len(errors):
            print >>sys.stderr, 'Found the following nonfatal errors'
            for msg in errors:
                print msg

        self.channels = [ (key, val[0], val[1]) for key, val in channeld.items()]
        self.channels.sort()

    def get_label(self, cnum):
        """
        Get the label for channel cnum.  cnum is the number from the
        BNI file, ie indexed from 1.  Label is the label from the BNI,
        not split into name, num.

        Return None if no label for that channel num
        """
        return self.labeld.get(cnum)

    def get_eeg(self, eegpath):

        assert(self.params.has_key('Filename'))
        #assert(len(self.channels)==self.params['NchanFile'])

        fullpath = self.params['Filename']
        amp = data.Amp()
        amp.extend(self.channels)

        if eegpath is None:
            raise RuntimeError('Could not find %s' % eegpath)

        if self.params.has_key('Date') and self.params.has_key('Time'):
            sd = self.params['Date'].strftime('%Y-%m-%d')
            st = self.params['Time'].strftime('%H:%M:%S')
            datestr = '%s %s' % (sd, st)

            basename, fname = os.path.split(eegpath)

        params = {
            'pid' : self.params.get('PatientId', 'Unknown'),
            'date' : datestr,
            'filename' : fname,     
            'description' : self.params.get('Comment', ''),  
            'channels' : self.params['NchanFile'],     
            'freq' : self.params.get('Rate'),
            'classification' : 99,
            'file_type' : 1,     
            'behavior_state' : 99, 
            }

        eeg = data.EEGFileSystem(eegpath, params)
        scale = self.params.get('UvPerBit', None)
        eeg.scale = scale
        eeg.amp = amp

        return eeg
