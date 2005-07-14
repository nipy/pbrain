"""
Todo:

  - check for tlim smaller than NFFT (cohere_bands raises type error)

  - enable cohere param setting

  - enable non periodogram cohere method

  - DONE update default dirs on load CSV and screenshot save

  - allow precise setting of bands

  - DONE enable an eegplot watcher that is responsive to changes in EEG and
    lim

  - DONE make default win smaller

  - DONE prevent toolbar buttons from expanding

  - fix eegplot to provide eoiAll if none is set

  - display active EOI only

  - DONE dialog percentage outside 0-1

  - DONE use Table for grid

  - DONE plot single selected option

  - respond to EOI changes

  - clear norm factor

  - surface map

  - DONE 2004-01-16 picture behind (translucent CT?)

  
"""
from __future__ import division
import sys, os, math
import vtk

import pygtk
pygtk.require('2.0')
import gtk

from sets import Set

from Numeric import array, zeros, ones, sort, absolute, Float, sqrt, divide,\
     argsort, take, arange
from MLab import mean, std

from loc3djr.markers import Marker
from loc3djr.GtkGLExtVTKRenderWindowInteractor import GtkGLExtVTKRenderWindowInteractor
from loc3djr.plane_widgets import PlaneWidgetsXYZ 
from loc3djr.image_reader import widgets as imageReaderWidgets

from matplotlib.cbook import exception_to_str
from matplotlib.mlab import detrend_none, detrend_mean, detrend_linear,\
     window_none, window_hanning, log2
from pbrainlib.gtkutils import error_msg, simple_msg, make_option_menu,\
     get_num_value, get_num_range, get_two_nums, str2int_or_err,\
     OpenSaveSaveAsHBox, ButtonAltLabel, SpreadSheet

from shared import fmanager
from borgs import Shared

from utils import filter_grand_mean, all_pairs_eoi, cohere_bands, power_bands,\
     cohere_pairs, cohere_pairs_eeg, get_best_exp_params,\
     get_exp_prediction, read_cohstat

from data import Amp, EOI
from matplotlib.backends.backend_gtkagg import FigureCanvasGTKAgg as FigureCanvas
from matplotlib.backends.backend_gtkagg import NavigationToolbar
from matplotlib.figure import Figure

from events import Observer
from dialogs import AutoPlayDialog
from mpl_windows import VoltageMapWin

def identity(frac, *args):
    return frac

def dist(x,y):
    tmp = array(x)-array(y)
    return sqrt(sum(tmp**2))


        
    

