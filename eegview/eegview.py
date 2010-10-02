# TODO: clear x,y lim and ticks when you change eegs
# TODO: fix vsteps for different numbers of electrodes
# font sizes are different on ylabels
from __future__ import division
import sys, os, copy, traceback
import distutils.sysconfig


import pygtk
pygtk.require("2.0")
import gtk
from gtk import gdk


from Numeric import fromstring, arange, Int16, Float, log10
from numpy import min as numpymin, max as numpymax, mean
#using numpy instead of Mlab. the difference is that min and max drill through dimensions, and mlab min and max don't. so mlab's min(min( or max(max( is #replaced by numpymin or numpymax respectively, while the other min and max are still handled by built in python functions.
from matplotlib.cbook import exception_to_str #took out enumerate
from pbrainlib.gtkutils import str2num_or_err, simple_msg, error_msg, \
     not_implemented, yes_or_no, FileManager, select_name, get_num_range

from data import EEGWeb, EEGFileSystem, EOI, Amp, Grids
from file_formats import FileFormat_BNI, W18Header, FileFormat_BNI

from dialogs import Dialog_Preferences, Dialog_SelectElectrodes,\
     Dialog_CohstatExport, Dialog_SaveEOI, Dialog_EEGParams, AutoPlayDialog,\
     SpecProps
import servers
from borgs import Shared
from events import Observer
from shared import fmanager, eegviewrc
from gladewrapper import PrefixWrapper
from utils import filter_grand_mean

from matplotlib import rcParams

from matplotlib.backends.backend_gtkagg import FigureCanvasGTKAgg as FigureCanvas
import matplotlib.cm as cm
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.transforms import BboxTransform, Bbox, ScaledTranslation #in all, removed unit_bbox, Value, Point, and
#replaced get_bbox_transform with BboxTransform, added ScaledTranslation

from scipy import arange, sin, pi, zeros, ones, reshape, \
     greater_equal, transpose, array, arange, resize, \
     absolute, nonzero

from scipy.signal import buttord, butter, lfilter

from mpl_windows import ChannelWin, AcorrWin, HistogramWin, SpecWin


major, minor1, minor2, s, tmp = sys.version_info
if major<2 or (major==2 and minor1<3):
    True = 1
    False = 0



def load_w18(fullpath):
    assert(os.path.exists(fullpath))
    basename, filename = os.path.split(fullpath)
    fh = file(fullpath, 'rb')
         
    header = W18Header(fh)
    params = {
        'filename'        : filename,
        'date'            : header.currtime,
        'description'     : '',
        'channels'        : 18,
        'freq'            : 200,
        'classification'  : 99,
        'file_type'       : W18,
        'behavior_state'  : 99,
        }

    eeg = EEGFileSystem(fullpath, params)
    return eeg


def load_bmsi(bnipath):

    bni = FileFormat_BNI(bnipath)
    basename, ext = os.path.splitext(bnipath)
    
    if os.path.exists(basename):    
        fullpath = basename
    elif os.path.exists(basename + '.eeg'):
        fullpath = basename + '.eeg'
    else:
        fullpath = fmanager.get_filename(
            title='Select EEG File accompanying this BNI file')

    eeg = bni.get_eeg(fullpath)
    return eeg



extmap = { '.w18' : load_w18,
           '.bni' : load_bmsi,
           }

