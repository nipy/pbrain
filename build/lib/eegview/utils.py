from __future__ import division

from __future__ import division
import re
import array
import scipy
from matplotlib.cbook import enumerate, iterable, Bunch
from matplotlib.mlab import cohere_pairs, fftsurr, hanning
#import matplotlib.numerix as nx
from math import floor, ceil
#from matplotlib.numerix import mean

#from matplotlib.numerix import zeros, ones, exp, Float, array, pi

from scipy import mean, zeros, ones, exp, Float, array, pi
from scipy import array, arange, std, rand

import scipy.signal

#import pickle

def hilbert_phaser(s):
    """
    Return the instantaneous phase of s using the hilbert transform
    """
    #f = file("hilbert_fpe.pickle", "w")
    #pickle.dump(s, f)
    #f.close()
    #print "utils:hilbert_phaser(): sig.hilbert(", s[0:10], ")"
    h = scipy.signal.hilbert(s)
    #print "utils:hilbert_phaser(): scipy.absolute(", h[0:10], ")"    
    a = scipy.absolute(h)
    #print "utils:hilbert_phaser(): scipy.angle(", h[0:10], ")"    
    phase = scipy.angle(h)
    return phase

def synchrony(s1, s2, t, winLen, freq, overlap=.1) :
    #print "utils.synchrony(s1(", len(s1), ",), s2(", len(s2), "), t(", len(t),"),", winLen, freq, overlap, ")"
    # Compute phase difference
    #print "utils.synchrony(): doing hilbert_phaser(s1)"
    p1 = hilbert_phaser(s1)
    #print "utils.synchrony(): doing hilbert_phaser(s2)"
    p2 = hilbert_phaser(s2)
    pdiff = p1 - p2

    sync = []
    time = []
    nWin = int(winLen * freq)
    nOverlap = int(overlap * freq)
    #print "utils.synchrony(): doing ", len(arange(0, len(pdiff), nWin - nOverlap)), " pdiffs"
    
    for i in arange(0, len(pdiff), nWin - nOverlap):
        sWin = pdiff[i:i + nWin]
        if len(sWin) < 3 : continue
        s = 1. / (1 + std(sWin))
        #print "utils.synchrony(): [", i, ", ", i+nWin, "]: appending value s=", s
        try : sync.append(s)
        except :
            print 'sWin:', sWin
            sys.exit()
        if t is not None :
            time.append(t[i] + winLen / 2.)

    return array(sync), array(time)

def sync_gamma(psi):
    """
    Compute the measure gamma

     gamma^2 =  <cos psi>^2 + <sin psi>^2

    where

    psi(t) = m phix(t) - n phiy(t)

    where phi is the instantaneous phase; see also phasediff

    gamma is a measure of phase synchrony and ranges from 0-1
    
    """
    from scipy import mean, cos, sin, sqrt
    return sqrt(mean(cos(psi))**2 + mean(sin(psi))**2)

def phasediff(s0, s1, filt, n=1, m=1):
    """
    Compute the n-m phase difference using the hilbert transform of s0
    and s1 after filtering with filt

    return value is a class with attributes
        s0filt : the filtered s0
        s1filt : the filtered s1
        p0     : the phase of s0
        p1     : the phase of s1
        psi    : the phase difference
        n      : n
        m      : m
    
    """
    s0filt = filt(s0)
    s1filt = filt(s1)

    p0 = hilbert_phaser(s0filt)
    p1 = hilbert_phaser(s1filt)

    return Bunch(
        s0filt = s0filt,
        s1filt = s1filt,
        p0 = p0,
        p1 = p1,
        psi = m*p0 - n*p1,
        n = n,
        m = m,
        )

def lowbutter(lpcf, lpsf, Fs, gpass=3, gstop=15):
    """
    Return a low pass butterworth filter with
    lpcf  : lowpass corner freq
    lpsf  : lowpass stop freq
    gpass : corner freq attenuation
    gstop : stop freq attenuation    

    return value is a callable function that will filter your data

    Example:
      mybutt = lowbutter(12, 15, eeg.freq)
      sfilt = mybutt(s1)

    """
    
    Nyq = Fs/2.
    wp = lpcf/Nyq
    ws = lpsf/Nyq

    ord, Wn = scipy.signal.buttord(wp, ws, gpass, gstop)
    b, a = scipy.signal.butter(ord, Wn, btype='lowpass')

    def func(x):
        return scipy.signal.lfilter(b,a,x)
    return func