class View3(gtk.Window, Observer):
    banddict =  {'delta':0, 'theta':1, 'alpha':2,
                 'beta':3, 'gamma':4, 'high':5}

    def __init__(self, eegPlot):
        gtk.Window.__init__(self)

        
        self.ok = False  # do not show if false
        
        self.eegPlot = eegPlot
        self.eeg = eegPlot.get_eeg()
        self.amp = self.eeg.get_amp()
        self.cnumDict = self.amp.get_channel_num_dict()
        self.eoi = eegPlot.get_eoi()
        self.eoiPairs = all_pairs_eoi(self.eoi)
        self.selected = None
        self.cohCache = None  # cache coherence results from other window
        
        self.filterGM = eegPlot.filterGM
        self.gridManager = None
        seen = {}
        for key in self.eoi:
            if seen.has_key(key):
                error_msg('Duplicate key in eoi: %s %d' % key)
                return
            seen[key] = 1


            
        interactor = GtkGLExtVTKRenderWindowInteractor()
        interactor.AddObserver('LeftButtonPressEvent', self.press_left)

        self.picker = vtk.vtkCellPicker()
        self.picker.SetTolerance(0.005)
        interactor.SetPicker(self.picker)

        W = 240
        interactor.set_size_request(W, int(W/1.3))
        
        interactor.show()
        interactor.Initialize()
        interactor.Start()
        interactor.AddObserver("ExitEvent", lambda o,e,x=None: x)

        self.renderer = vtk.vtkRenderer()
        interactor.GetRenderWindow().AddRenderer(self.renderer)
        self.interactor = interactor

        self.set_title("View3 Window")
        self.set_border_width(10)

        vbox = gtk.VBox(spacing=3)
        self.add(vbox)
        vbox.show()

        hbox = gtk.HBox()
        hbox.show()
        hbox.set_spacing(3)

        self.imageManager = ImageManager(self.interactor, self.renderer)

        csv = self.eeg.get_loc3djr()

        if csv is not None:
            csv.fh.seek(0)
            ok = self.load_markers(infile=csv.fh)
        else:
            ok = self.load_markers()
        if not ok:
            return
        
        toolbar1 = self.make_toolbar1()
        toolbar1.show()
        toolbar2 = self.make_toolbar2()
        toolbar2.show()


        if sys.platform != 'darwin':
            self.progBar = gtk.ProgressBar()
            self.progBar.set_size_request(10, 100)

            self.progBar.set_orientation(2)  # bottom-to-top
            self.progBar.set_fraction(0)
            self.progBar.show()

        vbox.pack_start(hbox, gtk.TRUE, gtk.TRUE)
        hbox.pack_start(toolbar1, gtk.FALSE, gtk.FALSE)
        hbox.pack_start(interactor, gtk.TRUE, gtk.TRUE)
        if sys.platform != 'darwin':
            hbox.pack_start(self.progBar, gtk.FALSE, gtk.FALSE)
        vbox.pack_end(toolbar2, gtk.FALSE, gtk.FALSE)

        # norm is a dictionary mapping band indices to
        # distance/coherence normalizations
        self.norm = {}  
        # text label attributes
        self.textOn = True

        # line connection attribute
        self.thresholdParams = 'pct.', 0.025


        self.interactor.Render()

        # only register when you are built
        Observer.__init__(self)

        self.ampAscii = None   # for external data
        self.ok = True

    def set_eoi(self, eoi):
        self.eoi = eoi
        self.cohCache = None
        self.eoiPairs = all_pairs_eoi(self.eoi)
        try: del self.cohereResults
        except AttributeError: pass

        try: del self.pxxResults
        except AttributeError: pass
        
    def press_left(self, *args):
        'If in selection mode and click over marker, select it and update plot'
        if not self.buttonSelected.get_active(): return
        if self.gridManager is None: return
        if self.gridManager.markers is None: return


        markers = self.gridManager.markers_as_collection()
        x, y = self.interactor.GetEventPosition()
        picker = vtk.vtkPropPicker()
        picker.PickProp(x, y, self.renderer, markers)
        actor = picker.GetActor()        
        if actor is None: return

        gname, gnum = actor.get_name_num()

        self.selected = gname, gnum

        # now get the amplifier channel num
        key = (gname, gnum)
        if not self.cnumDict.has_key(key):
            error_msg('No amplifier channel for electrode %s %d' % key,
                      parent=self)
            self.interactor.LeftButtonReleaseEvent()
            return
        cnum =  self.cnumDict[ key]
        self.plot_band()
        trode = gname, gnum
        self.broadcast(Observer.SELECT_CHANNEL, trode)
    
    def make_toolbar1(self):

        toolbar1  = gtk.Toolbar()
        iconSize = gtk.ICON_SIZE_SMALL_TOOLBAR
        toolbar1.set_border_width(5)
        toolbar1.set_style(gtk.TOOLBAR_ICONS)
        toolbar1.set_orientation(gtk.ORIENTATION_VERTICAL)


        def show_grid_manager(button):
            if self.gridManager is not None:
                self.gridManager.show()
            
        iconw = gtk.Image() # icon widget
        iconw.set_from_stock(gtk.STOCK_PREFERENCES, iconSize)
        button = toolbar1.append_item(
            'Grids',
            'Grid propertes',
            'Private',
            iconw,
            show_grid_manager)

        iconw = gtk.Image() # icon widget
        iconw.set_from_stock(gtk.STOCK_OPEN, iconSize)
        button = toolbar1.append_item(
            'Coherence from datafile',
            'Coherence from datafile',
            'Private',
            iconw,
            self.coherence_from_file)

        iconw = gtk.Image() # icon widget
        iconw.set_from_stock(gtk.STOCK_SELECT_COLOR, iconSize)
        button = toolbar1.append_item(
            'Voltage map',
            'Voltage map',
            'Private',
            iconw,
            self.voltage_map)

        def compute_and_plot(*args):
            self.compute_coherence()
            self.plot_band()
            
        iconw = gtk.Image() # icon widget
        iconw.set_from_stock(gtk.STOCK_EXECUTE, iconSize)
        button = toolbar1.append_item(
            'Coherence',
            'Compute coherence',
            'Private', 
            iconw,
            compute_and_plot)

        iconw = gtk.Image() # icon widget
        iconw.set_from_stock(gtk.STOCK_PROPERTIES, iconSize)
        button = toolbar1.append_item(
            'Normalization',
            'Define coherence normalization window',
            'Private', 
            iconw,
            self.compute_norm_over_range)



        toolbar1.append_space()
        iconw = gtk.Image() # icon widget
        iconw.set_from_stock(gtk.STOCK_CLEAR, iconSize)
        button = toolbar1.append_item(
            'Plot',
            'Plot band connections',
            'Private', 
            iconw,
            self.plot_band,
            'mouse1 color')


        toolbar1.append_space()


        iconw = gtk.Image() # icon widget
        iconw.set_from_stock(gtk.STOCK_SAVE_AS, iconSize)
        button = toolbar1.append_item(
            'Screenshot',
            'Save screenshot to file',
            'Private',
            iconw,
            self.save_image)

        iconw = gtk.Image()
        iconw.set_from_stock(gtk.STOCK_JUMP_TO, iconSize)
        bAuto = toolbar1.append_item(
            'Autoplay',
            'Automatically page the EEG',
            'Private',
            iconw,
            self.auto_play)

        def close(*args):
            self.destroy()

        iconw = gtk.Image() 
        iconw.set_from_stock(gtk.STOCK_QUIT, iconSize)
        button = toolbar1.append_item(
            'Close',
            'Close view 3D',
            'Private',
            iconw,
            close)

        return toolbar1


    def make_toolbar2(self):

        toolbar2  = gtk.Toolbar()
        iconSize = gtk.ICON_SIZE_SMALL_TOOLBAR
        toolbar2.set_border_width(5)
        #toolbar2.set_style(gtk.TOOLBAR_BOTH)
        toolbar2.set_style(gtk.TOOLBAR_ICONS)

        self._activeBand = 'delta'
        def set_active_band(menuitem, label):
            self._activeBand = label
            self.plot_band()
            
        bandMenu, bandItemd  = make_option_menu(
            ('delta', 'theta', 'alpha', 'beta', 'gamma', 'high'),
            func=set_active_band)
        toolbar2.append_widget(bandMenu, 'The frequency band', '')



        def get_thresh_value(menuitem, label):


            if label=='STD':
                title='Enter standard deviation'
                default = 2
            elif label=='pct.':
                title='Enter threshold percentage'
                default = 0.025
            elif label=='abs.':
                title='Enter absolute threshold'
                default = 0.7
            elif label=='ratio':
                title='Enter ratio'
                default = 1.5            
            elif label=='plot':
                self.plot_normed_data()
                return
            else:
                error_msg('Unrecognized label %s' % label,
                          parent=self)
                return

            oldLabel, oldVal = self.thresholdParams            
            if label==oldLabel: default = oldVal
            value = get_num_value(
                labelStr=label, title=title, default=default)

            if value is None: return
            self.thresholdParams = label, value
            self.plot_band()
            
        threshMenu, threshItemd  = make_option_menu(
            ('pct.', 'abs.', 'STD', 'ratio', 'plot'),
            func=get_thresh_value)
        toolbar2.append_widget(threshMenu, 'The threshold type', '')


        def low_clicked(button):
            self._low = button.get_active()
            
        self._low = False
        button = gtk.CheckButton('Low')
        button.show()
        button.set_active(self._low)
        toolbar2.append_widget(
            button, 'Only plot low', '')

        button.connect('toggled', low_clicked)

        self.entryMaxDist = gtk.Entry()
        self.entryMaxDist.show()
        self.entryMaxDist.set_text('None')
        self.entryMaxDist.set_width_chars(5)
        toolbar2.append_widget(self.entryMaxDist, 'Maximum distace', '')

        iconw = gtk.Image() # icon widget
        iconw.set_from_stock(gtk.STOCK_EXECUTE, iconSize)
        button = toolbar2.append_item(
            'Replot',
            'Replot',
            'Private', 
            iconw,
            self.plot_band)

        toolbar2.append_space()

        

        self.buttonFollowEvents = gtk.CheckButton('Auto')
        self.buttonFollowEvents.show()
        self.buttonFollowEvents.set_active(False)
        toolbar2.append_widget(
            self.buttonFollowEvents, 'Automatically update figure in response to changes in EEG window', '')

        def toggled(button):
            
            if not button.get_active():
                self.selected = None
            else:
                selected = self.eegPlot.get_selected()
                if selected is not None:
                    torig, data, trode = selected
                    gname, gnum = trode
                    self.selected = gname, gnum
                    self.plot_band()



        self.buttonSelected = gtk.CheckButton('Selected')
        self.buttonSelected.show()
        self.buttonSelected.set_active(False)
        toolbar2.append_widget(
            self.buttonSelected, 'Only plot coherences with selected electrode', '')

        self.buttonSelected.connect('toggled', toggled)




        def show_image_prefs(button):
            self.imageManager.show_prefs()
            
            
        iconw = gtk.Image() # icon widget
        iconw.set_from_stock(gtk.STOCK_NEW, iconSize)
        buttonNew = toolbar2.append_item(
            'Image data',
            'Image data preferences',
            'Private',
            iconw,
            show_image_prefs)


        iconw = gtk.Image() # icon widget
        iconw.set_from_stock(gtk.STOCK_INDEX, iconSize)
        buttonNew = toolbar2.append_item(
            'Show data',
            'Display coherences in spreadsheet',
            'Private',
            iconw,
            self.show_spreadsheet)

        

        return toolbar2

    def show_spreadsheet(self, *args):
        rows = self.plot_band(saveRows=True)
        sheet = SpreadSheet(rows, fmanager=fmanager, title='Suprathreshold coherehences in %s'%self._activeBand)
        sheet.show_all()
        
    def voltage_map(self, button):
        win = VoltageMapWin(self)
        win.show()

    def coherence_from_file(self, *args):


        filename = fmanager.get_filename()
        if filename is None: return
        if not os.path.exists(filename):
            error_msg('File %s does not exist' % filename, parent=dlg)
            return

        try: fh = file(filename)
        except IOError, msg:
            msg = exception_to_str('Could not open %s' % filename)
            error_msg(msg)
            return
            
        try: cxy, pxy = read_cohstat(fh)
        except RuntimeError, msg:
            msg = exception_to_str('Error parsing %s' % filename)
            error_msg(msg)
            return

        seen = {}
        for i,j in cxy.keys():
            seen[i] = 1
            seen[j] = 1
        channels = seen.keys()
        channels.sort()
            
        ampDlg = AmpDialog(channels)
        ampDlg.show()
        amp = ampDlg.get_amp()
        if amp is None: return
        self.amp = amp
        # Convert the cyx, pxy to electrode dicts and filter out
        # channels not in the eoi

        d = amp.get_channelnum_dict()

        # make sure the keys agree
        Cxy = {}; Pxy = {}
        keys = cxy.keys()
        skipd = {}
        eoi = amp.to_eoi()
        self.set_eoi(eoi)

        for i,j in keys:
            if not d.has_key(i):
                skipd[i] = 1
                continue
            if not d.has_key(j):
                skipd[j] = 1
                continue
            key = d[i], d[j]

            Cxy[key] = cxy[(i,j)]
            Pxy[key] = pxy[(i,j)]


        skipped = skipd.keys()
        skipped.sort()
        if len(skipped):
            print >>sys.stderr, 'Skipping these electrodes not in eoi\n\t%s eoi'%skipped

        
        self.cohereResults = None, Cxy, Pxy
        self.plot_band()


    def auto_play(self, *args):
        
        tmin, tmax = self.eegPlot.get_time_lim()
        twidth = tmax-tmin
        maxTime = self.eeg.get_tmax()
        dlg = AutoPlayView3Dialog(self, tmin, maxTime, twidth)
        self.buttonFollowEvents.set_active(True)
        dlg.show()


    def compute_norm_over_range(self, *args):
        pars = get_two_nums('T min', 'T max', parent=self,
                            title='Enter time range for normalization')
        if pars is None: return
        tmin, tmax = pars
        self.compute_coherence( setTime=(tmin, tmax) )
        freqs, Cxy, Pxy = self.cohereResults
        self.norm = {}
        for bandind in range(len(self.banddict)):
            dvec, cvec, predicted, pars = self.norm_by_distance(Cxy, bandind)
            normedvec = divide(cvec, predicted)
            cutoff = self.get_cutoff(normedvec)
            self.norm[bandind] = pars, cutoff
        
        self.plot_band()
        
    def load_markers(self, *args, **kwargs):

        infile = kwargs.get('infile', None)
        if infile is None:
            fname = fmanager.get_filename(title='Enter marker filename: *.csv')
            if fname is None: return

            try: infile = file(fname, 'r')
            except IOError, msg:
                err = '\n'.join(map(str, msg))
                error_msg('Could not open %s for reading\n%s' % (fname,err),
                          parent=self)
                self.gridManager.markers = None
                return

        self.gridManager = GridManager(self.interactor, self.renderer, infile)
        if not self.gridManager.ok:
            return
        
        # validate the marker dict with eoi
        bad = []
        for key in self.eoi:
            if not self.gridManager.markerd.has_key(key):
                bad.append(key)

        if len(bad):
            s = ', '.join(['%s %d'%key for key in bad])
            simple_msg('Ignoring these electrodes not in marker\n\t%s'%s)
            for key in bad:
                self.eoi.remove(key)
            self.eoiPairs = all_pairs_eoi(self.eoi)


        self.markersEOI = [self.gridManager.markerd[key] for key in self.eoi]

        named = {}
        self.xyzd = {}
        for m in self.markersEOI:
            name, num = m.get_name_num()
            self.xyzd[(name,num)] = m.get_center()
            named[name]=1

        self.gridNames = named.keys()

        self.renderer.ResetCamera()
        self.interactor.Render()

        return True
    
    def recieve(self, event, *args):

        if not self.buttonFollowEvents.get_active(): return
        if event in (Observer.SET_TIME_LIM,):
            self.compute_coherence()
            self.plot_band()
        elif event==Observer.SAVE_FRAME:
            fname = args[0]
            basename = '%s_%s_coherence' % (fname, self._activeBand)
            framefile = basename+'.png'
            self.save_image(filename=framefile)
            basedir, filepart = os.path.split(framefile)
            listfile = os.path.join(basedir, 'coherence.vfl')
            try:  file(listfile, 'a').write('%s\n'%filepart)
            except IOError:
                error_msg('Could not write list file %s' % listfile)
                return

            
        elif event == Observer.SELECT_CHANNEL:
            trode = args[0]
            gname, gnum = trode
            self.selected = gname, gnum
            self.plot_band()
        elif event== Observer.COMPUTE_COHERENCE:            
            tlim, eoiPairs, cohRes, pxxRes = args
            self.cohCache = tlim, eoiPairs, cohRes, pxxRes

        elif event == Observer.GMTOGGLED:
            button = args[0]
            self.filterGM = button.get_active()
            self.compute_coherence()
            self.plot_band()


    def compute_coherence(self, setTime=None, *args):

        if sys.platform == 'darwin':
            def progress_callback(frac,  msg):
                print msg, frac
        else:
            def progress_callback(frac,  msg):
                if frac<0 or frac>1: return
                self.progBar.set_fraction(frac)
                while gtk.events_pending(): gtk.mainiteration()

        

        if setTime is None:
            tmin, tmax = self.eegPlot.get_time_lim()
        else:
            tmin, tmax = setTime

        if self.cohCache is not None:
            tlim, eoiPairs, cohRes, pxxRes = self.cohCache
            if (tlim[0] == tmin and
                tlim[1] == tmax and
                self.eoiPairs==eoiPairs):
                self.cohereResults = cohRes
                self.pxxResults = pxxRes
                return

        
        eeg = self.eegPlot.get_eeg()
        dt = 1.0/eeg.freq

        t, data = self.eeg.get_data(tmin, tmax)

        Nt = len(t)
        NFFT = int(2**math.floor(log2(Nt)-2))
        print 'NFFT', NFFT
        NFFT = min(NFFT, 512)
        if self.filterGM:            
            data = filter_grand_mean(data)
            
        Cxy, Phase, freqs, Pxx = cohere_pairs_eeg(
            eeg,
            self.eoiPairs,
            data = data,
            NFFT = NFFT,
            detrend = detrend_none,
            window = window_none,
            noverlap = 0,
            preferSpeedOverMemory = 1,
            progressCallback = progress_callback,
            returnPxx=True,
            )
        bands = ( (1,4), (4,8), (8,12), (12,30), (30,50), (70,100) )
        cxyBands, phaseBands = cohere_bands(
            Cxy, Phase, freqs, self.eoiPairs, bands,
            progressCallback=progress_callback,
            )
        pxxBand = power_bands(Pxx, freqs, bands)

        self.cohereResults  = freqs, cxyBands, phaseBands
        self.pxxResults = pxxBand
        self.broadcast(Observer.COMPUTE_COHERENCE,
                       (tmin, tmax),
                       self.eoiPairs,
                       self.cohereResults,
                       self.pxxResults)
        
    def get_band_ind(self):
        'Get the index into the band summary coherences'
        try: self.cohereResults
        except AttributeError:  self.compute_coherence()
        
        freqs, cxyBands, phaseBands = self.cohereResults
        bandind = self.banddict[self._activeBand]
        return bandind
    
    def plot_band(self, *args, **kwargs):
        bandind = self.get_band_ind()

        try: self.cohereResults
        except AttributeError:  self.compute_coherence()

        freqs, cxyBands, phaseBands = self.cohereResults
        ret = self.draw_connections(cxyBands, phaseBands, **kwargs)

        
        try: pxx = self.pxxResults
        except AttributeError: pass
        else:
            datad = dict([(key, 10*math.log10(vals[bandind])) for key, vals in pxx.items()])

            self.gridManager.scalarVals = []
            self.gridManager.set_scalar_data(datad)
        return ret
        
        
    def norm_by_distance(self, Cxy, bandind=None, pars=None):
        """
        Convert the cxy dict to an array over the eoi pairs and
        compute the best exponential fit.  If the optimizer doesn't
        converge, it will raise an error and return None.
        """
        if bandind is None:
            bandind = self.get_band_ind()

        cvec = array([Cxy[key][bandind] for key in self.eoiPairs])
        dvec = array([dist(self.xyzd[e1], self.xyzd[e2])
                      for e1,e2 in self.eoiPairs])

        threshType, threshVal = self.thresholdParams
        if threshType=='abs.':
            predicted = ones(cvec.shape, typecode=Float)
            return dvec, cvec, predicted, None
        

        if pars is None:
            pars = get_best_exp_params(dvec, cvec)
        if pars is None:
            error_msg('Best fit exponential did not converge',
                      parent=self)
            return dvec, cvec, None, None

        predicted = get_exp_prediction(pars, dvec)
        return dvec, cvec, predicted, pars

    def plot_normed_data(self):

        if self.gridManager.markers is None:
            self.load_markers()

        try: self.cohereResults
        except AttributeError:  self.compute_coherence()



        
        win = gtk.Window()
        win.set_name("Coherence by distance")
        win.set_border_width(5)

        vbox = gtk.VBox(spacing=3)
        win.add(vbox)
        vbox.show()


        fig = Figure(figsize=(7,5), dpi=72)

        self.canvas = FigureCanvas(fig)  # a gtk.DrawingArea
        self.canvas.show()
        vbox.pack_start(self.canvas, gtk.TRUE, gtk.TRUE)


        freqs, Cxy, Pxy = self.cohereResults
        ret = self.get_cxy_pxy_cutoff(Cxy, Pxy)
        if ret is None: return
        dvec, cvec, cxy, pxy, predicted, pars, normedvec, cutoff = ret

            
        threshType, threshVal = self.thresholdParams

        
        if pars is None:
            bandind = self.get_band_ind()
            ax = fig.add_subplot(111)
            ax.plot(dvec, cvec, 'b,')
            if threshType=='abs.':
                ax.plot(dvec, cutoff*ones(dvec.shape, typecode=Float), 'r-')

        else:

            ax1 = fig.add_subplot(211)
            ax1.set_title('Coherence vs distance')            
            ind = argsort(dvec)
            dsort = take(dvec, ind)
            psort = take(predicted, ind)
            ax1.plot(dvec, cvec, 'b,',
                     dsort, psort, 'g-')

            if threshType=='abs.':
                ax1.plot(dvec, cutoff*ones(dvec.shape, typecode=Float), 'r-')
            ax1.set_ylabel('Absolute')

            ax2 = fig.add_subplot(212)
            ax2.plot(dvec, normedvec, 'k,',
                     dsort, ones(dsort.shape, typecode=Float), 'g-')
            ax2.set_ylabel('Normalized')
            ax2.set_xlabel('Distance (cm)')            

            #print 'threshType', threshType
            if threshType in ('pct.', 'STD', 'ratio'):
                #print 'plotting line at', threshVal
                ax2.plot(dvec, cutoff*ones(dvec.shape, typecode=Float), 'r-')
                

        toolbar = NavigationToolbar(self.canvas, win)
        toolbar.show()
        vbox.pack_start(toolbar, gtk.FALSE, gtk.FALSE)
        win.show()
        

    def get_cutoff(self, normedvec):

        threshType, threshVal = self.thresholdParams
        if threshType=='pct.':
            # normalize the coherences by expected value
            normsort = sort(normedvec)
            ptile = 1-threshVal
            cutoff = normsort[int(ptile*len(normsort))]  # the percentile cuttoff
        elif threshType=='abs.':
            cutoff = threshVal
        elif threshType=='STD':
            # normalize the coherences by expected value
            normsort = sort(normedvec)
            # compute the mean and std
            mu = mean(normedvec)
            sigma = std(normedvec)
            cutoff = mu + threshVal*sigma
        elif threshType=='ratio':
            cutoff = threshVal
        else:
            error_msg('Unrecognized threshold type %s' % threshType,
                      parent=self)
            return None
        return cutoff
    
    def get_cxy_pxy_cutoff(self, Cxy, Pxy):
        threshType, threshVal = self.thresholdParams
        #print 'threshparams', threshType, threshVal
        
        bandind = self.get_band_ind()
        cvals = [a[bandind] for a in Cxy.values()]
        #print 'get_cxy_pxy_cutoff1', '%1.2f'%min(cvals), '%1.2f'%max(cvals)

        stored  = self.norm.get(bandind, None)

        
        if stored is None:
            # compute local norm
            dvec, cvec, predicted, pars = self.norm_by_distance(Cxy)
            normedvec = divide(cvec, predicted)
            cutoff = self.get_cutoff(normedvec)
        else:
            pars, cutoff = stored
            dvec, cvec, predicted, tmp = self.norm_by_distance(Cxy, pars=pars)
            normedvec = divide(cvec, predicted)

        #print 'get_cxy_pxy_cutoff 2', '%1.2f'%min(cvec), '%1.2f'%max(cvec)
        cxy = {}
        pxy = {}
        for i in range(len(dvec)):
            key = self.eoiPairs[i]
            if not Cxy.has_key(key):
                print 'norm skip', key
                continue
            cxy[key] = Cxy[key][bandind]/predicted[i]
            pxy[key] = Pxy[key][bandind]

        return dvec, cvec, cxy, pxy, predicted, pars, normedvec, cutoff

        
    def draw_connections(self, Cxy, Pxy, **kwargs):

        N = len(self.eoi)

        ret = self.get_cxy_pxy_cutoff(Cxy, Pxy)
        if ret is None:
            print >>sys.stderr, 'return is None'
            return None
        dvec, cvec, cxy, pxy, predicted, pars, normedvec, cutoff = ret

        cvals = cxy.values()

        def posphase(frac):
            return frac
        def negphase(frac):
            return 1-frac

        lines = []


        useSelected = self.buttonSelected.get_active() and (self.selected is not None)

        maxd = self.entryMaxDist.get_text()
        try: maxd = float(maxd)
        except ValueError: maxd = None

        saveRows = kwargs.get('saveRows', False)
        rows = []
        
        
        self.gridManager.flush_connections()
        #for key in cxy.keys(): print key
        for i in range(N):
            for j in range(i+1,N):
                e1 = self.eoi[i]
                e2 = self.eoi[j]
                if (useSelected and not
                    (e1 == self.selected or e2 == self.selected)): continue

                key = (e1,e2)
                if not cxy.has_key(key):
                    print 'draw_connections no key:',key
                    continue
                if maxd is not None:
                    d = dist(self.xyzd[e1], self.xyzd[e2])
                    if d>maxd: continue
                phase = pxy[key]
                if abs(phase)<0.1: phasemap = None
                elif phase>0: phasemap = posphase  # 1 leads 2
                else: phasemap = negphase          # 2 leads 1

                coherence = cxy[key]
                #print e1, e2, coherence, cutoff
                if self._low:
                    if coherence>cutoff: continue
                else:
                    if coherence<cutoff: continue

                ok = self.gridManager.connect_markers(
                    e1, e2, scalarfunc=phasemap)
                if not ok:
                    error_msg('Giving up', parent=self)
                    break
                if saveRows: rows.append(('%s %d'%e1, '%s %d'%e2, '%1.4f'%coherence))
        self.interactor.Render()
        return rows
        



        
    def save_image(self, *args, **kwargs):

        fname = kwargs.get('filename')
        if fname is None:
            fname = fmanager.get_filename(title='Save image in filename')
        if fname is None: return

        
        extmap = {'.jpg' : vtk.vtkJPEGWriter,
                  '.jpeg' : vtk.vtkJPEGWriter,
                  '.png' : vtk.vtkPNGWriter,
                  '.pnm' : vtk.vtkPNMWriter,
                  }
        basename, ext = os.path.splitext(fname)
        try: Writer = extmap[ext.lower()]
        except KeyError:
            error_msg("Don't know how to handle %s files" % ext, parent=self)
            return
        
        renWin = self.renderer.GetRenderWindow()
        w2i = vtk.vtkWindowToImageFilter()
        writer = Writer()
        w2i.SetInput(renWin)
        w2i.Update()
        writer.SetInput(w2i.GetOutput())
        writer.SetFileName(fname)
        self.interactor.Render()
        writer.Write()