class EEGNavBar(gtk.Toolbar, Observer):
    
    def __init__(self, eegplot=None, win=None):
        """
        eegplot is the EEGPlot instance that the toolboar controls

        win, if not None, is the gtk.Window the Figure is embedded in
        
        """
        gtk.Toolbar.__init__(self)
        Observer.__init__(self)
        self.win = win
        self.eegplot = eegplot
        iconSize = gtk.ICON_SIZE_SMALL_TOOLBAR
        self.set_border_width(5)
        self.set_style(gtk.TOOLBAR_ICONS)


        iconw = gtk.Image()
        iconw.set_from_stock(gtk.STOCK_GOTO_FIRST, iconSize)
        self.bLeftPage = self.append_item(
            'Left page',
            'Move back one page',
            'private',
            iconw,
            self.panx) #took out deprecated user data
        self.bLeftPage.connect("scroll_event", self.panx)

        iconw = gtk.Image()
        iconw.set_from_stock(gtk.STOCK_GO_BACK, iconSize)
        self.bLeft = self.append_item(
            'Left',
            'Move back in time',
            'Private',
            iconw,
            self.panx,
            -1)

        self.bLeft.connect("scroll_event", self.panx)

        iconw = gtk.Image()
        iconw.set_from_stock(gtk.STOCK_GO_FORWARD, iconSize)
        self.bRight = self.append_item(
            'Right',
            'Move forward in time',
            'Private',
            iconw,
            self.panx,
            1)
        self.bRight.connect("scroll_event", self.panx)

        iconw = gtk.Image()
        iconw.set_from_stock(gtk.STOCK_GOTO_LAST, iconSize)
        self.bRightPage = self.append_item(
            'Right page',
            'Move forward one page',
            'Private',
            iconw,
            self.panx,
            10)
        self.bRight.connect("scroll_event", self.panx)

        self.append_space()

        iconw = gtk.Image()
        iconw.set_from_stock(gtk.STOCK_ZOOM_IN, iconSize)
        self.bZoomInX = self.append_item(
            'Shrink the time axis',
            'Shrink the time axis',
            'Private',
            iconw,
            self.zoomx,
            1)
        self.bZoomInX.connect("scroll_event", self.zoomx)

        iconw = gtk.Image()
        iconw.set_from_stock(gtk.STOCK_ZOOM_OUT, iconSize)
        self.bZoomOutX = self.append_item(
            'Expand the time axis',
            'Expand the time axis',
            'Private',
            iconw,
            self.zoomx,
            0)
        self.bZoomOutX.connect("scroll_event", self.zoomx)

        self.append_space()
        
        iconw = gtk.Image()
        iconw.set_from_stock(gtk.STOCK_GO_UP, iconSize)
        self.bUp = self.append_item(
            'Up',
            'Increase the voltage gain',
            'Private',
            iconw,
            self.zoomy,
            1)
        self.bUp.connect("scroll_event", self.zoomy)


        iconw = gtk.Image()
        iconw.set_from_stock(gtk.STOCK_GO_DOWN, iconSize)
        self.bDown = self.append_item(
            'Down',
            'Decrease the voltage gain',
            'Private',
            iconw,
            self.zoomy,
            0)
        self.bDown.connect("scroll_event", self.zoomy)
        self.append_space()

        iconw = gtk.Image()
        iconw.set_from_stock(gtk.STOCK_REDO, iconSize)
        self.bJump = self.append_item(
            'Enter range',
            'Specify time range',
            'Private',
            iconw,
            self.specify_range)

        iconw = gtk.Image()
        iconw.set_from_stock(gtk.STOCK_JUMP_TO, iconSize)
        self.bAuto = self.append_item(
            'Autoplay',
            'Automatically page the EEG',
            'Private',
            iconw,
            self.auto_play)


        iconw = gtk.Image()
        iconw.set_from_stock(gtk.STOCK_SAVE, iconSize)
        self.bSave = self.append_item(
            'Save',
            'Save the figure',
            'Private',
            iconw,
            self.save_figure)

        self.append_space()

        def toggled(button):
            self.broadcast(Observer.GMTOGGLED, button)

        self.buttonGM = gtk.CheckButton('GM')
        self.buttonGM.show()
        self.buttonGM.connect('toggled', toggled)
        self.buttonGM.set_active(True)
        self.append_widget(
            self.buttonGM, 'Remove grand mean from data if checked', '')
        
        
    def auto_play(self, *args):

        tmin, tmax = self.eegplot.get_time_lim()
        twidth = tmax-tmin

        dlg = AutoPlayDialog(0, self.eegplot.eeg.get_tmax(), twidth)
        dlg.show()
            
    def specify_range(self, *args):

        response = get_num_range()
        if response is None: return

        tmin, tmax = response
        
        self.eegplot.set_time_lim(tmin, tmax, updateData=True)
        self.eegplot.draw()

    def save_figure(self, button):
                
        def print_ok(button):
            fname = fs.get_filename()
            fmanager.set_lastdir(fname)
            fs.destroy()
            try: self.eegplot.canvas.print_figure(fname)
            except IOError, msg:                
                err = '\n'.join(map(str, msg))
                msg = 'Failed to save %s: Error msg was\n\n%s' % (
                    fname, err)
                try: parent = Shared.windowMain.widget
                except AttributeError: parent = None
                simple_msg(msg, title='Error', parent=parent)

        fs = gtk.FileSelection(title='Save the figure')
        if self.win is not None:
            fs.set_transient_for(self.win)
        fs.set_filename(fmanager.get_lastdir() + os.sep)

        fs.ok_button.connect("clicked", print_ok)
        fs.cancel_button.connect("clicked", lambda b: fs.destroy())
        fs.show()



    def set_eegplot(self, eegplot):
        self.eegplot = eegplot
        
    def panx(self, button, arg):

        if self.eegplot is None: return 
        try: arg.direction
        except AttributeError: right = arg
        else:
            if arg.direction == gdk.SCROLL_UP: right=1
            else: right=0

        self.eegplot.pan_time(right)
        self.eegplot.draw()
        return True

    def zoomx(self, button, arg):
        if self.eegplot is None: return 
        try: arg.direction
        except AttributeError: direction = arg
        else:            
            if arg.direction == gdk.SCROLL_UP: direction=1
            else: direction=0

        self.eegplot.change_time_gain(direction)
        self.eegplot.draw()
        return True

    def zoomy(self, button, arg):
        if self.eegplot is None: return 
        try: arg.direction
        except AttributeError: direction = arg
        else:
            if arg.direction == gdk.SCROLL_UP: direction=1
            else: direction=0

        self.eegplot.change_volt_gain(direction)
        self.eegplot.draw()
        return True