def donothing_callback(*args):
    pass


def read_cohstat(fh):
    """
    Read in a cohstat file and returns N, cxy, phases where cxy, pxy
    are dictionaries and N is the number of channels

    raises a RuntimeError on failure to parse
    """
    # grok the number of channels
    
    header1 = fh.readline()
    header2 = fh.readline()
    
    cxy = {}
    phases = {}
    while 1:
        line = fh.readline().strip()

        vals = line.split()
        if len(vals)!=6:
            break

        tup = vals[0].split('-')
        if len(tup) !=2:
            raise RuntimeError, 'Bad file format on line %s' % line

        try: i = int(tup[0])
        except ValueError: continue
        try: j = int(tup[1][:-1])
        except ValueError: continue
        

        cxy[(i,j)] = array(map(float, vals[1:]))

    header2 = fh.readline()
    header3 = fh.readline()
    
    while 1:
        line = fh.readline().strip()

        vals = line.split()
        if len(vals)!=6:
            break

        tup = vals[0].split('-')
        if len(tup) !=2:
            raise RuntimeError, 'Bad file format on line %s' % line
        try: i = int(tup[0])
        except ValueError: continue
        try: j = int(tup[1][:-1])
        except ValueError: continue
        
        phases[(i,j)] = array(map(float, vals[1:]))



    return cxy, phases


def all_pairs_ij(N):
    "Return a list of all uniq i,j tuples for cohstat"
    ij = []
    for i in range(N):
        for j in range(i+1, N):
            ij.append((i,j))
    return ij

def all_pairs_eoi(eoi):
    "Return a list of all uniq e1,e2 tuples for the eoi"

    return [ (eoi[i], eoi[j]) for i,j in all_pairs_ij(len(eoi))]

def ij_across_eois(eoi1, eoi2, amp):
    """
    gets ij pairs for across eois (useful for in and out of focus
    analysis).  takes three arguments eoi1, eoi2, and amp. as long as
    you keep track of which eoi is which when you enter them in,
    everything should be peachy

    Note, you really would rather be using electrode_pairs_across_eois
    """
    
    ind1=eoi1.to_data_indices(amp)
    ind2=eoi2.to_data_indices(amp)
    seen={}
    if len(ind1)<len(ind2):
        for i in ind1:
	    seen[i]=1
        ind2uniq=[j for j in ind2 if not seen.has_key(j)]
        indeoi1=ind1
        indeoi2=ind2uniq
    else:
	for i in ind2:
	    seen[i]=1
        ind1uniq=[j for j in ind1 if not seen.has_key(j)]
        indeoi1=ind1uniq
        indeoi2=ind2
    ij = []
    for i in indeoi1:
	 for j in indeoi2:
	    ij.append((i,j))
    return ij


def electrode_pairs_across_eois(eoia, eoib, amp):
    """
    gets (e1,e2) pairs for across eois (useful for in and out of focus
    analysis).  takes three arguments eoia, eoib, and amp.
    """

    # if eoia contains eoib you can get in trouble, because eoi2u
    # would be empty in the code below; just ask Sinem

    if eoia==eoib: return []
    if len(eoia)==0: return []
    if len(eoib)==0: return []

    def smaller_one_first(eoi1, eoi2):
        seen = {}
        for key in eoi1: seen[key] = 1
        # eoi2u are the electrodes in eoi2 that are not in eoi1
        eoi2u = [ e for e in eoi2 if not seen.has_key(e)]
        return [ (e1, e2) for e1 in eoi1 for e2 in eoi2u]

    if len(eoia) < len(eoib): return smaller_one_first(eoia, eoib)
    else: return smaller_one_first(eoib, eoia)
    

def cohere_dict_to_array(m, keys):
    """
    Convert a cohere dict 'm' (as returned by cohere_bands, or
    cohere_pairs) to an array for statistical processing
    """
    # get a representative band
    band = m[keys[0]]
    if iterable(band):
        if len(band)>1:
            # XXX: will not work with Numeric or numarray, but only with numpy. how to do this?!?
            a = zeros( (len(keys),len(band)), band.dtype)
        else:
            a = zeros( (len(keys),), band.dtype)
    else: 
        a = zeros( (len(keys),), Float)
        
    for count, key in enumerate(keys):
        a[count] = m[key]
    return a

