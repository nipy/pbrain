"""
matplotlib figure windows
"""
from __future__ import division
import os


import pygtk
pygtk.require('2.0')
import gtk
from scipy.signal import buttord, butter, lfilter

import MLab

import matplotlib.cm as cm
from matplotlib.mlab import meshgrid
from matplotlib.backends.backend_gtkagg import FigureCanvasGTKAgg as FigureCanvas
from matplotlib.backends.backend_gtk import NavigationToolbar, NavigationToolbar2GTK

from matplotlib.figure import Figure
from matplotlib.mlab import detrend_none, detrend_mean, detrend_linear
from matplotlib.numerix import array, take, cross_correlate, fromstring, arange, Int16, Float, log10, searchsorted

from pbrainlib.gtkutils import error_msg, simple_msg, make_option_menu,\
     get_num_value, get_num_range, get_two_nums, str2num_or_err,\
     str2posint_or_err, str2posnum_or_err
from utils import filter_grand_mean

from events import Observer
from dialogs import SpecProps


class FilterBase:
    """Do nothing filter"""
    def __call__(self, t, data):
        return data

    
class Filter(FilterBase):
    rp = 2
    rs = 20
    cf = 40
    sf = 55

    def __init__(self, parent=None):
        self.parent = None

    def __call__(self, t, data):
        dt = t[1]-t[0]
        Fs = 1.0/dt
        Nyq = Fs/2.0

        Wp = self.cf/Nyq
        Ws = self.sf/Nyq
        [n,Wn] = buttord(Wp,Ws,self.rp, self.rs)

        [b,a] = butter(n,Wn)
        data = lfilter(b,a,data)
        return data
        
        
    def make_butter_dialog(self):
        dlg = gtk.Dialog('Butterworth Filter')
        
        dlg.set_transient_for(self.parent)

        vbox = dlg.vbox

        lrp = gtk.Label('Ripple pass'); lrp.show()
        lrs = gtk.Label('Ripple stop'); lrs.show()

        lcf = gtk.Label('Low corner freq'); lcf.show()
        lsf = gtk.Label('Low stop freq');   lsf.show()        

        erp = gtk.Entry(); erp.show(); erp.set_width_chars(10)
        ers = gtk.Entry(); ers.show(); ers.set_width_chars(10)
        ecf = gtk.Entry(); ecf.show(); ecf.set_width_chars(10)
        esf = gtk.Entry(); esf.show(); esf.set_width_chars(10)        

        erp.set_text('%d'%self.rp)
        ers.set_text('%d'%self.rs)
        ecf.set_text('%1.1f'%self.cf)
        esf.set_text('%1.1f'%self.sf)        
        
        table = gtk.Table(2,4)
        table.show()
        table.set_row_spacings(4)
        table.set_col_spacings(4)

        table.attach(lrp, 0, 1, 0, 1)
        table.attach(lrs, 0, 1, 1, 2)
        table.attach(lcf, 0, 1, 2, 3)
        table.attach(lsf, 0, 1, 3, 4)                        

        table.attach(erp, 1, 2, 0, 1)
        table.attach(ers, 1, 2, 1, 2)
        table.attach(ecf, 1, 2, 2, 3)
        table.attach(esf, 1, 2, 3, 4)                        

        dlg.vbox.pack_start(table, gtk.TRUE, gtk.TRUE)

        dlg.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        dlg.add_button(gtk.STOCK_OK, gtk.RESPONSE_OK)
        dlg.set_default_response(gtk.RESPONSE_OK)
        dlg.show()


        while 1:
            response = dlg.run()
            if response == gtk.RESPONSE_OK:
                val = str2posint_or_err(erp.get_text(), lrp, dlg)
                if val is None: continue
                else: self.rp = val
                
                val = str2posint_or_err(ers.get_text(), lrs, dlg)
                if val is None: continue
                else: self.rs = val

                cf = str2posnum_or_err(ecf.get_text(), lcf, dlg)
                if cf is None: continue


                sf = str2posnum_or_err(esf.get_text(), lsf, dlg)
                if sf is None: continue

                if sf<=cf:
                    error_msg('Stop frequency must be greater than corner frequency', dlg)
                    continue
                
                
                self.cf = cf
                self.sf = sf
                break
            else: break
                
        dlg.destroy()

        
        