class AutoPlayView3Dialog(AutoPlayDialog):
    def __init__(self, view3, tmin, tmax, twidth, quitHook=None):
        AutoPlayDialog.__init__(self, tmin, tmax, twidth, quitHook)
        self.view3 = view3
        
        frame = gtk.Frame('Rotation')
        frame.show()
        self.vbox.pack_start(frame, gtk.FALSE, gtk.FALSE)
        frame.set_border_width(5)


        vboxFrame = gtk.VBox()
        vboxFrame.show()
        frame.add(vboxFrame)


                
        buttonUseRotation = gtk.CheckButton('Use rotation')
        buttonUseRotation.show()
        vboxFrame.pack_start(buttonUseRotation, gtk.FALSE, gtk.FALSE)
        buttonUseRotation.connect('toggled', self.use_rotation)
        buttonUseRotation.set_active(gtk.FALSE)
        self.buttonUseRotation = buttonUseRotation

        self.rotationWidgets = []
        hbox = gtk.HBox()
        hbox.show()
        hbox.set_spacing(3)
        vboxFrame.pack_start(hbox, gtk.TRUE, gtk.TRUE)
        self.rotationWidgets.append(hbox)

        self.frames = []
            
        button = ButtonAltLabel('Clear', stock=gtk.STOCK_CUT)
        button.show()
        hbox.pack_start(button, gtk.TRUE, gtk.TRUE)
        button.connect('clicked', self.clear_frames)

        button = ButtonAltLabel('Add frame', stock=gtk.STOCK_ADD)
        button.show()
        hbox.pack_start(button, gtk.TRUE, gtk.TRUE)
        button.connect('clicked', self.add_frame)

        button = ButtonAltLabel('Interpolate', stock=gtk.STOCK_EXECUTE)
        button.show()
        hbox.pack_start(button, gtk.TRUE, gtk.TRUE)
        button.connect('clicked', self.interpolate_frames)

        self.labelFrames = gtk.Label()
        self.labelFrames.show()
        hbox.pack_start(self.labelFrames, gtk.TRUE, gtk.TRUE)


        hbox = gtk.HBox()
        hbox.show()
        hbox.set_spacing(3)
        vboxFrame.pack_start(hbox, gtk.TRUE, gtk.TRUE)
        self.rotationWidgets.append(hbox)
        
        labelPerTime = gtk.Label('Frames per time step')
        labelPerTime.show()
        hbox.pack_start(labelPerTime, gtk.FALSE, gtk.FALSE)



        entryPerTime = gtk.SpinButton()
        entryPerTime.show()
        hbox.pack_start(entryPerTime, gtk.FALSE, gtk.FALSE)
        #entryPerTime.set_width_chars(5)

        entryPerTime.set_range(0, 100)
        entryPerTime.set_increments(1, 5)
        entryPerTime.set_value(5)
        entryPerTime.set_numeric(gtk.TRUE)
        entryPerTime.set_snap_to_ticks(gtk.TRUE)
        entryPerTime.update()
        self.entryPerTime = entryPerTime

        self.update_frames_label()        
        self.use_rotation(self.buttonUseRotation)

        self.interpFrames = None

    def update_frames_label(self):
        self.labelFrames.set_text('Num frames: %d' % len(self.frames))

    def add_frame(self, button):

        camera = self.view3.renderer.GetActiveCamera()
        fpu = camera.GetFocalPoint(), camera.GetPosition(), camera.GetViewUp()

        im = self.view3.imageManager

        if im.using_planes():
            slicex = im.pwX.GetOrigin(), im.pwX.GetPoint1(), im.pwX.GetPoint2()
            slicey = im.pwY.GetOrigin(), im.pwY.GetPoint1(), im.pwY.GetPoint2()
            slicez = im.pwZ.GetOrigin(), im.pwZ.GetPoint1(), im.pwZ.GetPoint2()
        else:
            slicex = None, None, None
            slicey = None, None, None
            slicez = None, None, None

        slicePositions = slicex, slicey, slicez
        self.frames.append((fpu, slicePositions))
        self.update_frames_label()


    def clear_frames(self, button):
        self.frames = []
        self.update_frames_label()

    def use_rotation(self, button):
        sensitive = button.get_active()
        for w in self.rotationWidgets:
            w.set_sensitive(sensitive)

    def interpolate_frames(self, button=None):
        """
        Interpolate between the camera frames, with steps interpolated
        points between each frame.  frames is a sequence of fpu, IPW
        slice positions, where fpu is a (Focal Point, Position,
        ViewUp) tuple

        This routine matches frames to time steps and interpolates a
        frame for each time step.  It does not do the subinterpolation
        between time steps
        """

        self.interpFrames = None
        self.setpars()
        numInPnts = len(self.frames)
        numOutPnts = len(self.steps)*self.entryPerTime.get_value_as_int()

        if numInPnts<2:
            error_msg('Found only %d input frames' % len(self.frames) ,
                      parent=self)
            return 
        if numOutPnts<2:
            error_msg('Found only %d time steps' % len(self.steps) ,
                      parent=self)
            return 
        def interpolate_tup3(tups):
            aSplineX = vtk.vtkCardinalSpline()
            aSplineY = vtk.vtkCardinalSpline()
            aSplineZ = vtk.vtkCardinalSpline()

            for i,tup in enumerate(tups):
                x,y,z = tup
                aSplineX.AddPoint(i, x)
                aSplineY.AddPoint(i, y)
                aSplineZ.AddPoint(i, z)

            pnts = []
            for i in range(numOutPnts):
                t = (numInPnts-1.0)/(numOutPnts-1.0)*i
                pnts.append((aSplineX.Evaluate(t),
                             aSplineY.Evaluate(t),
                             aSplineZ.Evaluate(t)))
            return pnts

        fpus, slicePositions = zip(*self.frames)
        fs, ps, us = zip(*fpus)
        
        interpFs = interpolate_tup3(fs)
        interpPs = interpolate_tup3(ps)
        interpUs = interpolate_tup3(us)
        interpFPUs = zip(interpFs,interpPs,interpUs)


        im = self.view3.imageManager
        if im.using_planes():
        
            slicex, slicey, slicez = zip(*slicePositions)

            o, p1, p2 = zip(*slicex)
            interpo = interpolate_tup3(o)
            interpp1 = interpolate_tup3(p1)
            interpp2 = interpolate_tup3(p2)
            interpx = zip(interpo,interpp1,interpp2)

            o, p1, p2 = zip(*slicey)
            interpo = interpolate_tup3(o)
            interpp1 = interpolate_tup3(p1)
            interpp2 = interpolate_tup3(p2)
            interpy = zip(*(interpo,interpp1,interpp2))

            o, p1, p2 = zip(*slicez)
            interpo = interpolate_tup3(o)
            interpp1 = interpolate_tup3(p1)
            interpp2 = interpolate_tup3(p2)
            interpz = zip(interpo,interpp1,interpp2)

            interpSlices = zip(interpx, interpy, interpz)

        else:
            interpSlices = [None]*len(interpFPUs)
        self.interpFrames =  zip(interpFPUs, interpSlices)
        simple_msg('%d frames created; read to play!' % len(self.interpFrames))
        
        

    def set_frame(self, frame):
        fpu, slicePos = frame
        camera = self.view3.renderer.GetActiveCamera()
        focal, pos, up = fpu
        camera.SetFocalPoint(focal)
        camera.SetPosition(pos)
        camera.SetViewUp(up)

        im = self.view3.imageManager



        if slicePos is not None:
            slicex, slicey, slicez = slicePos
            o,p1,p2 = slicex
            im.pwX.SetOrigin(o)
            im.pwX.SetPoint1(p1)
            im.pwX.SetPoint2(p2)
            im.pwX.UpdatePlacement()

            o,p1,p2 = slicey
            im.pwY.SetOrigin(o)
            im.pwY.SetPoint1(p1)
            im.pwY.SetPoint2(p2)
            im.pwY.UpdatePlacement()

            o,p1,p2 = slicez
            im.pwZ.SetOrigin(o)
            im.pwZ.SetPoint1(p1)
            im.pwZ.SetPoint2(p2)
            im.pwZ.UpdatePlacement()

        self.view3.renderer.ResetCameraClippingRange()
        self.view3.interactor.Render()

    def forward(self, *args):
        if (self.buttonUseRotation.get_active() and
            self.interpFrames is  None):  
            self.interpolate_frames()
            
        self.stop()
        good = self.setpars()
        if not good: return gtk.FALSE
        self.direction = 1
        self.idleID = gtk.idle_add(self.scroll)
        
    def scroll(self, *args):


        basename = '%s%05d' % (self.entryMovie.get_text(), self.ind)
        self.update_status_bar()
        
        if self.ind<0 or self.ind>=len(self.steps):
            self.stop()
            self.ind=0
            return gtk.FALSE
        
        # we're still playing
        thisMin = self.steps[self.ind]
        thisMax = thisMin + self.twidth
        self.broadcast(Observer.SET_TIME_LIM, thisMin, thisMax)

        # do the rotate interpolation for view3
        if self.buttonUseRotation.get_active():
            numSteps = self.entryPerTime.get_value_as_int()
            ind0 = self.ind*numSteps
            for i in range(numSteps):
                print 'Setting frame %d of %d' % (ind0+i, len(self.interpFrames))
                self.set_frame(self.interpFrames[ind0+i])
                fname = '%s_interp%04d' % (basename, i)
                if i< numSteps-1:
                    self.view3.recieve(Observer.SAVE_FRAME, fname)
        else:
            fname = basename

        # notify the observers
        if self.checkButtonMovie.get_active():
            self.broadcast(Observer.SAVE_FRAME, fname)
        self.ind += self.direction
        return gtk.TRUE