def cohere_array_to_dict(a, keys):
    """
    Convert a cohere array (as created by cohere_dict_to_array) back
    to a dict
    """
    
    d = {}

    count = 0
    for rowNum in range(len(keys)):
        d[keys[rowNum]] = a[rowNum]
    return d


def cohere_bands(cxy, phase, freqs, keys,
                 bands = ( (1,4), (4,8), (8,12), (12,30), (30,55) ),
                 progressCallback=donothing_callback):

    """
    
    Summarize the output of cohere_pairs_eeg by bands.  cxy and phase
    are a dictionary from electrode pair keys to Numeric arrays of
    coherence and phases for that pair.  keys is a list of (e1,e2)
    tuples.

    The bands are

    delta = 1-4 Hz
    theta = 4-8
    alpha = 8-12
    beta  = 12-30
    gamma = 30-55

    Return value is cxyAvg, phaseAvg

    """
    #convert the cxy and phase structs to a matrix for averaging
    

    df = freqs[1]-freqs[0]
    ind = []

    for (fmin, fmax) in bands:
        inds = max([int(floor(fmin/df)), 0     ])
        inde = min([int(ceil (fmax/df)), len(freqs)])
        ind.append( (inds, inde))
        

    cxyAvg = {}
    phaseAvg = {}

    # note I am doing this element wise as a dict rather than array
    # wise as a matrix to conserve memory.  dimensions of matrix are
    # len(ij)*len(freqs), which for NFFT=2048 and 64 electrodes
    # pairwise is 2016*2048 coherences and phases.  8 million floats.

    Nbands = len(bands)
    count = 0
    Nkeys = len(keys)
    count =0
    for key in keys:
        count +=1
        if count%20==0:
            progressCallback(count/Nkeys,  'Averaging over bands')
        thisCxy = cxy[key]
        thisPhase = phase[key]
        ac = zeros( (Nbands,), thisCxy.dtype)
        ap = zeros( (Nbands,), thisPhase.dtype)
        count = 0
        for inds, inde in ind:
            if inds==inde:
                ac[count]=thisCxy[inds]
                ap[count]=thisPhase[inds]
            else:
                #print key, inds, inde, thisCxy.shape, ac.shape
                ac[count] = mean(thisCxy[inds:inde])
                ap[count] = mean(thisPhase[inds:inde])
            count += 1
        cxyAvg[key] = ac
        phaseAvg[key] = ap
    return cxyAvg, phaseAvg




def power_bands(pxx, freqs,
                bands = ( (1,4), (4,8), (8,12), (12,30), (30,55) ),
                progressCallback=donothing_callback):

    """
    
    Summarize the output of cohere_pairs_eeg with pxx returned by
    bands.  pxx is a dictionary from electrodes to Numeric arrays of
    power for that trode.  
    tuples.

    The bands are

    delta = 1-4 Hz
    theta = 4-8
    alpha = 8-12
    beta  = 12-30
    gamma = 30-55

    Return value is pxxAvg

    """
    #convert the cxy and phase structs to a matrix for averaging
    

    df = freqs[1]-freqs[0]
    ind = []

    for (fmin, fmax) in bands:
        inds = max([int(floor(fmin/df)), 0     ])
        inde = min([int(ceil (fmax/df)), len(freqs)])
        ind.append( (inds, inde))
        

    pxxAvg = {}

    # note I am doing this element wise as a dict rather than array
    # wise as a matrix to conserve memory.  dimensions of matrix are
    # len(ij)*len(freqs), which for NFFT=2048 and 64 electrodes
    # pairwise is 2016*2048 coherences and phases.  8 million floats.

    Nbands = len(bands)
    count = 0
    keys = pxx.keys()
    Nkeys = len(keys)
    count =0
    for key in keys:
        count +=1
        if count%20==0:
            progressCallback(count/Nkeys,  'Averaging over bands')
        thisPxx = pxx[key]
        avg = zeros( (Nbands,), thisPxx.dtype)

        count = 0
        for inds, inde in ind:
            if inds==inde:
                avg[count]=thisPxx[inds]

            else:
                avg[count] = mean(thisPxx[inds:inde])

            count += 1
        pxxAvg[key] = avg

    return pxxAvg


def export_cohstat_xyz(XYZ):
    """
    XYZ is a 64 x 3 array of floats.  Return a string that can be
    written to a file cohstat can read.  Note the data should be
    rotated so that they are in the view plane
    """
    if len(XYZ) != 64:
        raise ValueError, 'Length of XYZ must be 64!'
    lines = [' 64']
    for row in XYZ:
        lines.append(', '.join(['%d'%val for val in row]))
    return '\r\n'.join(lines) + '\r\n'
        
    