class MPLWin(gtk.Window, Observer):
    """
    Graph a single channel
    """
    _title = 'Figure window'
    _size = 600,400
    _iconSize = gtk.ICON_SIZE_SMALL_TOOLBAR


    _detrendd = {'None'  : detrend_none,
                 'Mean'  : detrend_mean,
                 'Linear': detrend_linear,
                 }

    _detrend = 'Mean'



    def __init__(self, eegplot, packstart=None, packend=None):    
        gtk.Window.__init__(self)
        Observer.__init__(self)
        self.set_size_request(*self._size)

        self.eegplot = eegplot
        self.eeg = eegplot.get_eeg()
        self.eoi = eegplot.get_eoi()

        self._filterButter = Filter(self)
        self._filter       = FilterBase()   # no filtering
        self._filterGM = self.eegplot.filterGM
        
        vbox = gtk.VBox()
        vbox.show()
        vbox.set_spacing(3)
        self.add(vbox)

        if packstart is not None:
            for w, expand, fill in packstart:
                vbox.pack_start(w, expand, fill)
        self.fig = Figure()
        self.axes = self.fig.add_subplot(111)        
        
        self.canvas = FigureCanvas(self.fig)  # a gtk.DrawingArea
        self.canvas.set_size_request(0,0)
        self.canvas.show()
        vbox.pack_start(self.canvas, True, True)

        if packend is not None:
            for w, expand, fill in packend:
                vbox.pack_start(w, expand, fill)

        hbox = gtk.HBox()
        hbox.show()
        vbox.pack_start(hbox, False, False)

        self.toolbar = self.make_toolbar()
        self.toolbar.show()
        hbox.pack_start(self.toolbar, False, False)

        #self.statbar = gtk.Statusbar()
        #self.statbar.show()
        #self.statbarCID = self.statbar.get_context_id('channel bar')
        #hbox.pack_start(self.statbar, gtk.TRUE, gtk.TRUE)
        #self.update_status_bar('')

        self.set_title(self._title)
        self.set_border_width(10)

        #self.canvas.connect('motion_notify_event', self.on_move)

        self._init()      # last call before make_plot
        
        self.make_plot()  #last line!
        
        def remove(*args):
            Observer.observers.remove(self)        
        self.connect('delete-event', remove)

    def make_context_menu(self):
        contextMenu = gtk.Menu()

        # remove the mean, linear trend, etc
        itemDetrend = gtk.MenuItem('Detrend')
        contextMenu.append(itemDetrend)
        itemDetrend.show()
        menu = gtk.Menu()


        def set_detrend(item, l):
            if item.get_active():
                self._detrend = l
                self.make_plot() 

        group = None
        for l in ('None', 'Mean', 'Linear'):
            item = gtk.RadioMenuItem(label=l)
            if group is None: group = item
            else: item.set_group(group)
            if l==self._detrend:
                item.set_active(True)
            else:
                item.set_active(False)

            item.show()
            item.connect( "toggled", set_detrend, l)
            menu.append(item)
        itemDetrend.set_submenu(menu)


        # remove the mean, linear trend, etc
        itemFilter = gtk.MenuItem('Filter')
        contextMenu.append(itemFilter)
        itemFilter.show()
        menu = gtk.Menu()

        def set_filter(item, l):
            if l=='Butterworth':
                if item.get_active():
                    self._filterButter.make_butter_dialog()
                    self._filter = self._filterButter
                else:
                    self._filter       = FilterBase()  # no filtering

            if l=='Filter GM':
                self._filterGM = item.get_active()
            self.make_plot() 

        for l in ('Filter GM', 'Butterworth'):
            item = gtk.CheckMenuItem(label=l)
            item.show()
            if l=='Filter GM' and self._filterGM:
                item.set_active(True)
            if l=='Butterworth':
                item.set_active(False)
            item.connect( "toggled", set_filter, l)
            menu.append(item)
        itemFilter.set_submenu(menu)
        
        return contextMenu

    def on_move(self, widget, event):
        # get the x and y coords, flip y from top to bottom
        height = self.canvas.figure.bbox.height()
        x, y = event.x, height-event.y

        if self.axes.in_axes(x, y):
            # transData transforms data coords to display coords.  Use the
            # inverse method to transform back
            x,y = self.axes.transData.inverse_xy_tup( (x,y) )
            msg = self.get_msg(x,y)
            #self.update_status_bar(msg)

        return True

    #def update_status_bar(self, msg):
    #    self.statbar.pop(self.statbarCID) 
    #    mid = self.statbar.push(self.statbarCID, msg)

    def recieve(self, event, *args):
        if not self.buttonFollowEvents.get_active(): return
        if event in (Observer.SELECT_CHANNEL, Observer.SET_TIME_LIM):
            self.make_plot()

    def make_toolbar(self):
        
        toolbar = NavigationToolbar2GTK(self.canvas, self)
        #toolbar = NavigationToolbar(self.canvas, self)        
        self.buttonFollowEvents = gtk.CheckButton('Auto')
        self.buttonFollowEvents.show()
        self.buttonFollowEvents.set_active(True)
        lastpos = 7
        toolbar.insert_widget(
            self.buttonFollowEvents, 'Automatically update figure in response to changes in EEG window', '', lastpos); lastpos+=1
        

        omenu = gtk.OptionMenu()
        omenu.show()
        cmenu = self.make_context_menu()
        omenu.set_menu(cmenu)
        toolbar.insert_widget(omenu, 'Set filter/detrend etc', '', lastpos); lastpos+=1
        
        

        return toolbar

    def _init(self):
        'last call before make plot'
        pass
    
    def make_plot(self, *args):
        raise NotImplementedError

    def get_msg(self, *args):
        'get the status bar msg'
        return ''

    def get_data(self):
        'return t, data, dt, label, with t filtered according to selections'
        selected = self.eegplot.get_selected(self._filterGM)
        if selected is None:
            error_msg('You must first select an EEG channel by clicking on it',
                      parent=self)
            return
        t, data, trode = selected

        detrend = self._detrendd[self._detrend]    

        data = detrend(self._filter(t, data))
        gname, gnum = trode
        label = '%s %d' % (gname, gnum)

        dt = t[1]-t[0]
        return t, data, dt, label




        
        