class EEGPlot(Observer):
    timeSets = ((1.,.1), (2.,.2), (5.,.5), (10.,1.), (20.,2.),
                (50.,5.), (100., 10.), (200., 20.))

    voltSets = (.1, .2, .5,  .75, 1., 2., 5., 7.5,
                10., 20., 50., 75., 100., 200., 500., 750,
                1000., 2000., 5000., 7500.,
                10000., 20000., 50000., 75000., 150000., 300000.)

    colorOrder = ('b','k','g','c','m')
    def __init__(self, eeg, canvas):
        Observer.__init__(self)
        eeg.load_data()
        self.canvas = canvas #canvas is passed in by init - from the gtk MainWindow
        self.figure = canvas.figure
        self.axes = self.figure.axes[0]
        self.axes.cla()
        self.eeg = eeg
        self.cnumDict = self.eeg.get_amp().get_channel_num_dict()

        amp = eeg.get_amp()
        eoi = amp.to_eoi()

        self.colord = {}
        colorInd = 0

        for gname, gnum in eoi:
            gname = gname.lower()
            color = self.colord.get(gname.lower())
            if color is None:
                color = self.colorOrder[colorInd % len(self.colorOrder)]
                self.colord[gname] = color
                colorInd += 1
            
        self._selected = eoi[0]
        self.set_eoi(eoi)
        

        self.timeInd = 3
        self.voltInd = 18
        self.maxLabels = 36



        self.filterGM = Shared.windowMain.toolbar.buttonGM.get_active()
        self._selectedCache = None, None

        


    def get_color(self, trode):
        gname, gnum = trode
        gname = gname.lower()
        return self.colord[gname]

    def recieve(self, event, *args):

        if event in (Observer.SET_TIME_LIM,):
            tmin, tmax = args
            self.set_time_lim(tmin, tmax, broadcast=False)
            self.draw()

        elif event==Observer.SAVE_FRAME:
            fname = args[0] + '.png'
            self.canvas.print_figure(fname)
            basedir, filepart = os.path.split(fname)
            listfile = os.path.join(basedir, 'eegplot.vfl')
            try:  file(listfile, 'a').write('%s\n'%(filepart))
            except IOError:
                error_msg('Could not write list file %s' % listfile)
                return
            
            try:
                Shared.windowMain.update_status_bar(
                    'Saved frame: %s' % fname)
            except AttributeError: pass
        elif event == Observer.SELECT_CHANNEL:
            trode = args[0]
            gname, gnum = trode
            self.set_selected((gname, gnum))
        elif event == Observer.GMTOGGLED:
            button = args[0]
            self.filterGM = button.get_active()
            tmin, tmax = self.get_time_lim()
            t, data, freq = self.filter(tmin, tmax)        

            for ind, line in zip(self.indices, self.lines):
                line.set_data(t, data[:,ind])
            self.draw()

            
    def draw(self):
        self.canvas.draw()

    def get_selected(self, filtergm=False):
        'return t, data[ind], trode'
        tmin, tmax = self.get_time_lim()

        key = (tmin, tmax, self._selected, filtergm)

        keycache, retcache = self._selectedCache
        if keycache==key: return retcache
        
        t, data = self.eeg.get_data(tmin, tmax)
        data = -data

        if filtergm:
            data = filter_grand_mean(data)

        ind = self.eoiIndDict[self._selected]
        
        ret = t, data[:,self.indices[ind]], self._selected
        self._selectedCache = key, ret
        return ret
        
        
    def get_eoi(self):
        return self.eoi

    def get_eoi(self):
        return self.eoi

    def set_eoi(self, eoi):
        try:
            self.indices = eoi.to_data_indices(self.eeg.get_amp())
        except KeyError:
            
            msg = exception_to_str('Could not get amplifier indices for EOI')
            try: parent = Shared.windowMain.widget
            except AttributeError: parent = None
            error_msg(msg, title='Error', parent=parent)
            return 0



        self.eoi = eoi



        self.eoiIndDict = dict([ (trode, i) for i, trode in enumerate(self.eoi)])


        if not self.eoiIndDict.has_key(self._selected):
            self._selected = self.eoi[0]
            
        return True
        
    def get_eeg(self):
        return self.eeg
    
    def filter(self, tmin, tmax, lpcf=40, lpsf=55, hpcf=None, hpsf=None):


        try: t, data = self.eeg.get_data(tmin, tmax)
        except KeyError, msg:
            msg = exception_to_str('Could not get data')
            error_msg(exception_to_str('Could not get data'))
            return None

        data = -data  # invert neg up

        if self.filterGM:
            data = filter_grand_mean(data)

        data +=  self.eeg.get_baseline()

        Nyq = self.eeg.freq/2
        Rp, Rs = 2, 20
        
        #Wp = [0.5/Nyq, lpcf/Nyq]
        #Ws = [0.1/Nyq, lpsf/Nyq]
        Wp = lpcf/Nyq
        Ws = lpsf/Nyq
        [n,Wn] = buttord(Wp,Ws,Rp,Rs)
        [b,a] = butter(n,Wn)

        data = transpose( lfilter(b,a,transpose(data)))

        decimateFactor = int(Nyq/lpcf)
        decfreq = self.eeg.freq/decimateFactor
        self.decfreq = decfreq
        return t[::decimateFactor], data[::decimateFactor], decfreq
    
    def plot(self):
        self.axes.cla()
        t, data, freq = self.filter(0, 10)


        dt = 1/freq

        self.lines = []

        skip = max(1, len(self.indices)//self.maxLabels) 
        count = 0
        amp = self.eeg.get_amp()
        labels = []
        locs = []


        maxo = 0.975
        mino = 0.025

        N = len(self.indices)
        offsets = 1.0-((maxo-mino)/N*arange(N) + mino)

        
        vset = self.voltSets[self.voltInd]
#updated by removing Point and Value methods and simply passing four points to Bbox() this may be a bad idea... I tried passing them to Bbox.set_points() but this method seems to be either not working or badly documented.
#also, viewLim is deprecated from what I can tell, so I'll try to use axes.get_xlim
	viewLimX=self.axes.get_xlim() #this returns a list of min and max x points, which is what we want to pass below
        boxin = Bbox(
            [[viewLimX[0], -vset], #replaced self.axes.viewLim.ll().x() with viewLimX
            [viewLimX[1], vset]])

	#does this work? yes! there actually is a bbox living in axes, for whatever reason, and this method returns all four points as an array of the form [[x0,y0],[x1,y1]]. the bbox that we rebuild below is (hopefully!) taking the x values of the two points.
	axesBboxCoords = self.axes.bbox.get_points()
        boxout = Bbox(
            [[axesBboxCoords[0][0], -72], #see comment above: I replaced self.axes.bbox.ll().x() with axesBboxCoords[0][0]
            [axesBboxCoords[1][0], 72]])


        transOffset = BboxTransform(
            Bbox.unit(), # ([[0,0], [1,1]]), #replaced unit_bbox with unit()
            Bbox(  [[0, axesBboxCoords[0][1]],
                   [1, axesBboxCoords[1][1]]]
                  ))
        
        pairs = zip(self.indices, offsets)

        labeld = amp.get_dataind_dict()

	for ind, offset in pairs:

   	    trode = labeld[ind]

            color = self.get_color(trode)
            if self._selected==trode: color='r'
            trans = BboxTransform(boxin, boxout)

            thisLine = Line2D(t, data[:,ind],
                              color=color,
                              linewidth=0.75,
                              linestyle='-',
			      clip_on=False,
                              )
            thisLine.set_transform(trans)
            #thisLine.set_data_clipping(False) #updated set_data_clipping to clip_on as a kwarg
            #set_offset is way deprecated. I'm going to use a tip from the newer transforms_tutorial on the matplotlib.sourceforge page.
	    #the basic idea is to use ScaledTranslation, which creates an offset that can than be added to the original trans.
	    newtrans = ScaledTranslation(0,offset,transOffset)
	    trans = trans + newtrans
	    #trans.set_offset((0, offset), transOffset)
	    #note: I'm still not even clear how/if trans even gets used again
            thisLine.set_lod(on=1)
            self.lines.append(thisLine)
            self.axes.add_line(thisLine)

            if count % skip == 0:                
                labels.append('%s%d' % trode)
                locs.append(offset)
            count += 1


        self.set_time_lim(0, updateData=False)

        self.axes.set_yticks(locs)            

        labels = self.axes.set_yticklabels(labels, fontsize=8)

        for tick in self.axes.yaxis.get_major_ticks():
            tick.label1.set_transform(self.axes.transAxes)
            tick.label2.set_transform(self.axes.transAxes)
            tick.tick1line.set_transform(self.axes.transAxes)
            tick.tick2line.set_transform(self.axes.transAxes)
            tick.gridline.set_transform(self.axes.transAxes)            
        
        
        self.save_excursion()
        self.draw()

        
    def restore_excursion(self):
        try: self.saveExcursion
        except AttributeError: return
        tmin, self.timeInd, self.voltInd = self.saveExcursion 

        self.set_time_lim(tmin)
        

    def save_excursion(self):
        tmin, tmax = self.get_time_lim()
        self.saveExcursion = (tmin, self.timeInd, self.voltInd)
        

    def get_max_labels(self):
        return 25
    

    def change_time_gain(self, magnify=1):
        """Change the time scale.  zoom out with magnify=0, zoom in
        with magnify=1)"""

        # keep the index in bounds
        if magnify and self.timeInd>0:
            self.timeInd -= 1
            
        if not magnify and self.timeInd<(len(self.timeSets)-1):    
            self.timeInd += 1

        origmin, origmax = self.get_time_lim()
        wid, step = self.timeSets[self.timeInd]

        xmin = origmin
        xmax = origmin+wid
        
        self.set_time_lim(xmin, xmax, updateData=True)

    def change_volt_gain(self, magnify=1):
        """Change the voltage scale.  zoom out with magnify=0, zoom in
        with magnify=1)"""

        # keep the index in bounds
        if magnify and self.voltInd>0:
            self.voltInd -= 1
            
        if not magnify and self.voltInd<(len(self.voltSets)-1):    
            self.voltInd += 1

        vset = self.voltSets[self.voltInd]

        for line in self.lines:
            trans = line.get_transform()
            box1 =  trans.get_bbox1()
            box1.intervaly().set_bounds(-vset, vset)


    def pan_time(self, right=1):
        """Pan the time axis to the right or left"""

        # keep the index in bounds
        wid, step = self.get_twid_step()
        tmin, tmax = self.get_time_lim()
        step *= right
        
        self.set_time_lim(tmin+step)


    def get_time_lim(self,):
        return self.axes.get_xlim()


    def get_twid_step(self):
        return self.timeSets[self.timeInd]
        ticks = self.axes.get_xticks()
        wid = ticks[-1] - ticks[0]
        step = ticks[1] - ticks[0]
        return wid, step
        
    def set_time_lim(self, xmin=None, xmax=None,
                     updateData=True, broadcast=True):
        #make sure xmin keeps some eeg on the screen
        
        origmin, origmax = self.get_time_lim()
        if xmin is None: xmin = origmin
        
        if xmax is None:
            wid, step = self.get_twid_step()
            xmax = xmin+wid
        else:
            wid = xmax-xmin
            step = wid/10.0

        
        self.axes.set_xlim([xmin, xmax])
        ticks = arange(xmin, xmax+0.001, step)
        self.axes.set_xticks(ticks)
        def fmt(val):
            if val==int(val): return '%d' % val
            else: return '%1.1f' % val
        #self.axes.set_xticklabels([fmt(val) for val in ticks])
        self.axes.set_xticklabels([])


        if updateData:
            t, data, freq = self.filter(xmin, xmax)        
            self.axes.set_xlim((xmin, xmax))
            for ind, line in zip(self.indices, self.lines):
                line.set_data(t, data[:,ind])

        # recieve the observers
        if broadcast:
            self.broadcast(Observer.SET_TIME_LIM, xmin, xmax)

        
    def get_channel_at_point(self, x, y):
        "Get the EEG with the voltage trace nearest to x, y (window coords)"
        tmin, tmax = self.get_time_lim()
        dt = 1/self.decfreq


        height = self.canvas.figure.bbox.height()
        t, yt = self.axes.transData.inverse_xy_tup( (x,y) )

        ind = int((t-tmin)/dt)

        
        ys = zeros( (len(self.lines), ), typecode = Int16)


        for i, line in enumerate(self.lines):
            thisx = line.get_xdata()[ind]
            thisy = line.get_ydata()[ind]
            trans = line.get_transform()
            xt, yt = trans.xy_tup((thisx, thisy))
            ys[i] = height-yt

        ys = absolute(ys-y)
        matches = nonzero(ys==min(ys))

        ind = matches[0]
        labeld = self.eeg.amp.get_dataind_dict()
        trode = labeld[self.indices[ind]]
        gname, gnum = trode
        ok = self.set_selected((gname, gnum))
        if ok: self.broadcast(Observer.SELECT_CHANNEL, trode)
        return trode

    def set_selected(self, trode):
        
        
        lastind = self.eoiIndDict[self._selected]
        ind = self.eoiIndDict[trode]

        lastcolor = self.get_color(self._selected)
        self.lines[lastind].set_color(lastcolor)

        
        self._selected = trode
        self.lines[ind].set_color('r')

        self.canvas.draw()
        Shared.windowMain.update_status_bar('Selected %s %d' % trode)

        return True


class SpecPlot(Observer):
    propdlg = SpecProps()
    flim = 0, 40    # the defauly yaxis
    clim = None     # the colormap limits

    def __init__(self, axes, canvas, eegplot):
        Observer.__init__(self)
        self.axes = axes
        self.canvas = canvas
        self.eegPlot = eegplot
        self.cmap = cm.jet
        # min and max power

        
        
    def make_spec(self, *args):

        selected = self.eegPlot.get_selected()
        if selected is None:
            self.axes.cla()
            t = self.axes.text(
                0.5, 0.5,
                'Click on EEG channel for spectrogram (scroll mouse to expand)',
                verticalalignment='center',
                horizontalalignment='center',
                )
            t.set_transform(self.axes.transAxes)
            xmin, xmax = self.eegPlot.get_time_lim()
            self.axes.set_xlim( [xmin, xmax] )
            self.axes.set_xticks( self.eegPlot.axes.get_xticks()  )
            return

        flim = SpecPlot.flim
        clim = SpecPlot.clim

        torig, data, trode = selected
        gname, gnum = trode
        label = '%s %d' % (gname, gnum)
        Fs = self.eegPlot.eeg.freq

        NFFT, Noverlap = (512, 477)

        self.axes.cla()
        xmin, xmax = self.eegPlot.get_time_lim()
        xextent = xmin, xmax
        Pxx, freqs, t, im = self.axes.specgram(
            data, NFFT=NFFT, Fs=Fs, noverlap=Noverlap,
            cmap=self.cmap, xextent=xextent)

        if clim is not None:
            im.set_clim(clim[0], clim[1])

        t = t + min(torig)

        Z = 10*log10(Pxx)
        self.pmin = numpymin(Z) #i think the built in min and max should do exactly what the Mlab versions did, but we should make sure to test this further
        self.pmax = numpymax(Z)
        

        self.axes.set_xlim( [xmin, xmax] )
        self.axes.set_xticks( self.eegPlot.axes.get_xticks()  )

        #self.axes.set_title('Spectrogram for electrode %s' % label)
        #self.axes.set_xlabel('TIME (s)')
        self.axes.set_ylabel('FREQUENCY (Hz)')
        self.axes.set_ylim(flim)

        if flim[1]-flim[0]>=100:
            self.axes.set_yticks(arange(flim[0], flim[1]+1, 20))
        else:
            self.axes.set_yticks(arange(flim[0], flim[1]+1, 10))

    def recieve(self, event, *args):

        if event in (Observer.SELECT_CHANNEL, Observer.SET_TIME_LIM):
            self.make_spec()
            self.canvas.draw()
        elif event==Observer.SAVE_FRAME:
            fname = args[0]
            self.canvas.print_figure(fname + '_specgram.png', dpi=72)

    def set_properties(self, *args):
        dlg = SpecPlot.propdlg
        dlg.show()
        if not len(dlg.entryCMin.get_text()) and hasattr(self, 'pmin'):
            dlg.entryCMin.set_text('%1.2f'%self.pmin)
        if not len(dlg.entryCMax.get_text()) and hasattr(self, 'pmax'):
            dlg.entryCMax.set_text('%1.2f'%self.pmax)
            
        while 1:
            response = dlg.run()

            if response in  (gtk.RESPONSE_OK, gtk.RESPONSE_APPLY):
                b = dlg.validate()
                if not b: continue
                SpecPlot.flim = dlg.get_flim()
                SpecPlot.clim = dlg.get_clim()
                self.make_spec()
                self.canvas.draw()
                if response==gtk.RESPONSE_OK:
                    dlg.hide()
                    break
            else:
                dlg.hide()
                break

        
    
class MainWindow(PrefixWrapper):
    prefix = ''
    widgetName = 'windowMain'
    gladeFile = 'main.glade'

    def __init__(self):
    
        if os.path.exists(self.gladeFile):
            theFile=self.gladeFile
        else:
            theFile = os.path.join(
                distutils.sysconfig.PREFIX,
                'share', 'pbrain', self.gladeFile)
        
	#this is where we load the glade gui
        try: Shared.widgets = gtk.glade.XML(theFile)
        except:
            raise RuntimeError('Could not load glade file %s' % theFile)
        
        PrefixWrapper.__init__(self)
        self._isConfigured = False
        self.patient = None

        figsize = eegviewrc.figsize
        self.fig = Figure(figsize=figsize, dpi=72) #this is from matplotlib

        self.canvas = FigureCanvas(self.fig)  # a gtk.DrawingArea
        self.canvas.connect("scroll_event", self.scroll_event)
        self.canvas.show()

        #self.fig = Figure(figsize=(7,5), dpi=72)
        t = arange(0.0,50.0, 0.01)
        xlim = array([0,10]) #why is this line here? it seems to be unused

        self.axes = self.fig.add_axes([0.075, 0.25, 0.9, 0.725], axis_bgcolor='#FFFFCC') #changed the kwarg axisbg to the new version

        self.axes.plot(t, sin(2*0.32*pi*t) * sin(2*2.44*pi*t) )
        self.axes.set_xlim([0.0,10.0])
        self.axes.set_xticklabels([])

        
        self.axesSpec = self.fig.add_axes([0.075, 0.05, 0.9, 0.2])
        t = self.axesSpec.text(
            0.5, 0.5,
            'Click on EEG channel for spectrogram (scroll mouse to expand)',
            verticalalignment='center',
            horizontalalignment='center',
            )
        t.set_transform(self.axes.transAxes)
        self.axesSpec.set_xlim([0.0,10.0])
        self.axesSpec.set_xticklabels([])
        self.axesSpec.set_yticklabels([])
        
        win = self['windowMain']
        win.move(0,0)
        self.canvas.set_events(
            gdk.KEY_PRESS_MASK |
            gdk.KEY_RELEASE_MASK |
            gdk.EXPOSURE_MASK |
            gdk.LEAVE_NOTIFY_MASK |
            gdk.BUTTON_PRESS_MASK |
            gdk.BUTTON_RELEASE_MASK |
            gdk.POINTER_MOTION_MASK )
        self.canvas.connect('key_press_event', self.key_press_event)
        self.canvas.connect('key_release_event', self.key_release_event)
        self.canvas.connect('motion_notify_event', self.motion_notify_event)
        self.canvas.connect('button_press_event', self.button_press_event)
        self.canvas.connect('button_release_event', self.button_release_event)


        self['vboxMain'].pack_start(self.canvas, True, True)
        self['vboxMain'].show()
        
        self.toolbar = EEGNavBar( self.canvas, self['windowMain'])
        self.toolbar.show()
        self['vboxMain'].pack_start(self.toolbar, False, False)

        self.statbar = gtk.Statusbar()
        self.statbar.show()
        self.statbarCID = self.statbar.get_context_id('my stat bar')
        self['vboxMain'].pack_start(self.statbar, False, False)
        self.update_status_bar('')
        self.buttonDown = None


    def update_status_bar(self, msg):

        self.statbar.pop(self.statbarCID) 
        mid = self.statbar.push(self.statbarCID, 'Message: ' + msg)

        

    def menu_select_eeg(self, eeg):
        amp = eeg.get_amp()
        if amp.message is not None:
            simple_msg(amp.message, title='Warning',
                       parent=Shared.windowMain.widget)
            

        try: self.eegPlot
        except AttributeError: pass
        else: Observer.observers.remove(self.eegPlot)        

        try: self.specPlot
        except AttributeError: pass
        else: Observer.observers.remove(self.specPlot)        

        self.eegPlot = EEGPlot(eeg, self.canvas)
        self.toolbar.set_eegplot(self.eegPlot)
        self.specPlot = SpecPlot(self.axesSpec, self.canvas, self.eegPlot)
        self.specMenu = self.make_spec_menu()
        eois = eeg.get_associated_files(atype=5, mapped=1)
        self.eoiMenu = self.make_context_menu(eois)
        self.eegPlot.plot()
        return True

                  
    def make_patients_menu(self):

        entries = servers.sql.eeg.select(
            where='file_type in (1,4)')
        eegMap = {}
        for entry in entries:
            eegMap.setdefault(entry.pid,[]).append(EEGWeb(entry.get_orig_map()))

        pidList = ','.join(map(str,eegMap.keys()))

        # make a list of eegs and patients so we can pass an index to
        # the callback
        menuItemPatients = self['menuitemPatients']
        menuPatients = gtk.Menu()
        patients = servers.sql.patients.select(
            where='pid in (%s) ORDER BY last' % pidList)
        for patient in patients:
            if not eegMap.has_key(patient.pid): continue

            menuItemPatient = gtk.MenuItem(
                '%s%s' % (patient.first[:2], patient.last[:2]))
            menuItemPatient.show()

            menuEEGs = gtk.Menu()
            for eeg in eegMap[patient.pid]:
                eegLabel = eeg.filename.replace('_', '-')
                item = gtk.MenuItem(label=eegLabel)
                item.show()
                eeg.patient = patient
                item.connect_object(
                    "activate", self.menu_select_eeg, eeg)
                menuEEGs.append(item)
            menuItemPatient.set_submenu(menuEEGs)
            menuPatients.append(menuItemPatient)
        menuItemPatients.set_submenu(menuPatients)

        
    def load_eoi(self, eoi):
        success = self.eegPlot.set_eoi(eoi)
        
        if success:
            tmin, tmax = self.eegPlot.get_time_lim()
            self.eegPlot.plot()
            self.eegPlot.set_time_lim(tmin, tmax)
            self.eegPlot.draw()
        else:
            #todo: popup edit window for eoi
            pass
        
    def new_eoi(self, menuitem):
        self.edit_eoi()
        
    def make_context_menu(self, eois):
        contextMenu = gtk.Menu()

        label = "Load EOI"
        menuItemLoad = gtk.MenuItem(label)
        contextMenu.append(menuItemLoad)
        menuItemLoad.show()

        menuEOIS = gtk.Menu()
        for eoi in eois:
            eoiLabel = eoi.filename.replace('_', '-')
            item = gtk.MenuItem(label=eoiLabel)
            item.show()
            item.connect_object(
                "activate", self.load_eoi, eoi)
            menuEOIS.append(item)
        menuItemLoad.set_submenu(menuEOIS)

    
        label = "Save EOI"
        menuItemSave = gtk.MenuItem(label)
        contextMenu.append(menuItemSave)
        menuItemSave.connect("activate", self.save_eoi, 0)
        menuItemSave.show()

        label = "Save As EOI"
        menuItemSaveAs = gtk.MenuItem(label)
        contextMenu.append(menuItemSaveAs)
        menuItemSaveAs.connect("activate", self.save_eoi, 1)
        menuItemSaveAs.show()

        label = "Edit EOI"
        menuItemEdit = gtk.MenuItem(label)
        contextMenu.append(menuItemEdit)
        menuItemEdit.connect("activate", self.edit_eoi)
        menuItemEdit.show()

        label = "New EOI"
        menuItemNew = gtk.MenuItem(label)
        contextMenu.append(menuItemNew)
        menuItemNew.connect("activate", self.new_eoi)
        menuItemNew.show()
        return contextMenu


        return contextMenu


    def make_spec_menu(self):
        contextMenu = gtk.Menu()

        label = "Set limits"
        menuItemSave = gtk.MenuItem(label)
        contextMenu.append(menuItemSave)
        menuItemSave.connect("activate", self.specPlot.set_properties, 0)
        menuItemSave.show()
        return contextMenu


    def edit_eoi(self, *args):

        def ok_callback(eoi):
            success = self.eegPlot.set_eoi(eoi)
            if success:
                tmin, tmax = self.eegPlot.get_time_lim()
                self.eegPlot.plot()
                self.eegPlot.set_time_lim(tmin, tmax)
                self.eegPlot.draw()

            d.destroy_dialog()
            return
        
        eoiActive = self.eegPlot.get_eoi()
        eoiAll = self.eegPlot.get_eeg().get_amp().to_eoi()
        d = Dialog_SelectElectrodes(trodes=eoiAll,
                                    ok_callback=ok_callback,
                                    selected=eoiActive
                                    )
        d.set_transient_for(self.widget)


    def save_eoi(self, menuitem, saveas):

        eoi = self.eegPlot.get_eoi()
        if not self['dlgPref_radiobuttonUseWebOn'].get_active():
            # not using the web, write to local filesystem
            fname = fmanager.get_filename(
                    title='Enter filename for EOI')
            if not os.path.exists(fname):
                basepath, ext = os.path.splitext(fname)
                if ext.lower() != '.eoi':
                    fname += '.eoi'
            try:
                fh = file(fname, 'w')
                fh.write(eoi.to_conf_file())
            except IOError:
                error_msg('Could not write EOI to %s' % fname,
                          parent=self.widget)
            return

        #todo: handle same filename vs different filename; add a save as?
        def ok_callback(m):
            pid=self.eegPlot.get_eeg().get_pid()
            newName = m['filename']

            eoiNew = EOI()
            eoiNew.extend(eoi)
            
            def new_eoi_success():
                eeg = self.eegPlot.get_eeg()
                success = self.eegPlot.set_eoi(eoiNew)

                eoiNew.update_map(eeg.get_filename())
                eois = eeg.get_associated_files(atype=5, mapped=1)
                self.eoiMenu = self.make_context_menu(eois)
                dlgSave.hide_widget()
                simple_msg('%s successfully uploaded' % newName,
                              title='Congratulations',
                              parent=self.widget)
                if success: self.eegPlot.plot()

            # make a new file
            try:
                eoiNew.new_web(pid, newName)
            except NameError:
                # fname already exists
                def response_callback(dialog, response):
                    if response==gtk.RESPONSE_YES:
                        eoiNew.set_exists_web(pid, newName)
                        eoiNew.update_web()                            
                        new_eoi_success()
                    else: dialog.destroy()
                msg = '%s already exists.  Overwrite?' % newName
                yes_or_no(msg=msg, title='Warning!',
                          responseCallback=response_callback,
                          parent=dlgSave.widget)
            else: new_eoi_success()

        if not saveas and eoi.is_web_file():
            eoi.update_web()
            simple_msg('%s updated' % eoi.filename,
                          title='You did it!',
                          parent=self.widget)
            return
        
        dlgSave = Dialog_SaveEOI(eoiActive=self.eegPlot.get_eoi(),
                           eoisAll=self.eegPlot.get_eeg().get_eois(),
                           ok_callback=ok_callback)
        dlgSave.get_widget().set_transient_for(self.widget)
        dlgSave.show_widget()
        
    
    def on_buttonSaveExcursion_clicked(self, event):

        self.eegPlot.save_excursion()
        return True
    
    def on_buttonRestoreExcursion_clicked(self, event):

        self.eegPlot.restore_excursion()
        self.eegPlot.draw()
        return True
    
    def on_buttonJumpToTime_clicked(self, event):

        val = str2num_or_err(self['entryJumpToTime'].get_text(),
                            parent=self.widget)

        if val is None: return
        self.eegPlot.set_time_lim(val)
        self.eegPlot.draw()
        return True

    def expose_event(self, widget, event):
        return True
    
    def configure_event(self, widget, event):
        self._isConfigured = True
        return True

    def realize(self, widget):
        return True


            
    def key_press_event(self, widget, event):
        print event, dir(event)


    def key_release_event(self, widget, event):
        print 'bye mom'
        
    def motion_notify_event(self, widget, event):
        return True

    def scroll_event(self, widget, event):
        "If in specgram resize"
        if event.direction == gdk.SCROLL_UP:
            direction = 1
        else:
            direction = -1

        l1,b1,w1,h1 = self.axes.get_position()
        l2,b2,w2,h2 = self.axesSpec.get_position()


        
        deltay = direction*0.1*h2
        h1 -= deltay
        h2 += deltay
        
        self.axes.set_position([l1, b2+h2, w1, h1])
        self.axesSpec.set_position([l2, b2, w2, h2])

        self.canvas.draw()

        
    def button_press_event(self, widget, event):
        win = widget.window
        self.buttonDown = event.button
        height = self.canvas.figure.bbox.height()
        x, y = event.x, height-event.y
        if event.button==3:
            # right click brings up the context menu

            
            if self.axes.in_axes(x, y):
                menu = self.eoiMenu
            elif self.axesSpec.in_axes(x,y):
                menu = self.specMenu
            else:
                return 
            menu.popup(None, None, None, 0, 0)
        elif event.button==1:
            if self.axes.in_axes(x, y):
                trode = self.eegPlot.get_channel_at_point(event.x, event.y)
                gname, gnum = trode
                self.update_status_bar('Electrode: %s%d' % (gname, gnum))
            elif self.axesSpec.in_axes(x,y):
                t, f = self.axes.transData.inverse_xy_tup( (x,y) )
                self.update_status_bar(
                    'Time  = %1.1f (s), Freq = %1.1f (Hz)' % (t,f))

                
        else: print event.button
        return True

    def button_release_event(self, widget, event):
        self.buttonDown = None

    def on_menuFilePreferences_activate(self, event=None):

        
        def mysql_callback(dbname, host, user, passwd, port):
            servers.sql.init(dbname, host, user, passwd, port)
            self.make_patients_menu()
            eegviewrc.sqlhost = host
            eegviewrc.sqluser = user
            eegviewrc.sqlpasswd = passwd
            eegviewrc.sqlport = port
            eegviewrc.save()
            
        def datamanager_callback(url, user, passwd, cachedir):
            servers.datamanager.init(url, user, passwd, cachedir)
            eegviewrc.httpurl = url
            eegviewrc.httpuser = user
            eegviewrc.httppasswd = passwd
            eegviewrc.httpcachedir = cachedir
            eegviewrc.save()
            
        d = Dialog_Preferences(
            mysqlCallBack       = mysql_callback,
            dataManagerCallBack = datamanager_callback)

        params = {
            'zopeServer' : eegviewrc.httpurl,
            'zopeUser' : eegviewrc.httpuser,
            'zopePasswd' : eegviewrc.httppasswd,
            'zopeCacheDir' : eegviewrc.httpcachedir,
            
            'mysqlDatabase' : eegviewrc.sqldatabase,
            'mysqlServer' : eegviewrc.sqlhost,
            'mysqlUser' : eegviewrc.sqluser,
            'mysqlPasswd' : eegviewrc.sqlpasswd,
            'mysqlPort' : eegviewrc.sqlport,
            }        
        d.set_params(params)
        d.show_widget()
        d.get_widget().set_transient_for(self.widget)

        
        return True

    def on_menuFileQuit_activate(self, event):
        update_rc_and_die()


    def on_menuFileNew_activate(self, event):
        not_implemented(self.widget)

    def get_eeg_params(self, fullpath):
        def callback(pars): pass
            
        dlg = Dialog_EEGParams(fullpath, callback)

        dlg.show_widget()

        response = dlg.widget.run()

        if response == gtk.RESPONSE_OK:
            dlg.hide_widget()
            pars =  dlg.get_params()
            return pars


    def on_menuFileOpen_activate(self, event):
        dlg = gtk.FileSelection('Select EEG param file')
        dlg.set_transient_for(self.widget)
        dlg.set_filename(fmanager.get_lastdir() + os.sep)

        dlg.cancel_button.connect("clicked", lambda w: dlg.destroy())
        dlg.show()

        response = dlg.run()

        if response == gtk.RESPONSE_OK:
            fullpath =  dlg.get_filename()
            fmanager.set_lastdir(fullpath)
            dlg.destroy()

            if not os.path.exists(fullpath):
                error_msg(
                    'Cannot find %s' % fullpath,
                    title='Error',
                    parent=Shared.windowMain.widget)

            basename, ext = os.path.splitext(fullpath)
            if not extmap.has_key(ext.lower()):
                error_msg(
                    'Do not know how to handle extension %s in %s' % (ext, fullpath),
                    title='Error',
                    parent=Shared.windowMain.widget)
                
                return
            else:
                loader = extmap[ext.lower()]
                try: eeg = loader(fullpath)
                except ValueError, msg:
                    msg = exception_to_str('Error loading EEG' )
                    error_msg(msg, title='Error loading EEG',
                              parent=Shared.windowMain.widget)
                    return
                    

            if len(eeg.amps)>0:
                names = [os.path.split(fullname)[-1] for fullname in eeg.amps]
                name = select_name(names, 'Pick the AMP file')
                if name is None: return
                else:
                    amp = eeg.get_amp(name)

            else:
                amp = eeg.get_amp()

            if amp.message is not None:
                simple_msg(amp.message, title='Warning',
                           parent=Shared.windowMain.widget)


            dlg = gtk.Dialog('Please stand by')
            dlg.show()
            msg = gtk.Label('Loading %s; please hold on' % eeg.filename)
            msg.show()
            dlg.vbox.add(msg)            
            while gtk.events_pending(): gtk.main_iteration()

            try: self.eegPlot
            except AttributeError: pass
            else: Observer.observers.remove(self.eegPlot)        
            try: self.specPlot
            except AttributeError: pass
            else: Observer.observers.remove(self.specPlot)        
                
            self.eegPlot = EEGPlot(eeg, self.canvas)
            self.specPlot = SpecPlot(self.axesSpec, self.canvas, self.eegPlot)
            self.specMenu = self.make_spec_menu()
            dlg.destroy()
            while gtk.events_pending(): gtk.main_iteration()
            self.toolbar.set_eegplot(self.eegPlot)
            try: self.eegPlot.plot()
            except:
                msg = exception_to_str('Could not read data:')
                error_msg(msg, title='Error',
                          parent=Shared.windowMain.widget)
                return

                
            eois = eeg.get_associated_files(atype=5, mapped=1)
            self.eoiMenu = self.make_context_menu(eois)
            return True


    def on_menuFileSave_activate(self, event):
        not_implemented(self.widget)

    def on_menuHelpAbout_activate(self, event):
        not_implemented(self.widget)


    def on_menuChannelWindow_activate(self, event):

        try: self.eegPlot
        except AttributeError:
            simple_msg(
                'You must first select an EEG from the Patients menu',
                title='Error',
                parent=self.widget)
            return

        win = ChannelWin(eegPlot=self.eegPlot)
        win.show()

    def on_menuHistogramWindow_activate(self, event):

        try: self.eegPlot
        except AttributeError:
            simple_msg(
                'You must first select an EEG from the Patients menu',
                title='Error',
                parent=self.widget)
            return

        win = HistogramWin(eegPlot=self.eegPlot)
        win.show()

    def on_menuAcorrWindow_activate(self, event):

        try: self.eegPlot
        except AttributeError:
            simple_msg(
                'You must first select an EEG from the Patients menu',
                title='Error',
                parent=self.widget)
            return
        win = AcorrWin(eegPlot=self.eegPlot)
        win.show()

    def on_menuEmbedWindow_activate(self, event):

        try: self.eegPlot
        except AttributeError:
            simple_msg(
                'You must first select an EEG from the Patients menu',
                title='Error',
                parent=self.widget)
            return
        from embed import EmbedWin
        embedWin = EmbedWin(eegPlot=self.eegPlot)
        embedWin.show()

    def on_menuView3DWindow_activate(self, event):
        try: self.eegPlot
        except AttributeError:
            simple_msg(
                'You must first select an EEG from the Patients menu',
                title='Error',
                parent=self.widget)
            return
        from view3 import View3
        viewWin = View3(eegPlot=self.eegPlot)

        if viewWin.ok:
            viewWin.show()
        else:
            print >>sys.stderr, 'Got an error code from view3'

    def on_menuSpecWindow_activate(self, event):
        try: self.eegPlot
        except AttributeError:
            simple_msg(
                'You must first select an EEG',
                title='Error',
                parent=self.widget)
            return

        specWin = SpecWin(eegPlot=self.eegPlot)
        specWin.show()                
        
    def on_menuComputeExportToCohstat_activate(self, event):
        try: self.eegPlot
        except AttributeError:
            simple_msg(
                'You must first select an EEG from the Patients menu',
                title='Error',
                parent=self.widget)
            return
        eoi = self.eegPlot.get_eoi()
        if len(eoi)==64: 
            d = Dialog_CohstatExport(self.eegPlot.get_eeg(), eoi)
        else:
            d = Dialog_CohstatExport(self.eegPlot.get_eeg())
        d.get_widget().set_transient_for(self.widget)
        d.show_widget()
        
        return True

def update_rc_and_die(*args):
    eegviewrc.lastdir = fmanager.get_lastdir()
    #eegviewrc.figsize = Shared.windowMain.fig.get_size_inches()
    eegviewrc.save()
    gtk.main_quit()

if __name__=='__main__':
    Shared.windowMain = MainWindow()
    Shared.windowMain.show_widget()
    Shared.windowMain.on_menuFilePreferences_activate(None)
    Shared.windowMain.widget.connect('destroy', update_rc_and_die)
    Shared.windowMain.widget.connect('delete_event', update_rc_and_die)

    try: gtk.main ()
    except KeyboardInterrupt:
        update_rc_and_die()