def export_to_cohstat(cxyBands, phaseBands, keys):
    """
export_to_cohstat

This function takes the coherence between pairs of electrodes in a
grid as determined by cohere_bands (which processes the output from
cohere_pairs and puts the data into a string format that can be loaded
CohStat for visual analysis.

export_to_cohstat returns the average coherence and phase within bands
defined by cohere_bands, here defined as follows:

delta = 1-4 Hz
theta = 4-8
alpha = 8-12
beta  = 12-30
gamma = 30-55


keys are an ordered list of keys into the cxy and phase dictionaries.
Eg, if keys is from cohere_pairs_eeg, then it is a list of (e1,e2)
tuples

export_to_cohstat then creates a string (with all appropriate headers)
that can be written to a file

The output string is in the format:
Average coherence within selected bands
         Delta      Theta      Alpha        Beta      gamma
i-j:     coh[0]     coh[1]     coh[2]       coh[3]    coh[4]

Average phase within selected bands
         Delta      Theta      Alpha        Beta      gamma
i-j:     pha[0]     pha[1]     pha[2]       pha[3]    pha[4]        



Authors: Scott Simon (ssimon1@uchicago.edu) and John Hunter, 


Please refer questions to John Hunter.  Feel free to call home and
call late.  Ask for "Kelly."

    """

    lines = ["""Average coherence within selected bands:\r
                            Delta      Theta      Alpha       Beta   lowgamma \r
"""]
    count=0
    #Format the coherence data for each pair

    ij = all_pairs_ij(64)
    if len(keys)!=len(ij):
        raise RuntimeError, 'Cohstat can only handle 64 channels, talk to Leo'

    count = 0
    for i, j in ij:
        thisCxy = cxyBands[keys[count]]
        s = '%d-%d:'%(i+1,j+1)
        s = s.rjust(22)
        lines.append(s + '      %1.3f      %1.3f      %1.3f      %1.3f      %1.3f \r\n' %\
                      (thisCxy[0], thisCxy[1],thisCxy[2],thisCxy[3], thisCxy[4]))
        count +=1

    #Create the phase header of the file
    lines.append("""
Phase of average coherency within selected bands (degrees):\r
                            Delta      Theta      Alpha       Beta   lowgamma \r
""")

    count = 0
    #Format the phase data for each pair
    for i, j in ij:
        thisPhase = 180.0/pi*array(phaseBands[keys[count]])
        s = '%d-%d:'%(i+1,j+1)
        s = s.rjust(22)
        lines.append(s + '% 11.3f% 11.3f% 11.3f% 11.3f% 11.3f \r\n' %\
                      (thisPhase[0], thisPhase[1],thisPhase[2],thisPhase[3], thisPhase[4]))
        count+=1
    lines.append("""
""")
    return ''.join(lines)


def convert_ebersole(filein, fileout):
    """
    convert_ebersole

    This function converts a float ASCI eeg record into a binary eeg
    record.

    This function takes two file names as inputs.  The first, filein,
    is the name of the file being converted.  The second, fileout, is
    the name of the file that will be created.

    The output is a file with the voltage from each individual channel
    given a column, and each row representing another sampling point.
    In the output file, this floating point data is represented in
    binary.

    Author: Scott Simon, ssimon1@uchicago.edu
    """

    from array import array

    count = 0
    fi = open(filein, 'r')
    for line in fi.xreadlines():
        if line[0] == '"': continue
        elif len(line.strip())==0:
            count += 1
            if count == 2: break
 	
    fo = open(fileout, 'wb')
    for line in fi.xreadlines():
        a = array('f', map(float, line.split(',')[1:]))
        fo.write(a.tostring())


def eoi_for_matlab(eoi, grd, fileout):
    """
    eoi_for_matlab

    This function takes the xyz for the electrodes of interest,
    assigned from the .grd file by eoi_to_xyz, and formats these
    values in a way that matlab can read.

    The input is an .eoi and .grd file, and an output file name.  The
    output is a file in the format

    [...
    x y z;...
    x y z;...
    ];

    Author: Scott Simon, ssimon1@uchicago.edu
    """

    fo = open(fileout, 'w')
    fo.write('XYZ = [...\n')
    t = eoi_to_xyz(eoi, grd)
    for l in t:
        fo.write('\t%1.8f %1.8f %1.8f;...\n' % tuple(l))
    fo.write('];')
    