class ChannelWin(MPLWin):
    _title = "Single Channel"

    def __init__(self, eegplot):
        self.ylim = None
        MPLWin.__init__(self, eegplot)


    def get_msg(self, x,y):
        return  't = %1.2f, v=%1.2f' % (x, y)
        
    def make_plot(self, *args):
        # get the old limits
        self.axes.cla()
        self.axes.grid(True)

        tup = self.get_data()
        if tup is None: return 
        t, data, dt, label = tup
        self.axes.plot(t, data)
        if self.ylim is not None:
            self.axes.set_ylim(self.ylim)
        self.ylim = self.axes.get_ylim()
        self.axes.set_title('Channel %s'%label)
        self.axes.set_xlabel('time(s)')        


        self.canvas.draw()


class VoltageMapWin(MPLWin):
    _title = "Voltage mapper"
    
    def __init__(self, view3):
        self._idleid = 0
        self.ylim = None
        self.view3 = view3
        self.scrollbar = gtk.HScrollbar()
        self.scrollbar.show()

        packend = [(self.scrollbar, gtk.FALSE, gtk.FALSE)]
        MPLWin.__init__(self, view3.eegplot, packend=packend)
        self.scrollbar.connect('value_changed', self.update_map)        
        self.axes.connect('xlim_changed', self.update_scrolllim)


    def update_map(self, bar):
        thist = bar.get_value()
        xmin, xmax = self.axes.get_xlim()
        if thist<xmin or thist>xmax: return
        

        t, data = self.eegplot.eeg.get_data(xmin, xmax)
        if self._filterGM:
            data = filter_grand_mean(data)
        
        detrend = self._detrendd[self._detrend]    
        data = detrend(self._filter(t, data))

        dt = t[1]-t[0]

        indTime = searchsorted(t, thist)
        if indTime==data.shape[0]: return 
        # we do this here rather than in the eegview win so that we
        # can use this windows filter params
        slice = {}
        for trode, eoiInd in self.eegplot.eoiIndDict.items():
            indData = self.eegplot.indices[eoiInd]
            slice[trode] = -data[indTime, indData]
            
        self.view3.gridManager.set_scalar_data(slice)
        
        self.draw_vlines(thist)
        
    def draw_vlines(self, t):


        def make_line(ax, canvas):
            if canvas.window is None: return            
            thist, tmp = ax.transData.xy_tup((t, 0))
            ymin, ymax = ax.bbox.intervaly().get_bounds()
            height = canvas.figure.bbox.height()
            ymax = height-ymax
            ymin = height-ymin

            thist = int(thist)
            ymax = int(ymax)
            ymin = int(ymin)
            gc = canvas.window.new_gc()
            canvas.blit()
            canvas.window.draw_line(gc, thist, ymin, thist, ymax)

        make_line(self.axes, self.canvas)
        make_line(self.eegplot.axes, self.eegplot.canvas)

    def get_msg(self, x,y):
        return  't = %1.2f, v=%1.2f' % (x, y)

    def update_scrolllim(self, ax):
        xmin, xmax = ax.get_xlim()
        try: self.dt
        except AttributeError: dt = 1/400.0
        else: dt = self.dt
        self.scrollbar.set_range(xmin , xmax)
        self.scrollbar.set_increments(dt, dt)
        x = (xmax-xmin)/2.0 + xmin
        self.scrollbar.set_value(x)

        self.draw_vlines(x)

        
    def make_plot(self, *args):
        # get the old limits
        self.axes.cla()
        self.axes.grid(True)

        tup = self.get_data()
        if tup is None: return 
        t, data, dt, label = tup
        self.t = t
        self.dt = dt
        
        self.axes.plot(t, data)

        if self.ylim is not None:
            self.axes.set_ylim(self.ylim)
        self.ylim = self.axes.get_ylim()
        ymin , ymax = self.ylim
        self.axes.set_title('Channel %s'%label)
        self.axes.set_xlabel('time(s)')        

        #self.indicatorLine, = self.axes.plot(
        #    [min(t), min(t)], (ymin , ymax), 'k-', linewidth=2)
        self.canvas.draw()
        self.update_scrolllim(self.axes)
        


            