class ScalarMapper:
    """
    Classes that provide data to the grid manager

    The derived classes are responsible for loading data and building
    the electrode->scalar maps required by GridManager.set_scalar_data
    """
    SCROLLBARSIZE = 150,20
    def __init__(self, gridManager):
        self.gridManager = gridManager


class ArrayMapper(gtk.Window, ScalarMapper):

    def __init__(self, gridManager, X, channels, amp):
        ScalarMapper.__init__(self, gridManager)
        gtk.Window.__init__(self)
        self.set_title('Array data')


        self.channels = channels        
        self.amp = amp
        self.trodes = [(gname, gnum) for cnum, gname, gnum in amp]
        self.X = X


        self.numChannels, self.numSamples = X.shape
        
        vbox = gtk.VBox()
        vbox.show()
        self.add(vbox)

        self.fig = self.make_fig()


        self.canvas = FigureCanvas(self.fig)  # a gtk.DrawingArea
        self.canvas.show()
        vbox.pack_start(self.canvas, gtk.TRUE, gtk.TRUE)        

        hbox = gtk.HBox()
        hbox.show()
        vbox.pack_start(hbox, gtk.FALSE, gtk.FALSE)        

        label = gtk.Label('Sample num')
        label.show()
        hbox.pack_start(label, gtk.FALSE, gtk.FALSE)

        scrollbar = gtk.HScrollbar()
        scrollbar.show()
        hbox.pack_start(scrollbar, gtk.TRUE, gtk.TRUE)
        scrollbar.set_range(0, self.numSamples-1)
        scrollbar.set_increments(1,1)
        scrollbar.set_value(self.numSamples//2)
        scrollbar.connect('value_changed', self.set_sample_num)
        self.scrollbarIndex = scrollbar

        toolbar = NavigationToolbar(self.canvas, self)
        toolbar.show()
        vbox.pack_start(toolbar, gtk.FALSE, gtk.FALSE)

        self.set_sample_num(scrollbar)

    def set_sample_num(self, bar):
        ind = int(bar.get_value())
        datad = self.get_datad(ind)
        self.gridManager.set_scalar_data(datad)
        xdata = array([ind, ind], typecode=Float)
        for line in self.lines:
            line.set_xdata(xdata)
        self.canvas.draw()


    def get_datad(self, ind):
        
        slice = self.X[:,ind]
        datad = dict(zip(self.trodes, slice))
        return datad

    def make_fig(self):
        

        fig = Figure(figsize=(7,5), dpi=72)
        self.lines = []
        N = len(self.channels)
        for i, channel in enumerate(self.channels):
            ax = fig.add_subplot(N, 1, i+1)
            x = self.X[channel-1,:]
            ax.plot(arange(self.numSamples), x)
            ax.grid(True)
            mid = self.numSamples/2.0
            line = ax.plot([mid, mid], [min(x), max(x)])[0]
            ax.add_line(line)
            ax.set_ylabel('Chan #%d' % channel)
            self.lines.append(line)
            if ax.is_last_row(): ax.set_xlabel('index')
            if ax.is_first_row(): ax.set_title('Evoked response')

            
        return fig


class AmpDialog(gtk.Dialog):
    def __init__(self, channels):
        gtk.Dialog.__init__(self, 'Channel num to electrode mapping')

        self.channels = channels
        self.numChannels = len(channels)
        
        self.set_size_request(300,600)
        scrolledWin = gtk.ScrolledWindow()
        scrolledWin.show()
        self.vbox.pack_start(scrolledWin, gtk.TRUE, gtk.TRUE)

        vbox = gtk.VBox()
        vbox.show()
        scrolledWin.add_with_viewport(vbox)        

        table=gtk.Table(self.numChannels+1, 3)
        table.set_col_spacings(3)
        table.show()
        vbox.pack_start(table, gtk.TRUE, gtk.TRUE)

        labelCnum = gtk.Label('Channel')
        labelCnum.show()

        labelName = gtk.Label('Grid name')
        labelName.show()
        labelNum = gtk.Label('Grid num')
        labelNum.show()

        table.attach(labelCnum, 0, 1, 0, 1,
                     xoptions=gtk.FALSE, yoptions=gtk.FALSE)
        table.attach(labelName, 1, 2, 0, 1,
                     xoptions=gtk.FALSE, yoptions=gtk.FALSE)
        table.attach(labelNum, 2, 3, 0, 1,
                     xoptions=gtk.FALSE, yoptions=gtk.FALSE)
        entries = []
        for i,cnum in enumerate(channels):
            label = gtk.Label('%d' % cnum)
            label.show()
            entryName = gtk.Entry()
            entryName.show()
            entryName.set_width_chars(10)
            entryNum = gtk.Entry()
            entryNum.show()
            entryNum.set_width_chars(10)
            table.attach(label, 0, 1, i+1, i+2,
                         xoptions=gtk.FALSE, yoptions=gtk.FALSE)
            table.attach(entryName, 1, 2, i+1, i+2,
                         xoptions=gtk.FALSE, yoptions=gtk.FALSE)
            table.attach(entryNum, 2, 3, i+1, i+2,
                         xoptions=gtk.FALSE, yoptions=gtk.FALSE)
            entries.append((label, entryName, entryNum))

        self.entries = entries
            
        frame = gtk.Frame('Auto fill')
        frame.show()
        vbox.pack_start(frame, gtk.TRUE, gtk.TRUE)
        frame.set_border_width(5)

        vboxFrame = gtk.VBox()
        vboxFrame.show()
        frame.add(vboxFrame)
        
        table = gtk.Table(2,3)
        table.set_col_spacings(3)
        table.set_row_spacings(3)
        table.show()
        vboxFrame.pack_start(table, gtk.TRUE, gtk.TRUE)
        
        label = gtk.Label('Grid name')
        label.show()
        entryGname = gtk.Entry()
        entryGname.show()
        entryGname.set_width_chars(10)
        table.attach(label, 0, 1, 0, 1,
                     xoptions=gtk.FALSE, yoptions=gtk.FALSE)
        table.attach(entryGname, 0, 1, 1, 2,
                     xoptions=gtk.FALSE, yoptions=gtk.FALSE)

        labelStart = gtk.Label('Chan# Start')
        labelStart.show()
        entryStart = gtk.Entry()
        entryStart.show()
        entryStart.set_width_chars(10)
        entryStart.set_text('1')
        
        table.attach(labelStart, 1, 2, 0, 1,
                     xoptions=gtk.FALSE, yoptions=gtk.FALSE)
        table.attach(entryStart, 1, 2, 1, 2,
                     xoptions=gtk.FALSE, yoptions=gtk.FALSE)

        labelEnd = gtk.Label('Chan# End')
        labelEnd.show()
        entryEnd = gtk.Entry()
        entryEnd.show()
        entryEnd.set_width_chars(10)
        entryEnd.set_text('%d'%len(entries))
        
        table.attach(labelEnd, 2, 3, 0, 1,
                     xoptions=gtk.FALSE, yoptions=gtk.FALSE)
        table.attach(entryEnd, 2, 3, 1, 2,
                     xoptions=gtk.FALSE, yoptions=gtk.FALSE)

        def fill_it(button):
            gname = entryGname.get_text()
            cstart = str2int_or_err(entryStart.get_text(), labelStart, parent=self)

            if cstart is None: return
            cend = str2int_or_err(entryEnd.get_text(), labelEnd, parent=self)
            if cend is None: return

            cnt = 1

            if cend>len(entries):
                #TODO: i not defined
                error_msg('Channel #%d out of range' % i, parent=self)
                return


            for i in range(cstart, cend+1):
                label, ename, enum = entries[i-1]
                ename.set_text(gname)
                enum.set_text('%d'%cnt)
                cnt += 1
            
        button = gtk.Button(stock=gtk.STOCK_EXECUTE)
        button.show()
        vboxFrame.pack_start(button, gtk.FALSE, gtk.FALSE)

        button.connect('clicked', fill_it)


        self.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        self.add_button(gtk.STOCK_OK, gtk.RESPONSE_OK)

    def get_amp(self):
        
        while 1:
            response = self.run()

            if response==gtk.RESPONSE_OK:
                trodes = []
                for i, tup in enumerate(self.entries):
                    label, ename, enum = tup
                    gname = ename.get_text()
                    if not len(gname):
                        error_msg('Empty grid name on channel %d' % i+1, parent=self)
                        break
                    gnum = str2int_or_err(enum.get_text(), label, parent=self)
                    if gnum is None: break
                    trodes.append( (i+1, gname, gnum) )
                else:
                    self.hide()
                    amp = Amp()
                    amp.extend(trodes)
                    return amp
            else:
                self.hide()
                return
                    

                
                
        



class ImageManager:
    SCROLLBARSIZE = 150,20
    def __init__(self, interactor, renderer):
        self.interactor = interactor
        self.renderer = renderer
        self.pwX = vtk.vtkImagePlaneWidget()        
        self.pwY = vtk.vtkImagePlaneWidget()        
        self.pwZ = vtk.vtkImagePlaneWidget()
        self._usingPlanes = False
        self.readerDlg = imageReaderWidgets['dlgReader']
        self.propsDlg = self.make_prop_dialog()
        
    def show_prefs(self, *args):
        self.propsDlg.show()


    def load_image_dialog(self, *args):                
        response = self.readerDlg.run()

        if response == gtk.RESPONSE_OK:
            try: reader = imageReaderWidgets.reader
            except AttributeError: 
                pars = imageReaderWidgets.get_params()
                pars = imageReaderWidgets.validate(pars)
                if pars is None:
                    error_msg('Could not validate the parameters',
                              self.readerDlg)
                    return
                reader = imageReaderWidgets.get_reader(pars)

            imageData = reader.GetOutput()
            imageData.SetSpacing(reader.GetDataSpacing())
            self.imageData = imageData
            self.load_image_data()
        else:
            imageData = None
        self.readerDlg.hide()


    def load_image_data(self, *args):

        if self.imageData is None: return 
        self.pwxyz = PlaneWidgetsXYZ(self.imageData)
        self.pwxyz.show()

        extent = self.imageData.GetExtent()
        frac = 0.3

        self._plane_widget_boilerplate(
            self.pwX, key='x', color=(1,0,0),
            index=frac*(extent[1]-extent[0]),
            orientation=0)

        self._plane_widget_boilerplate(
            self.pwY, key='y', color=(1,1,0),
            index=frac*(extent[3]-extent[2]),
            orientation=1)
        self.pwY.SetLookupTable(self.pwX.GetLookupTable())

        self._plane_widget_boilerplate(
            self.pwZ, key='z', color=(0,0,1),
            index=frac*(extent[5]-extent[4]),
            orientation=2)
        self.pwZ.SetLookupTable(self.pwX.GetLookupTable())        
        self.pwX.SetResliceInterpolateToCubic()
        self.pwY.SetResliceInterpolateToCubic()
        self.pwZ.SetResliceInterpolateToCubic()
        self.camera = self.renderer.GetActiveCamera()

        center = self.imageData.GetCenter()
        spacing = self.imageData.GetSpacing()
        bounds = self.imageData.GetBounds()
        pos = center[0], center[1], center[2] - max(bounds)*2
        fpu = center, pos, (0,-1,0)
        self.set_camera(fpu)
        self.set_interact()
        self._usingPlanes = True

    def using_planes(self):
        return self._usingPlanes

    def _plane_widget_boilerplate(self, pw, key, color, index, orientation):

        pw.TextureInterpolateOn()
        #pw.SetResliceInterpolateToCubic()
        pw.SetKeyPressActivationValue(key)
        pw.GetPlaneProperty().SetColor(color)
        pw.DisplayTextOn()
        pw.SetInput(self.imageData)
        pw.SetPlaneOrientation(orientation)
        pw.SetSliceIndex(int(index))
        pw.SetInteractor(self.interactor)
        pw.On()
        pw.UpdatePlacement()

    def set_camera(self, fpu):
        camera = self.renderer.GetActiveCamera()
        focal, position, up = fpu
        camera.SetFocalPoint(focal)
        camera.SetPosition(position)
        camera.SetViewUp(up)
        self.renderer.ResetCameraClippingRange()
        self.interactor.Render()

    def set_interact(self, *args):
        'b is a boolean'
        if self.imageData is None: return

        if self.buttonInteract.get_active():
            self.pwX.InteractionOn()
            self.pwY.InteractionOn()
            self.pwZ.InteractionOn()
        else:
            self.pwX.InteractionOff()
            self.pwY.InteractionOff()
            self.pwZ.InteractionOff()


    def make_prop_dialog(self):

        dlg = gtk.Dialog('Image data properties')

        vbox = dlg.vbox

        button = ButtonAltLabel('Info file', gtk.STOCK_OPEN)
        button.show()
        vbox.pack_start(button, gtk.FALSE, gtk.FALSE)
        button.connect('clicked', self.load_image_dialog)


        button = gtk.CheckButton('Interact with planes')
        button.show()
        vbox.pack_start(button, gtk.FALSE, gtk.FALSE)
        button.set_active(False)
        button.connect('toggled', self.set_interact)
        self.buttonInteract = button

        frame = gtk.Frame('Opacity')
        frame.show()
        frame.set_border_width(5)
        vbox.pack_start(frame, gtk.TRUE, gtk.TRUE)



        table = gtk.Table(4,2)
        table.set_homogeneous(gtk.FALSE)
        table.show()
        frame.add(table)
        
        table.set_col_spacings(3)
        table.set_row_spacings(3)
        table.set_border_width(3)
        
        class OpacityScrollbar(gtk.HScrollbar):
            render = True
            interactor = self.interactor
            SCROLLBARSIZE = self.SCROLLBARSIZE
            def __init__(self, labelStr, pw, row):
                self.pw = pw
                label = gtk.Label(labelStr)
                label.show()

                scrollbar = gtk.HScrollbar()
                scrollbar.show()
                scrollbar.set_range(0, 1)
                scrollbar.set_increments(0.05,0.25)
                scrollbar.set_value(1)
                scrollbar.set_size_request(*self.SCROLLBARSIZE)
                self.scrollbar = scrollbar
                scrollbar.connect('value_changed', self.set_opacity)

                table.attach(label, 0, 1, row, row+1,
                             xoptions=gtk.FALSE, yoptions=gtk.FALSE)
                table.attach(scrollbar, 1, 2, row, row+1,
                             xoptions=gtk.TRUE, yoptions=gtk.FALSE)

            def set_opacity(self, *args):
                val = self.scrollbar.get_value()
                self.pw.GetTexturePlaneProperty().SetOpacity(val)
                self.pw.GetPlaneProperty().SetOpacity(val)
                if self.render: self.interactor.Render()

        xScroll = OpacityScrollbar('X', self.pwX, 0)
        yScroll = OpacityScrollbar('Y', self.pwY, 1)
        zScroll = OpacityScrollbar('Z', self.pwZ, 2)
        row = 3


        label = gtk.Label('All')
        label.show()

        scrollbar = gtk.HScrollbar()
        scrollbar.show()
        scrollbar.set_range(0, 1)
        scrollbar.set_increments(0.05,0.25)
        scrollbar.set_value(1)

        def set_all_opacity(bar):
            xScroll.render=False
            yScroll.render=False
            zScroll.render=False
            val = bar.get_value()
            xScroll.scrollbar.set_value(val)
            yScroll.scrollbar.set_value(val)
            zScroll.scrollbar.set_value(val)
            xScroll.render=True
            yScroll.render=True
            zScroll.render=True
            self.interactor.Render()
            
        scrollbar.connect('value_changed', set_all_opacity)
        scrollbar.set_size_request(150,20)

        table.attach(label, 0, 1, row, row+1,
                     xoptions=gtk.FALSE, yoptions=gtk.FALSE)
        table.attach(scrollbar, 1, 2, row, row+1,
                     xoptions=gtk.TRUE, yoptions=gtk.FALSE)



        def hide(button):
            dlg.hide()
            return gtk.TRUE
        
        button = ButtonAltLabel('Hide', gtk.STOCK_CANCEL)
        button.show()
        button.connect('clicked', hide)
        vbox.pack_end(button, gtk.FALSE, gtk.FALSE)        

        return dlg




class GridManager:
    SCROLLBARSIZE = 150,20
    def __init__(self, interactor, renderer, infile, dimensiond=None):
        
        self.interactor = interactor
        self.renderer = renderer

        self.gridActors = {}  # dict from name -> grid or ribbon actors
        self.ribbons = {}     # dict from name -> ribbon actor
        self.surfs = {}       # dict from name -> surf actor
        self.normalActors = []
        self.markers = []
        self.textActors = []
        self.tubeActors = []
        self.dimensiond = dimensiond
        self.scalarSet = []        
        self.scalarVals = []
        self.dlgDim = None
        self.dlgProp = None
        self.vtkIDs = {}  # a map from name, num -> vtkID
        ok = self.load_markers(infile)

        # a set of gridnames where we have wanred if can't build grid
        self.gridWarned = Set()  
        self.markerFilename = None
        self.ok = ok

        self.ampAscii  = None  # an ampfile for ascii data
        
    def markers_as_collection(self):
        markers = vtk.vtkActorCollection()
        for marker in self.markers:
            markers.AddItem(marker)
        return markers
    
    def set_scalar_data(self, datad):
        """
        data d is a dict from (gname, gnum) -> scalar

        Plot the data on the grids using surface interpolation
        """

        self.scalarVals.extend([val for key, val in datad.items()])
        if self.dimensiond is None:
            self.scalarSet.append(datad)
            return

        
        
        named = {}

        for tup, val in datad.items():
            gname, gnum = tup
            
            named.setdefault(gname, []).append((gnum, val))


        rangeSet = self.get_scalar_range()
        if rangeSet is not None:
            minVal, maxVal = rangeSet
            
        
        for name in self.get_grid1_names():
            items = named.get(name, None)
            if items is None: continue
            items.sort()



            polydata, actor, filter, markers = self.ribbons[name]
            if len(markers)!=len(items):
                if name not in self.gridWarned:
                    simple_msg('Some missing scalar data for grid %s.  %d markers and %d scalars' % (name, len(markers), len(items)))
                self.gridWarned.add(name)

            scalars = vtk.vtkFloatArray()
            for num, val in items:
                vtkID = self.vtkIDs[(name, num)]
                scalars.InsertValue(vtkID, val)
            polydata.GetPointData().SetScalars(scalars)

            if rangeSet is not None:
                #pass
                actor.GetMapper().SetScalarRange(minVal, maxVal)
                    
                    

                
        for name in self.get_grid2_names():
            items = named.get(name, None)
            if items is None: continue
            items.sort()

            grid, actor, filter, markers = self.surfs[name]

            if len(markers)!=len(items):
                if name not in self.gridWarned:
                    simple_msg('Missing some scalar data for grid %s.  %d markers and %d scalars' % (name, len(markers), len(items)))
                self.gridWarned.add(name)


            scalars = vtk.vtkFloatArray()
            for num, val in items:
                vtkID = self.vtkIDs.get((name, num))
                if vtkID is None: continue
                scalars.InsertValue(vtkID, val)
            grid.GetPointData().SetScalars(scalars)
            if rangeSet is not None:
                mapper = actor.GetMapper()
                if 1:
                    mapper.SetColorModeToMapScalars()
                    mapper.SetScalarRange(minVal, maxVal)
                else:
                    mapper.SetColorModeToMapScalars()
                    lut = mapper.GetLookupTable()
                    lut.SetRange(minVal, maxVal)
        self.interactor.Render()
            
    def flush(self):
        for actor in self.normalActors:
            self.renderer.RemoveActor(actor)
        for actor in self.gridActors.values():
            self.renderer.RemoveActor(actor)            
        for actor in self.markers:
            self.renderer.RemoveActor(actor)
        for actor in self.textActors:
            self.renderer.RemoveActor(actor)

        self.flush_connections()
            
        self.gridActors = {}  # dict from name -> grid or ribbon actors
        self.ribbons = {}  # dict from name -> ribbon actor
        self.surfs = {}    # dict from name -> surf actor
        self.normalActors = []
        self.markers = []
        self.textActors = []
        self.dimensiond = None
        self.scalarSet = []
        self.scalarVals = []
        self.interactor.Render()
        self.vtkIDs = {}
        
    def flush_connections(self):
        for actor in self.tubeActors:
            self.renderer.RemoveActor(actor)
        self.tubeActors = []
        
    def connect_markers(self, e1, e2, relHeight=0.25, lineWid=0.05,
                        scalarfunc=identity, radiusFactor=10):
        """
        Draw a line connecting electode1 with electrode2 (gname, gnum)
        tuples. scalarfunc sets the scalar values of the connecting
        arc as a function of the frac of distance between them (use
        none for homogenous line)
        """
        m1 = self.markerd.get(e1)
        m2 = self.markerd.get(e2)

        if m1 is None:  err = '%s %d' % e1
        elif m2 is None: err = '%s %d' % e2
        else: err = None
        if err is not None:
            error_msg('No marker with label %s' % err)
            return False
        
        p1 = array(m1.get_center())
        p2 = array(m2.get_center())
        d = dist(p1,p2)
        midp = 0.5*(p1+p2)

        try:
            n1 = m1.normal
            n2 = m2.normal
        except AttributeError: return False

        normal = 0.5*(n1+n2)
        vtk.vtkMath.Normalize(normal)

        p3 = midp + relHeight*d*normal
        #p3 = midp

        aSplineX = vtk.vtkCardinalSpline()
        aSplineY = vtk.vtkCardinalSpline()
        aSplineZ = vtk.vtkCardinalSpline()


        aSplineX.AddPoint(0, p1[0])
        aSplineX.AddPoint(1, p3[0])
        aSplineX.AddPoint(2, p2[0])

        aSplineY.AddPoint(0, p1[1])
        aSplineY.AddPoint(1, p3[1])
        aSplineY.AddPoint(2, p2[1])

        aSplineZ.AddPoint(0, p1[2])
        aSplineZ.AddPoint(1, p3[2])
        aSplineZ.AddPoint(2, p2[2])

        numInPnts = 3
        numOutPnts = 20

        # Interpolate x, y and z by using the three spline filters and
        # create new points
        points = vtk.vtkPoints()
        scalars = vtk.vtkFloatArray()

        for i in range(numOutPnts):
            t = (numInPnts-1.0)/(numOutPnts-1.0)*i
            points.InsertPoint(
                i, aSplineX.Evaluate(t), aSplineY.Evaluate(t), aSplineZ.Evaluate(t))
            if scalarfunc is not None:
                scalars.InsertTuple1(i,scalarfunc(t/(numInPnts-1.0)))

        # Create the polyline.
        lines = vtk.vtkCellArray()
        lines.InsertNextCell(numOutPnts)
        for i in range(numOutPnts):
            lines.InsertCellPoint(i)

        polyData = vtk.vtkPolyData()
        polyData.SetPoints(points)
        polyData.SetLines(lines)
        if scalarfunc is not None:
            polyData.GetPointData().SetScalars(scalars)

        # Add thickness to the resulting line.
        filter = vtk.vtkTubeFilter()
        filter.SetNumberOfSides(8)
        filter.SetInput(polyData)


        #if scalarfunc is not None:
        #    # Vary tube thickness with scalar
        #    filter.SetRadius(lineWid*m1.get_size())
        #    filter.SetRadiusFactor(radiusFactor)
        #    #filter.SetVaryRadiusToVaryRadiusByScalar()
        #else:
        #    filter.SetRadius(0.75*radiusFactor*lineWid*m1.get_size())
        filter.SetRadius(0.75*radiusFactor*lineWid*m1.get_size())

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInput(filter.GetOutput())
        #Set this to Off to turn off color variation with scalar
        if scalarfunc is not None:
            mapper.ScalarVisibilityOn()
            #mapper.SetScalarRange(0,t)   

        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetSpecular(.3)
        actor.GetProperty().SetSpecularPower(30)
        self.renderer.AddActor(actor)
        self.tubeActors.append(actor)
        
        return True
            
    def load_markers(self, infile):
        self.flush()
        infile.seek(0)
        try: self.markers = [Marker.from_string(line) for line in infile]
        except ValueError:
            msg = exception_to_str('Could not parse marker file')
            error_msg(msg)
            return
        
        self.markerd = dict([ (m.get_name_num(), m) for m in self.markers])

        self._add_markers(self.markers)
            
        self.interactor.Render()

        if self.dlgDim is not None: self.dlgDim.destroy()
        if self.dlgProp is not None: self.dlgProp.destroy()

        self.dlgDim, self.dlgDimEntries = self.make_dim_dialog()
        self.dlgProp = self.make_prop_dialog()

        for datad in self.scalarSet:
            self.set_scalar_data(datad)
        self.renderer.ResetCamera()
        self.interactor.Render()

        return True

    def _add_markers(self, markers):
        textActors = []
        for marker in markers:
            text = vtk.vtkVectorText()
            text.SetText(marker.get_label())
            textMapper = vtk.vtkPolyDataMapper()
            textMapper.SetInput(text.GetOutput())

            textActor = vtk.vtkFollower()
            textActor.SetMapper(textMapper)
            size = marker.get_size()
            textActor.SetScale(size, size, size)
            x,y,z = marker.get_center()
            textActor.SetPosition(x+size, y+size, z+size)
            camera = self.renderer.GetActiveCamera()
            textActor.SetCamera(camera)
            textActor.GetProperty().SetColor(marker.get_label_color())
            #textActor.VisibilityOff()
            textActors.append(textActor)

            self.renderer.AddActor(textActor)
            self.renderer.AddActor(marker)

        self.textActors = textActors

    def show(self, *args):
        self.dlgProp.show()

        # set defaults for scalar range

        tup = self.get_scalar_range()
        if tup is not None:
            minVal, maxVal = tup

            smin = self.entryScalarMin.get_text()
            if not smin:
                self.entryScalarMin.set_text('%1.2f'%minVal)
            smax = self.entryScalarMax.get_text()
            if not smin:
                self.entryScalarMax.set_text('%1.2f'%maxVal)


    def _update_frames(self):

        'Update the frames fo the main dialog'
        

        """
        #todo: change grid file is broken on the remove with
        (grid_manager_test.py:13237): Gtk-CRITICAL **: file
        gtkcontainer.c: line 981 (gtk_container_remove): assertion
        `widget->parent == GTK_WIDGET (container)' failed"""

        try: self.tableOpacity
        except AttributeError: pass
        else: self.frameOpacity.remove(self.tableOpacity)
        self.tableOpacity = self._make_opacity_table()
        self.frameOpacity.add(self.tableOpacity)

        try: self.vboxNormals
        except AttributeError: pass
        else: self.frameNormals.remove(self.vboxNormals)
        self.vboxNormals = self._make_normals_vbox()
        self.frameNormals.add(self.vboxNormals)

        # call this after normals vbox since we need to know about the
        # flip button
        try: self.tableAngle
        except AttributeError: pass
        else: self.frameAngle.remove(self.tableAngle)
        self.tableAngle = self._make_strip_angle_table()
        self.frameAngle.add(self.tableAngle)

    def get_scalar_range(self):

        minVal, maxVal = None, None
        
        if len(self.scalarVals): 
            minVal = min(self.scalarVals)
            maxVal = max(self.scalarVals)
            
        smin = self.entryScalarMin.get_text()
        smax = self.entryScalarMax.get_text()
        if len(smin):
            try: minVal = float(smin)
            except ValueError:
                error_msg('Illegal floating point value "%s" for minimum scalar range.  Please fix it in the preferences dialog'%smin)
                return
        if len(smax):
            try: maxVal = float(smax)
            except ValueError:
                error_msg('Illegal floating point value "%s"for maximum scalar range.  Please fix it in the preferences dialog'%smax)
                return

        if minVal is None or maxVal is None: return None
        return minVal, maxVal
        
    def make_prop_dialog(self):

        
        if self.dimensiond is None:
            results = self.get_dimensions()

        def hide(*args):
            dlg.hide()
            return gtk.TRUE
        dlg = gtk.Dialog('Grid properties')
        # intercept delete events
        dlg.connect('delete_event', hide)
        
        notebook = gtk.Notebook()
        notebook.show()
        dlg.vbox.pack_start(notebook, gtk.TRUE, gtk.TRUE)

        frame = gtk.Frame('Strip angle')
        frame.show()
        frame.set_border_width(5)
        label = gtk.Label('Strips')
        label.show()
        notebook.append_page(frame, label)
        self.frameAngle = frame

        frame = gtk.Frame('Grid normals')
        frame.show()
        frame.set_border_width(5)
        label = gtk.Label('Normals')
        label.show()
        notebook.append_page(frame, label)
        self.frameNormals = frame
        

        frame = gtk.Frame('Opacity')
        frame.show()
        frame.set_border_width(5)
        label = gtk.Label('Opacity')
        label.show()
        notebook.append_page(frame, label)
        self.frameOpacity = frame



        vboxMappers = gtk.VBox()
        vboxMappers.show()
        label = gtk.Label('Scalar data')
        label.show()
        notebook.append_page(vboxMappers, label)
        
        frame = gtk.Frame('Scalar Range')
        frame.show()
        frame.set_border_width(5)
        vboxMappers.pack_start(frame, gtk.FALSE, gtk.FALSE)

        frameVBox = gtk.VBox()
        frameVBox.show()
        frameVBox.set_spacing(3)
        frame.add(frameVBox)


        hbox = gtk.HBox()
        hbox.set_spacing(3)
        hbox.show()
        frameVBox.pack_start(hbox, gtk.FALSE, gtk.FALSE)
        
        label = gtk.Label('Min/Max')
        label.show()
        
        hbox.pack_start(label, gtk.FALSE, gtk.FALSE)


        self.entryScalarMin = gtk.Entry()
        self.entryScalarMin.show()
        self.entryScalarMin.set_width_chars(10)
        hbox.pack_start(self.entryScalarMin, gtk.FALSE, gtk.FALSE)

        
        self.entryScalarMax = gtk.Entry()
        self.entryScalarMax.show()
        self.entryScalarMax.set_width_chars(10)
        hbox.pack_start(self.entryScalarMax, gtk.FALSE, gtk.FALSE)


        hbox = gtk.HBox()
        hbox.set_spacing(3)
        hbox.show()
        frameVBox.pack_start(hbox, gtk.FALSE, gtk.FALSE)

        def set_range(button):
            tup = self.get_scalar_range()
            if tup is None: return
            minVal, maxVal = tup

            for grid, actor, filter, markers in self.surfs.values():
                actor.GetMapper().SetScalarRange(minVal, maxVal)
            for polydata, actor, filter, markers in self.ribbons.values():
                actor.GetMapper().SetScalarRange(minVal, maxVal)
            self.interactor.Render()
            
                
        button = gtk.Button(stock=gtk.STOCK_APPLY)
        button.show()
        hbox.pack_start(button, gtk.TRUE, gtk.TRUE)
        button.connect('clicked', set_range)

        def autoset(button):
            if not len(self.scalarVals):
                error_msg('No scalar data set')
                return
            
            minVal = min(self.scalarVals)
            maxVal = max(self.scalarVals)
            self.entryScalarMin.set_text('%1.2f'%minVal)
            self.entryScalarMax.set_text('%1.2f'%maxVal)
            set_range(None)
            
        button = ButtonAltLabel('Auto', gtk.STOCK_EXECUTE)
        button.show()
        button.connect('clicked', autoset)
        hbox.pack_start(button, gtk.TRUE, gtk.TRUE)

        frame = gtk.Frame('Scalars from ASCII file')
        frame.show()
        frame.set_border_width(5)
        vboxMappers.pack_start(frame, gtk.FALSE, gtk.FALSE)

        frameVBox = gtk.VBox()
        frameVBox.show()
        frameVBox.set_spacing(3)
        frame.add(frameVBox)

        def load_ascii_data(filename):
            try: fh = file(filename)
            except IOError, msg:
                msg = exception_to_str('Could not open %s' % filename)
                error_msg(msg, parent=dlg)
                return

            try:
                numHeaderLines = str2int_or_err(
                    entryHeader.get_text(), labelHeader, parent=dlg)
                if numHeaderLines is None: return

                # skip the header lines
                for i in range(numHeaderLines):
                    fh.readline()

                X = []
                for line in fh:
                    vals = [float(val) for val in line.split()]
                    X.append(vals)
            except:
                msg = exception_to_str('Error parsing %s' % filename)
                error_msg(msg, parent=dlg)
                return

            if buttonSampChan.get_active():
                # transpose the data to channels x samples
                X = array(zip(*X), typecode=Float)
            else:
                X = array(X, typecode=Float)

            numChannels, numSamples = X.shape
            self.X = X


            ampDlg = AmpDialog([(i+1) for i in range(numChannels)])
            ampDlg.show()
            amp = ampDlg.get_amp()
            if amp is None: return
            self.ampAscii = amp
           
        def set_filename(button):

            filename = fmanager.get_filename()
            if filename is None: return
            if not os.path.exists(filename):
                error_msg('File %s does not exist' % filename, parent=dlg)
                return
            entryAsciiFile.set_text(filename)
            load_ascii_data(filename)

        def doit(button):
            s = entryChannels.get_text()
            if not len(s):
                simple_msg('Please select channels: format like 1 2 3',
                           parent=dlg)
                return
        
            try: channels = [int(val) for val in s.split()]
            except ValueError:
                error_msg('Could not convert %s to a list of integers.  Use format like: 1 12 54' % s, parent=dlg)
                return

            filename = entryAsciiFile.get_text()
            if not filename:
                error_msg('You must first set the filename', parent=dlg)
                return

            
            if self.ampAscii is None:
                error_msg('No valid channel->electrode map', parent=dlg)
                return
            if not len(self.X):
                error_msg('No ascii data loaded', parent=dlg)
                return

            
            am = ArrayMapper(self, self.X, channels, self.ampAscii)
            am.show()

        def radio_changed(button):
            filename = entryAsciiFile.get_text()
            if not filename:
                set_filename(button=None)
            else:
                load_ascii_data(filename)
                
                
        radioGrp = None
        button = gtk.RadioButton(radioGrp)
        button.set_label('Samples x Channels')
        button.set_active(True)
        button.show()
        button.connect('clicked', radio_changed)
        frameVBox.pack_start(button, gtk.TRUE, gtk.TRUE)
        buttonSampChan = button
        
        button = gtk.RadioButton(button)
        button.set_label('Channels x Samples')
        button.show()
        frameVBox.pack_start(button, gtk.TRUE, gtk.TRUE)
        buttonChanSamp = button

        hbox = gtk.HBox()
        hbox.show()
        hbox.set_spacing(3)
        frameVBox.pack_start(hbox, gtk.TRUE, gtk.TRUE)

        label = gtk.Label('Header lines')
        label.show()
        labelHeader = label
        hbox.pack_start(label, gtk.FALSE, gtk.FALSE)
        entry = gtk.Entry()
        entry.show()
        entry.set_text('0')
        entry.set_width_chars(5)
        hbox.pack_start(entry, gtk.FALSE, gtk.FALSE)
        entryHeader = entry

        hbox = gtk.HBox()
        hbox.show()
        hbox.set_spacing(3)
        frameVBox.pack_start(hbox, gtk.TRUE, gtk.TRUE)

        label = gtk.Label('Channels')
        label.show()
        hbox.pack_start(label, gtk.FALSE, gtk.FALSE)
        entry = gtk.Entry()
        entry.show()
        entry.set_text('1 2 3')
        hbox.pack_start(entry, gtk.FALSE, gtk.FALSE)
        entryChannels = entry

        hbox = gtk.HBox()
        hbox.show()
        hbox.set_spacing(3)
        frameVBox.pack_start(hbox, gtk.TRUE, gtk.TRUE)

        self.ampAscii = None
        self.X = []

            
        button = gtk.Button(stock=gtk.STOCK_OPEN)
        button.show()
        button.connect('clicked', set_filename)
        hbox.pack_start(button, gtk.FALSE, gtk.FALSE)
        entry = gtk.Entry()
        entry.show()
        hbox.pack_start(entry, gtk.TRUE, gtk.TRUE)
        entryAsciiFile = entry
        
        button = gtk.Button(stock=gtk.STOCK_EXECUTE)
        button.show()
        frameVBox.pack_start(button, gtk.TRUE, gtk.TRUE)
        button.connect('clicked', doit)

            

        
        frame = gtk.Frame('Markers')
        frame.show()
        frame.set_border_width(5)
        label = gtk.Label('Markers')
        label.show()
        notebook.append_page(frame, label)


        frameVBox = gtk.VBox()
        frameVBox.show()
        frameVBox.set_spacing(3)
        frame.add(frameVBox)


        table = gtk.Table(1,2)
        table.set_homogeneous(gtk.FALSE)
        table.show()
        frameVBox.pack_start(table, gtk.FALSE, gtk.FALSE)
        
        table.set_col_spacings(3)
        table.set_row_spacings(3)
        table.set_border_width(3)


        row = 0
        label = gtk.Label('Size')
        label.show()


        scrollbar = gtk.HScrollbar()
        scrollbar.show()
        scrollbar.set_range(0, 1)
        scrollbar.set_increments(0.01,0.1)
        scrollbar.set_value(0.2)

        def set_size(bar):
            val = bar.get_value()
            for marker in self.markers:
                marker.set_size(val)
            self.interactor.Render()
            # do something
        scrollbar.connect('value_changed', set_size)
        scrollbar.set_size_request(*self.SCROLLBARSIZE)
        table.attach(label, 0, 1, row, row+1,
                     xoptions=gtk.FALSE, yoptions=gtk.FALSE)
        table.attach(scrollbar, 1, 2, row, row+1,
                     xoptions=gtk.TRUE, yoptions=gtk.FALSE)



        def markers_openhook(infile):
            try: self.load_markers(infile)
            except:
                msg = exception_to_str('Error parsing marker file %s' % hboxFile.filename)
                error_msg(msg, parent=dlg)
                return False
            else:
                return True



        def markers_savehook(outfile):
            try:
                for marker in self.markers:
                    outfile.write(marker.to_string() + '\n')
            except:
                msg = exception_to_str('Could not write markers to %s' % hboxFile.filename)
                error_msg(msg, parent=dlg)
                return
            else:
                return True

        hboxFile = OpenSaveSaveAsHBox(
            fmanager, markers_openhook, markers_savehook, parent=dlg)
        hboxFile.show()
        frameVBox.pack_start(hboxFile, gtk.FALSE, gtk.FALSE)
                    
        hbox = gtk.HBox()
        hbox.show()
        dlg.vbox.pack_start(hbox, gtk.FALSE, gtk.FALSE)

        def hide(button):
            dlg.hide()

        button = ButtonAltLabel('Hide', gtk.STOCK_CANCEL)
        button.show()
        button.connect('clicked', hide)
        hbox.pack_start(button, gtk.TRUE, gtk.TRUE)        

        self._update_frames()
        notebook.set_current_page(2)        


        return dlg


        
    def show_normals(self, button):

        for actor in self.normalActors:
            self.renderer.RemoveActor(actor)
            
        self.normalActors = []


        if not button.get_active():
            self.interactor.Render()
            return
        
        for marker in self.markerd.values():
            if not hasattr(marker, 'normal'): continue
            lineSource = vtk.vtkLineSource()
            xyz = array(marker.get_center())
            lineSource.SetPoint1(xyz)
            pnt2 = array(xyz) + marker.normal
            lineSource.SetPoint2(pnt2)
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInput(lineSource.GetOutput())
            actor = vtk.vtkActor()
            actor.SetMapper(mapper)
            self.renderer.AddActor(actor)
            self.normalActors.append(actor)
        
        self.interactor.Render()
            
    def _make_normals_vbox(self):
        vbox = gtk.VBox()
        vbox.show()

        button = gtk.CheckButton('Show normals')
        button.show()
        button.set_active(False)
        vbox.pack_start(button, gtk.FALSE, gtk.FALSE)
        button.connect('clicked', self.show_normals)
        self.buttonShowNormals = button

        class FlipNormals:
            def __init__(self, parent, markers, filter, button):
                self.parent = parent
                self.button = button
                self.markers = markers
                self.filter = filter
                
            def __call__(self, *args):
                flip = self.button.get_active()
                self.parent.set_normals_grid2(self.markers, self.filter, flip)
                self.parent.show_normals(self.parent.buttonShowNormals)
                
        self.buttonsFlip = {}


        for name in self.get_grid2_names():
            grid, actor, filter, markers = self.surfs[name]
            button = gtk.CheckButton('Flip %s normals' % name)
            button.show()
            button.set_active(False)
            vbox.pack_start(button, gtk.FALSE, gtk.FALSE)
            func = FlipNormals(self, markers, filter, button)
            button.connect('clicked', func)
            self.buttonsFlip[name] = button

        return vbox
        
    def _make_opacity_table(self):
        names = self.get_grid_names()

        table = gtk.Table(len(names)+4,2)
        table.set_homogeneous(gtk.FALSE)
        table.show()
        table.set_col_spacings(3)
        table.set_row_spacings(3)
        table.set_border_width(3)



        row = 0
        label = gtk.Label('Markers')
        label.show()


        scrollbar = gtk.HScrollbar()
        scrollbar.show()
        scrollbar.set_range(0, 1)
        scrollbar.set_increments(0.05,0.25)
        scrollbar.set_value(1)

        def set_marker_opacity(bar):
            val = bar.get_value()
            for marker in self.markers:
                marker.GetProperty().SetOpacity(val)
            self.interactor.Render()
            
        scrollbar.connect('value_changed', set_marker_opacity)
        scrollbar.set_size_request(*self.SCROLLBARSIZE)

        table.attach(label, 0, 1, row, row+1,
                     xoptions=gtk.FALSE, yoptions=gtk.FALSE)
        table.attach(scrollbar, 1, 2, row, row+1,
                     xoptions=gtk.TRUE, yoptions=gtk.FALSE)
        row+=1

        label = gtk.Label('Labels')
        label.show()
        scrollbar = gtk.HScrollbar()
        scrollbar.show()
        scrollbar.set_range(0, 1)
        scrollbar.set_increments(0.05,0.25)
        scrollbar.set_value(1)

        def set_label_opacity(bar):
            val = bar.get_value()
            for actor in self.textActors:
                actor.GetProperty().SetOpacity(val)
            self.interactor.Render()
            
        scrollbar.connect('value_changed', set_label_opacity)
        scrollbar.set_size_request(*self.SCROLLBARSIZE)

        table.attach(label, 0, 1, row, row+1,
                     xoptions=gtk.FALSE, yoptions=gtk.FALSE)
        table.attach(scrollbar, 1, 2, row, row+1,
                     xoptions=gtk.TRUE, yoptions=gtk.FALSE)
        
        row += 1


        label = gtk.Label('Pipes')
        label.show()
        scrollbar = gtk.HScrollbar()
        scrollbar.show()
        scrollbar.set_range(0, 1)
        scrollbar.set_increments(0.05,0.25)
        scrollbar.set_value(1)

        def set_pipe_opacity(bar):
            val = bar.get_value()
            for actor in self.tubeActors:
                actor.GetProperty().SetOpacity(val)
            self.interactor.Render()
            
        scrollbar.connect('value_changed', set_pipe_opacity)
        scrollbar.set_size_request(*self.SCROLLBARSIZE)

        table.attach(label, 0, 1, row, row+1,
                     xoptions=gtk.FALSE, yoptions=gtk.FALSE)
        table.attach(scrollbar, 1, 2, row, row+1,
                     xoptions=gtk.TRUE, yoptions=gtk.FALSE)
        row += 1

        self.opacityBarsDict = {}

        class SetOpacity:
            def __init__(self, prop, bar, interactor):
                self.prop = prop
                self.bar = bar
                self.renderOn = True
                self.interactor = interactor
                
            def __call__(self, *args):                
                val = self.bar.get_value()
                self.prop.SetOpacity(val)                
                if self.renderOn:
                    self.interactor.Render()    
        funcs = []

        
        for i, name in enumerate(names):
            label = gtk.Label(name)
            label.show()

            actor = self.gridActors[name]
            prop = actor.GetProperty()

            
            scrollbar = gtk.HScrollbar()
            scrollbar.show()
            scrollbar.set_range(0, 1)
            scrollbar.set_value(1)
            func = SetOpacity(prop, scrollbar, self.interactor)
            scrollbar.connect('value_changed', func)
            scrollbar.set_size_request(*self.SCROLLBARSIZE)
            scrollbar.set_increments(0.05,0.25)
            self.opacityBarsDict[name] = scrollbar
            table.attach(label, 0, 1, row, row+1,
                         xoptions=gtk.FALSE, yoptions=gtk.FALSE)
            table.attach(scrollbar, 1, 2, row, row+1,
                         xoptions=gtk.TRUE, yoptions=gtk.FALSE)
            row += 1
            funcs.append(func)

        label = gtk.Label('All')
        label.show()


        def set_opacity(bar):
            val = bar.get_value()
            for func in funcs: func.renderOn = False

            for bar in self.opacityBarsDict.values():
                bar.set_value(val)
            for func in funcs: func.renderOn = True
            self.interactor.Render()

        scrollbar = gtk.HScrollbar()
        scrollbar.show()
        scrollbar.set_range(0, 1)
        scrollbar.set_increments(0.05,0.25)
        scrollbar.set_value(1)
        scrollbar.connect('value_changed', set_opacity)
        scrollbar.set_size_request(*self.SCROLLBARSIZE)

        table.attach(label, 0, 1, row, row+1,
                     xoptions=gtk.FALSE, yoptions=gtk.FALSE)
        table.attach(scrollbar, 1, 2, row, row+1,
                     xoptions=gtk.TRUE, yoptions=gtk.FALSE)
        row += 1

        return table

    def _make_strip_angle_table(self):
        # call this after normal table built since we need to know the
        # flip state
        names = self.get_grid1_names()

        table = gtk.Table(len(names),2)
        table.set_homogeneous(gtk.FALSE)
        table.show()
        table.set_col_spacings(3)
        table.set_row_spacings(3)
        table.set_border_width(3)


        class SetAngle:
            def __init__(self, parent, name, scrollbar):
                self.name = name
                self.parent = parent
                polydata, actor, self.filter, self.markers = parent.ribbons[self.name]
                self.bar = scrollbar
                
            def __call__(self, *args):                
                val = self.bar.get_value()
                self.filter.SetAngle(val)
                self.parent.set_normals_grid1(self.markers, self.filter)
                self.parent.interactor.Render()    

        for i, name in enumerate(names):
            label = gtk.Label(name)
            label.show()


            scrollbar = gtk.HScrollbar()
            scrollbar.show()
            scrollbar.set_range(0, 360)
            scrollbar.set_value(0)

            plydata, actor, filter, markers = self.ribbons[name]
            func = SetAngle(self, name, scrollbar)

            scrollbar.connect('value_changed', func)
            scrollbar.set_size_request(*self.SCROLLBARSIZE)
            scrollbar.set_increments(5,10)
            table.attach(label, 0, 1, i, i+1,
                         xoptions=gtk.FALSE, yoptions=gtk.FALSE)
            table.attach(scrollbar, 1, 2, i, i+1,
                         xoptions=gtk.TRUE, yoptions=gtk.FALSE)

        return table
        
        
    def update_actors(self):

        for actor in self.gridActors.values():
            self.renderer.RemoveActor(actor)

        if self.dimensiond is None: return
        self.ribbons = {}  # dict from name -> ribbon actor
        self.surfs = {}    # dict from name -> surf actor
        
        for name in self.get_grid1_names():
            polydata, ribbon, filter, markers = self.make_strip_ribbon(name)
            self.ribbons[name]= polydata, ribbon, filter, markers
            self.gridActors[name]= ribbon

        for name in self.get_grid2_names():
            grid, surf, filter, markers = self.make_grid_surf(name)
            self.surfs[name] = grid, surf, filter, markers
            self.gridActors[name]= surf

        for actor in self.gridActors.values():
            self.renderer.AddActor(actor)

        self.interactor.Render()
        
    def get_grid_names(self):
        'Return a sorted list of grid names in markerd'
        d = dict([ (label[0],1) for label, trode in self.markerd.items()])
        names = d.keys()
        names.sort()
        return names

    def get_grid1_names(self):
        'Return the names of the Nx1 by grids'        
        names = []
        for name, tup in self.dimensiond.items():
            numrows, numcols = tup
            if numrows==1 or numcols==1:
                names.append(name)

        names.sort()            
        return names

    def get_grid2_names(self):
        'Return the names of the NxM'        
        names = []
        for name, tup in self.dimensiond.items():
            numrows, numcols = tup
            if numrows>1 and numcols>1:
                names.append(name)

        names.sort()            
        return names

    def make_dim_dialog(self):

        dlg = gtk.Dialog('Grid Dimensions')
        
        gridNames = self.get_grid_names()
        

        vbox = dlg.vbox
        entries = {}

        # make a dict from grid name to electrodes in grid
        named = {}
        for key, val in self.markerd.items():
            gname, gnum = key
            named.setdefault(gname, []).append( (gname, gnum) )

        table = gtk.Table( 4, len(gridNames))
        table.show()
        table.set_row_spacings(2)
        table.set_col_spacings(2)
        vbox.pack_start(table, gtk.TRUE, gtk.TRUE)
        

        for cnt, name in enumerate(gridNames):

            label = gtk.Label(name)
            label.show()
            table.attach(label, 0, 1, cnt, cnt+1)
            
            entryRows = gtk.Entry()
            entryRows.show()
            entryRows.set_text('1')
            entryRows.set_width_chars(5)
            table.attach(entryRows, 1, 2, cnt, cnt+1)
            

            entryCols = gtk.Entry()
            entryCols.show()
            entryCols.set_text('1')
            entryCols.set_width_chars(5)
            table.attach(entryCols, 2, 3, cnt, cnt+1)


            entries[name] = entryRows, entryCols

        for key in entries.keys():            
            e1, e2 = entries[key]

            N = len(named[key])
            if N==64:
                e1.set_text('8')
                e2.set_text('8')
            elif N==48:
                e1.set_text('8')
                e2.set_text('6')
            elif N==32:
                e1.set_text('8')
                e2.set_text('4')
            elif N==16:
                e1.set_text('8')
                e2.set_text('2')
            elif N==12:
                e1.set_text('6')
                e2.set_text('2')
            elif N==10:
                e1.set_text('5')
                e2.set_text('2')
            elif N==8:
                e1.set_text('8')
                e2.set_text('1')
            else:
                e1.set_text('%d'%N)
                e2.set_text('1')
                
        dlg.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        dlg.add_button(gtk.STOCK_OK, gtk.RESPONSE_OK)
        dlg.set_default_response(gtk.RESPONSE_OK)

        return dlg, entries
        
    def get_dimensions(self):
        'Return a dict mapping name to numrows, numcols'       
        self.dlgDim.show()
        response = self.dlgDim.run()

        if response == gtk.RESPONSE_OK:
            results = {}
            
            for name in self.get_grid_names():
                erows, ecols = self.dlgDimEntries[name]
                #todo: error checking
                numrows = int(erows.get_text())
                numcols = int(ecols.get_text())
                results[name] = numrows, numcols

            self.dlgDim.hide()
            self.dimensiond = results

            self.update_actors()
            
            return results
        else:
            self.dlgDim.hide()
            return None


    def make_strip_ribbon(self, name):
        """

        Return a ribbon actor for the grid with name and shape given by
        numRows, numCols where either numRows or numCols ==1

        The function attaches two properties to the markers in grid:
           normal : a Numeric array of normal values at the marker point
           ind    : an index into the point set of the grid

        """

        
        markerd = self.markerd
        numrows, numcols = self.dimensiond[name]
        N = numrows*numcols
        
        trodes = []
        for trode, marker in markerd.items():
            gname, gnum = trode
            if gname==name:
                trodes.append( (gnum, gname, marker) )

        if len(trodes) != N:
            error_msg('%s strip requires %d electrodes; only found %d' %
                      ((numrows, numcols), N, len(trodes)))
            return None
        points = vtk.vtkPoints()

        trodes.sort()
        for gnum, gname, marker in trodes:
            vtkID = points.InsertNextPoint(*marker.get_center())
            self.vtkIDs[(name, gnum)] = vtkID


        # Create the polyline.
        lines = vtk.vtkCellArray()
        lines.InsertNextCell(N)
        for i in range(N):
            lines.InsertCellPoint(i)

        polyData = vtk.vtkPolyData()
        polyData.SetPoints(points)
        polyData.SetLines(lines)


        filter = vtk.vtkRibbonFilter()
        filter.SetInput(polyData)
        filter.SetWidth(0.2)

        markers = [marker for gnum, gname, marker in trodes]
        self.set_normals_grid1(markers, filter)  # todo: check flipped state
        
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInput(filter.GetOutput())

        # make red hot
        lut = vtk.vtkLookupTable()
        lut.SetHueRange(0.667, 0.0)
        mapper.SetLookupTable(lut)

        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        #profile.GetProperty().SetDiffuseColor(banana)
        actor.GetProperty().SetSpecular(.3)
        actor.GetProperty().SetSpecularPower(30)
        return polyData, actor, filter, markers


    def make_grid_surf(self, name):
        """

        Return a surface actor for the grid with name 

        The function attaches two properties to the markers in grid:
           normal : a Numeric array of normal values at the marker point
           ind    : an index into the point set of the grid

        """

        numrows, numcols = self.dimensiond[name]
        N = numrows*numcols

        trodes = []
        for trode, marker in self.markerd.items():
            gname, gnum = trode
            if gname==name:
                trodes.append( (gnum, gname, marker) )

        if len(trodes) != N:
            error_msg('%s grid requires %d electrodes; only found %d' %
                      (numrows, numcols), N, len(trodes))
            return None

        trodes.sort() # sort by number
        
        grid = vtk.vtkStructuredGrid()
        grid.SetDimensions(numrows, numcols, 1)
        points = vtk.vtkPoints()



        for gnum, gname, marker in trodes:
            vtkID = points.InsertNextPoint(*marker.get_center())
            self.vtkIDs[(gname, gnum)] = vtkID

        grid.SetPoints(points)


        filter = vtk.vtkDataSetSurfaceFilter()
        filter.SetInput(grid)

        markers = [marker for gnum, gname, marker in trodes]
        self.set_normals_grid2(markers, filter)  # todo: check flipped state
        
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInput(filter.GetOutput())


        surfActor = vtk.vtkActor()
        surfActor.SetMapper(mapper)

        # make red hot
        lut = vtk.vtkLookupTable()
        lut.SetHueRange(0.667, 0.0)
        mapper.SetLookupTable(lut)


        property = surfActor.GetProperty()

        property.SetColor(1,1,1)
        #property.SetRepresentationToWireframe()
        property.SetRepresentationToSurface()
        property.SetInterpolationToGouraud()
        #property.SetInterpolationToPhong()
        #property.SetInterpolationToFlat()
        property.SetOpacity(1.0)
        property.EdgeVisibilityOn()
        #property.SetPointSize(10.0)

        return grid, surfActor, filter, markers

    def set_normals_grid1(self, markers, filter, flip=False):
        norms = vtk.vtkPolyDataNormals()
        norms.SetInput(filter.GetOutput())
        norms.ComputePointNormalsOn()
        #norms.AutoOrientNormalsOff()
        norms.ConsistencyOn()
        if flip:
            norms.FlipNormalsOn()
        norms.Update()
        normVecs =  norms.GetOutput().GetPointData().GetNormals()


        # todo: fix me so normals rotate too!  will need some
        # transform goop
        for i, marker in enumerate(markers):
            thisNorm = array([normVecs.GetComponent(i,0), normVecs.GetComponent(i,1), normVecs.GetComponent(i,2)], typecode=Float)

            marker.normal = thisNorm

    def set_normals_grid2(self, markers, filter, flip=False):
        norms = vtk.vtkPolyDataNormals()
        norms.SetInput(filter.GetOutput())
        norms.ComputePointNormalsOn()
        #norms.AutoOrientNormalsOff()
        norms.ConsistencyOn()
        if flip:
            norms.FlipNormalsOn()
        norms.Update()
        normVecs =  norms.GetOutput().GetPointData().GetNormals()

        for i, marker in enumerate(markers):
            thisNorm = array([normVecs.GetComponent(i,0), normVecs.GetComponent(i,1), normVecs.GetComponent(i,2)], typecode=Float)

            marker.normal = thisNorm



            
def coherence_matrix(Cxy, Pxy, xyzd, eoi, bandind):
    N = len(eoi)
    M = zeros( (N,N), Float)
    P = zeros( (N,N), Float)
    D = zeros( (N,N), Float)
    
    for i in range(N):
        for j in range(N):
            if i==j:
                M[i,j]=1.0
                D[i,j]=0.0
                continue
            key = (eoi[i], eoi[j])
            if not Cxy.has_key(key):
                key = (eoi[j], eoi[i])
            M[i,j] = Cxy[key][bandind]
            P[i,j] = Pxy[key][bandind]
            D[i,j] = dist(xyzd[eoi[i]], xyzd[eoi[j]])

    return M, P, D


def validate_marker_dict(md, eoi, parent):
    # make sure you have a key in md for every electrode in eoi

    for key in eoi:
        if not md.has_key(key):

            error_msg('Could not find a marker for electrode %s %d' % key,
                      parent=parent)            
            return False

    return True
    