def eeg_grand_mean(X):
    """
    X is a numSamples by numChannels numeric array.  Return the grand
    mean of X (For each element of X, subtract the mean of the row
    for which it occurs)
    """
    return mean(X,1)

def filter_grand_mean(X):
    """
    X is a numSamples by numChannels numeric array.  Return X with
    the grand mean removed
    """
    X = array(X, Float)
    gm =  eeg_grand_mean(X)
    print "utils.filter_grand_mean(): type(gm)=", gm.dtype

    gm.shape = X.shape[0],
    numRows, numCols = X.shape
    for i in range(numCols):
        X[:,i] = X[:,i] -  gm

    print "utils.filter_grand_mean(): return X of type ", X.dtype
    return X


def remove_channel_means(X):
    "remove the mean from each channel.  X is a numSamples x numChannels array"
    mu = mean(X,0)
    mu.shape = 1,X.shape[1]
    return X - mu




    

def get_exp_prediction(pars, x):
    """
    pars is an a, alpha, k0 tuple of parameters for the exponential function
    y = a*exp(alpha*t) + k

    Evaluate this function at x and return y

    Eg, if x are distances, this would return the predicted coherence
    as a function of distance assuming an exponential relationship See
    get_best_exp_params for the function to get the best exponential
    params for a distance array x and a coherence array.
    """
    a, alpha, k = pars
    #print a, alpha, k
    return a*exp(alpha*x) + k 


def get_best_exp_params(x, y, guess=(1.0, -.5, 0.0)): 
    """
    Given a distance array x and an equal shaped array of coherences y
    and an initial guess for the parameters of get_exp_prediction,
    where pars is an a, alpha, k0 tuple, return the best fit
    parameters as an a, alpha, k0 tuple

    Eg,
    best = get_best_exp_params(delta, coh, guess)
    """
    
    def errfunc(pars): 
        return y - get_exp_prediction(pars, x)  #return the error 

    J = zeros( (3,len(x)), Float)  # init the Jacobian only once 
    ddk = -ones((len(x),), Float)  # d/dk indep of k 
    def deriv_errfunc(pars): 
        'The Jacobian of the errfunc is -Jacobian of the func' 

        a, alpha, k = pars 

        J[0,:] = -exp(alpha*x)  #d/da 
        J[1,:] = -x*a*exp(alpha*x) #d/alpha 
        J[2,:] = ddk 
        return J 

    from scipy.optimize import leastsq
    ret = leastsq(errfunc, guess, 
                  full_output=1, 
                  Dfun=deriv_errfunc, 
                  col_deriv=1) 

    if len(ret)==4:
        best, info, ier, mesg = ret
    elif len(ret)==5:
        best, info, ier, mesg, cov_x = ret

    if ier != 1: return None 
    return best 