class AcorrWin(MPLWin):
    _title = "Autocorrelation"

    def __init__(self, eegplot):
        self._haveData = False
        MPLWin.__init__(self, eegplot)
    
    def get_msg(self, x,y):
        if not hasattr(self, '_dt'):
            return 'no acorr defined'
        t, corr = x, y
        lag = int(t/self._dt)
        return  't = %1.2f, lag=%d, corr = %1.2f' % (t, lag, corr)
        
    def make_plot(self, *args):
        # get the old limits
        if self._haveData:
            xlim = self.axes.get_xlim()
            ylim = self.axes.get_ylim()            

        self.axes.cla()
        self.axes.grid(True)

        tup = self.get_data()
        if tup is None: return 
        t, data, dt, label = tup

        dt = t[1]-t[0]
        self._dt = dt # for get_msg

        corr = cross_correlate(data, data, mode=2)
        corr = corr/corr[len(data)-1] # normed so autocorr at zero lag is 1
        lags = arange(-len(data)+1, len(data))*dt
        self.axes.plot(lags, corr)

        if self._haveData:
            self.axes.set_xlim(xlim)
            self.axes.set_ylim(ylim)


        self._haveData = True
        self.canvas.draw()
                         

class HistogramWin(MPLWin):
    _title = 'Histogram'
    
    def get_msg(self, x,y):
        return  'bin = %1.2f; cnt = %1.2f' % (x,y)
        
    def make_plot(self, *args):
        # get the old limits
        self.axes.cla()
        self.axes.grid(True)

        tup = self.get_data()
        if tup is None: return 
        t, data, dt, label = tup

        self.axes.hist(data, 200)
        self.axes.set_title('Channel %s'%label)
        self.canvas.draw()