def cohere_pairs_eeg( eeg, eoiPairs=None, indMin=0, indMax=None,
                      data=None, returnPxx=False, **kwargs):

    """
    Cxy, Phase, freqs = cohere_pairs_eeg(  ...)
    
    Compute the coherence for all pairs in the eoi.  eeg is a
    EEG instance.

    eoiPairs is a list of electrode tuples; if none, use all.  Each
    tuple is a pair of electrodes, eg,

      eoiPairs = [ ( ('MT',7), ('MT',8) ),
                     ( ('MT',7), ('MT',9) ),
                     ....
                     ]

    indMin, indmax if provided, give the sample number indices into
    eeg.data to do the coherence over (default all)

    if data is not None, use data rather than eeg.data to compute
    coherence
    
    The other function arguments, except for 'preferSpeedOverMemory'
    (see below), are explained in the help string of 'psd'.

    Return value is a tuple (Cxy, Phase, freqs).

      Cxy -- a dictionary of electrode tuples -> coherence vector for that
        pair.  
      
      Phase -- a dictionary of phases of the cross spectral density at
        each frequency for each pair.  keys are (e1,e2).

      freqs -- a vector of frequencies, equal in length to either the
        coherence or phase vectors for any electrode key.  Eg, to make
        a coherence
        
        Bode plot:
          e1 = ('MT', 7)
          e2 = ('MT', 8)
          subplot(211)
          plot( freqs, Cxy[(e1,e2)])
          subplot(212)
          plot( freqs, Phase[(e1,e2)])
      
    For a large number of pairs, cohere_pairs can be much more
    efficient than just calling cohere for each pair, because it
    caches most of the intensive computations.  If N is the number of
    pairs, this function is O(N) for most of the heavy lifting,
    whereas calling cohere for each pair is O(N^2).  However, because
    of the caching, it is also more memory intensive, making 2
    additional complex arrays with approximately the same number of
    elements as X.

    See mlab cohere_pairs for optional kwargs
    
    See test/cohere_pairs_test.py in the src tree for an example
    script that shows that this cohere_pairs and cohere give the same
    results for a given pair.

    """

    amp = eeg.get_amp()
    if eoiPairs is None:
        eoiPairs = all_pairs_eoi( amp.to_eoi() )


    m = amp.get_electrode_to_indices_dict()
    ij = [ (m[e1], m[e2]) for e1, e2 in eoiPairs]
    ij.sort()
        
    #print len(ij), len(eoiPairs)

    if data is None: data = eeg.data

    print "cohere_pairs_eeg: data.shape is ", data.shape
    
    if indMax is None: indMax = data.shape[0]
    X = data[indMin:indMax]
    if returnPxx:
        try:
            Cxy, Phase, freqs, Pxx = cohere_pairs(
                X, ij, Fs=eeg.freq, returnPxx=True, **kwargs)
        except OverflowError, overflowerror:
            print "cohere_pairs_eeg(): caught overflow error!! bailing: ", overflowerror
            
    else:
        Cxy, Phase, freqs = cohere_pairs(
            X, ij, Fs=eeg.freq, **kwargs)

    seen = {}
    keys = Cxy.keys()
    keys.sort()

    assert(len(ij)==len(eoiPairs))

    for keyIJ, keyEOI in zip(ij, eoiPairs):
        Cxy[keyEOI] = Cxy[keyIJ]
        del Cxy[keyIJ]
        Phase[keyEOI] = Phase[keyIJ]
        del Phase[keyIJ]

        i,j = keyIJ
        e1, e2 = keyEOI
        seen[i] = e1
        seen[j] = e2

    if returnPxx:
        for i, ei in seen.items():
            Pxx[ei] = Pxx[i]
            del Pxx[i]

    if returnPxx:
        return Cxy, Phase, freqs, Pxx
    else:
        return Cxy, Phase, freqs

def window_hanning(x):
    "return x times the hanning window of len(x)"
    sigma = std(x)
    win =  hanning(len(x))*x
    return win*(sigma/std(win))

def bandpass(lpsf, lpcf, hpcf, hpsf, Fs, gpass=3, gstop=20):
    "return a butterworth bandpass filter"
    Nyq = Fs/2.
    wp = [lpcf/Nyq, hpcf/Nyq]
    ws = [lpsf/Nyq, hpsf/Nyq]
    ord, Wn = scipy.signal.buttord(wp, ws, gpass, gstop)
    b,a = scipy.signal.butter(ord, Wn, btype='bandpass') # pun intended
    def func(x):
        return scipy.signal.lfilter(b,a,x)

    return func

def gen_surrogate_data(eeg, tmin, tmax, eoi, filters, numSurrs) :
    surrData = {}

    # Get data
    t, data = eeg.get_data(tmin, tmax)

    # Extract random pairs from the data
#    randInds = (nx.mlab.rand(numSurrs, 2) * len(eoi)).astype(nx.Int)
    randInds = (rand(numSurrs, 2) * len(eoi)).astype(Int)
    e2i = eeg.get_amp().get_electrode_to_indices_dict()
    for i, pair in enumerate(randInds) :
        print 'Computing surrogate %d of %d' % (i, numSurrs)

        # Get indices into data
        ie1, ie2 = pair
        i1 = e2i[eoi[ie1]]
        i2 = e2i[eoi[ie2]]

        # Generate surrogate data
# XXX
        surr1 = fftsurr(data[:,i1], window=window_hanning)
        surr2 = fftsurr(data[:,i2], window=window_hanning)
#        surr1 = fftsurr(data[:,i1])
#        surr2 = fftsurr(data[:,i2])

        # Generate filtered surrogate data
        for j, tup in enumerate(filters.items()) :
            band, info = tup
            winLen, filter = info

            fsurr1 = filter(surr1)
            fsurr2 = filter(surr2)

            surrData[i, j, band] = (fsurr1, fsurr2)

    return surrData