class SpecWin(MPLWin):
    propdlg = SpecProps()

    def _init(self):
        self.cmap = cm.jet
        # min and max power
        self.flim = 0, 100   # the defauly yaxis
        self.clim = None     # the colormap limits
                
        iconw = gtk.Image()
        iconw.set_from_stock(gtk.STOCK_PREFERENCES, self._iconSize)
        bAuto = self.toolbar.append_item(
            'Properties',
            'Set the color map properties',
            'Private',
            iconw,
            self.set_properties)


    def set_properties(self, *args):
        dlg = self.propdlg

        if not len(dlg.entryCMin.get_text()) and hasattr(self, 'pmin'):
            dlg.entryCMin.set_text('%1.2f'%self.pmin)
        if not len(dlg.entryCMax.get_text()) and hasattr(self, 'pmax'):
            dlg.entryCMax.set_text('%1.2f'%self.pmax)
            
        while 1:
            response = dlg.run()

            if response in  (gtk.RESPONSE_OK, gtk.RESPONSE_APPLY):
                b = dlg.validate()
                if not b: continue
                self.flim = dlg.get_flim()
                self.clim = dlg.get_clim()
                self.make_plot()
                if response==gtk.RESPONSE_OK:
                    dlg.destroy()
                    break
            else:
                dlg.destroy()
                break


    def make_plot(self, *args):

        self.axes.cla()

        tup = self.get_data()
        if tup is None: return 
        torig, data, dt, label = tup

        # use this instead of self.eegplot.eeg.freq in case filter decimates
        Fs = 1.0/dt  
        NFFT, Noverlap = 512, 477


        self.axes.clear()
        xmin, xmax = self.eegplot.axes.get_xlim()
        Pxx, freqs, t, im = self.axes.specgram(
            data, NFFT=NFFT, Fs=Fs, noverlap=Noverlap,
            cmap=self.cmap, xextent=(xmin, xmax))

        if self.clim is not None:
            im.set_clim(self.clim[0], self.clim[1])

        t = t + min(torig)

        Z = 10*log10(Pxx)
        self.pmin = MLab.min(MLab.min(Z))
        self.pmax = MLab.max(MLab.max(Z))
        

        self.axes.set_xlim( [xmin, xmax] )
        self.axes.set_xticks( self.eegplot.axes.get_xticks()  )
        self.axes.set_title('Spectrogram for electrode %s' % label)
        self.axes.set_xlabel('TIME (s)')
        self.axes.set_ylabel('FREQUENCY (Hz)')
        self.axes.set_ylim(self.flim)
        self.axes.set_yticks(arange(self.flim[0], self.flim[1]+1, 10))        
        #print 'calling draw'
        self.canvas.draw()
        
    def recieve(self, event, *args):
        if not self.buttonFollowEvents.get_active(): return
        if event in (Observer.SELECT_CHANNEL, Observer.SET_TIME_LIM):
            self.make_plot()
        elif event==Observer.SAVE_FRAME:
            fname = args[0]
            framefile = fname + '_specgram.png'
            self.fig.print_figure(framefile, dpi=72)
            basedir, filepart = os.path.split(framefile)
            listfile = os.path.join(basedir, 'eegplot.vfl')
            try:  file(listfile, 'a').write('%s\n'%filepart)
            except IOError:
                error_msg('Could not write list file %s' % listfile)
                return
            
            
    
