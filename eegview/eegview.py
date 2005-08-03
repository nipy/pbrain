# begin jonathan -
#
#  * the rect drawing is fucked w/ or w/o use blit but I think I can
#  fix this reasonably soon
# 
# end jonathan
#
# TODO: fix vsteps for different numbers of electrodes
# font sizes are different on ylabels
from __future__ import division
import sys, os, copy, traceback
import distutils.sysconfig

#import pygtk
#pygtk.require('2.0')

import gtk
from gtk import gdk

from Numeric import fromstring, arange, Int16, Float, log10
import MLab
from matplotlib.cbook import enumerate, exception_to_str, popd
from pbrainlib.gtkutils import str2num_or_err, simple_msg, error_msg, \
     not_implemented, yes_or_no, FileManager, select_name, get_num_range

from matplotlib.widgets import Cursor, HorizontalSpanSelector

from data import EEGWeb, EEGFileSystem, EOI, Amp, Grids
from file_formats import FileFormat_BNI, W18Header, FileFormat_BNI

from dialogs import Dialog_Preferences, Dialog_SelectElectrodes,\
     Dialog_CohstatExport, Dialog_SaveEOI, Dialog_EEGParams, \
     Dialog_Annotate, Dialog_AnnBrowser, AutoPlayDialog, SpecProps
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
from matplotlib.transforms import get_bbox_transform, Point, Value, Bbox,\
     unit_bbox, blend_xy_sep_transform
from matplotlib.patches import Rectangle

from scipy import arange, sin, pi, zeros, ones, reshape, Float, Float0, \
     greater_equal, transpose, array, arange, resize, Int16, \
     absolute, nonzero

from scipy.signal import buttord, butter, lfilter

from mpl_windows import ChannelWin, AcorrWin, HistogramWin, SpecWin

from datetime import datetime


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

def load_params(path):
    params = {}
    for line in file(path):
        line = line.strip()
        if not len(line): continue
        if line.startswith('#'): continue

        k,v = line.split(':',1)
        k = k.strip()
        v = v.strip()
        if k in ('channels', 'pid', 'freq', 'classification', 'file_type', 'behavior_state') :
            v = int(v)
        params[k] = v

    eegfile = params['eegfile']
    if not os.path.exists(eegfile):
        error_msg('Cannot find eeg file "%s"'%eegfile)
        return

    eeg = EEGFileSystem(eegfile, params)
    return eeg

extmap = { '.w18' : load_w18,
           '.bni' : load_bmsi,
           '.params' : load_params,
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
            'Private',
            iconw,
            self.panx,
            -10)
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

        def lock_trode_toggled(button) :
            self.broadcast(Observer.LOCK_TRODE_TOGGLED, button)

        self.buttonGM = gtk.CheckButton('GM')
        self.buttonGM.show()
        self.buttonGM.connect('toggled', toggled)
        self.buttonGM.set_active(True)
        self.append_widget(
            self.buttonGM, 'Remove grand mean from data if checked', '')
        
        self.buttonLockTrode = gtk.CheckButton('Lock')
        self.buttonLockTrode.show()
        self.buttonLockTrode.connect('toggled', lock_trode_toggled)
        self.append_widget(
            self.buttonLockTrode, 'Lock Selected Electrode', '')

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
        return False

    def zoomx(self, button, arg):
        if self.eegplot is None: return 
        try: arg.direction
        except AttributeError: direction = arg
        else:            
            if arg.direction == gdk.SCROLL_UP: direction=1
            else: direction=0

        self.eegplot.change_time_gain(direction)
        self.eegplot.draw()
        return False

    def zoomy(self, button, arg):
        if self.eegplot is None: return 
        try: arg.direction
        except AttributeError: direction = arg
        else:
            if arg.direction == gdk.SCROLL_UP: direction=1
            else: direction=0

        self.eegplot.change_volt_gain(direction)
        self.eegplot.draw()
        return False


class AnnotationManager:
    """
    The highlight is the currently created rectangle that has not yet been
    annotated.  

    The selected rectangle is a rect that has been annotated and
    selected (not the same as highlighted!)
    
    """
    def __init__(self, eegplot):
        self.eegplot = eegplot
        self.axes = self.eegplot.axes
        self.canvas = self.axes.figure.canvas

        self.ann = self.eegplot.eeg.get_ann()

        rectprops = dict(facecolor='#bbbbff',
                         alpha=0.5)
        self.selector = HorizontalSpanSelector(self.axes, self.onselect,
                                               minspan=0.01, 
                                               useblit=True,
                                               rectprops=rectprops)

        self._highlight = None
        self.resize = False
        self.background = None

        def ok_callback(*args) :
            self.dlgbrowser.hide_widget()
            
        self.selectedkey = None
        self.dlgbrowser = Dialog_AnnBrowser(eegplot, self, ok_callback)

        # Update Annotations menuitems sensitivity.
        menuItemAnnBrowser = Shared.widgets.get_widget('menuItemAnnBrowser')
        menuItemAnnBrowser.set_sensitive(1)
        menuItemAnnCreateEdit = Shared.widgets.get_widget('menuItemAnnCreateEdit')
        menuItemAnnCreateEdit.set_sensitive(1)
        menuItemAnnHorizCursor = Shared.widgets.get_widget('menuItemAnnHorizCursor')
        menuItemAnnHorizCursor.set_sensitive(1)
        menuItemAnnVertCursor = Shared.widgets.get_widget('menuItemAnnVertCursor')
        menuItemAnnVertCursor.set_sensitive(1)

    def onselect(self, xmin, xmax):
        if self._highlight is not None:
            self.remove_highlight()
        self._highlight = xmin, xmax, self._new_rect(xmin, xmax, 
                                                     facecolor='#bbbbff',
                                                     edgecolor='k',
                                                     linewidth=2,
                                                     alpha=0.5,
                                                     zorder=3
                                                     )

        # Update Annotations menuitems sensitivity
        label = 'Create New'
        menuItemAnnCreateEdit = Shared.widgets.get_widget('menuItemAnnCreateEdit')
        menuItemAnnCreateEdit.get_children()[0].set_text(label)
        menuItemAnnDelete = Shared.widgets.get_widget('menuItemAnnDelete')
        menuItemAnnDelete.set_sensitive(0)

    def _new_rect(self, xmin, xmax, **props):
        trans = blend_xy_sep_transform( self.axes.transData,
                                        self.axes.transAxes   )

        rect = Rectangle(
            xy=(xmin, 0), width=xmax-xmin, height=1,
            transform=trans, **props)
        self.axes.add_patch(rect)
        return rect

    def over_annotation(self, t):
        """
        If you are over an annotation, return it's key

        If you are over multiple annotations, return the one who's
        center is closest to point

        If not over annotation, return None
        """
        ret = []
        for key, info in self.ann.items():
            s = info['startTime']
            e = info['endTime']
            if t >= s - .05 and t <= e + .05 :
                middle = 0.5 * (e + s)
                d = abs(t - middle)
                ret.append((d, key))
        ret.sort()
        if not len(ret): return None

        return ret[0][1]  

    def over_edge(self, t) :
      """
      If you are over an annotation edge, return it's key
      """
      for key, info in self.ann.items() :
          s = info['startTime']
          e = info['endTime']
          if t >= s - .05 and t <= s + .05 :
              return key, 0
          elif t >= e - .05 and t <= e + .05 :
              return key, 1

      return (None, None), None

    def is_over_highlight(self, t) :
        xmin, xmax = self.highlight_span()
        return t >= xmin and t <= xmax

    def remove_highlight(self):
        if self._highlight is not None:
            xmin, xmax, rect = self._highlight
            self.axes.patches.remove(rect)
        self._highlight = None
        self.canvas.draw()

        # Update Annotations menuitems sensitivity
        label = 'Create New'
        menuItemAnnCreateEdit = Shared.widgets.get_widget('menuItemAnnCreateEdit')
        menuItemAnnCreateEdit.get_children()[0].set_text(label)
        menuItemAnnDelete = Shared.widgets.get_widget('menuItemAnnDelete')
        menuItemAnnDelete.set_sensitive(0)

    def get_highlight(self):
        """
        return (xmin, xmax, Rectangle instance) if a rect is highlighted
        Otherwise return None
        """
        return self._highlight 

    def highlight_span(self):
        'return the min/max of current highlight or raise if not highlight'
        if self._highlight is None: return None, None
        xmin, xmax, rect = self._highlight
        return xmin, xmax

    def remove_selected(self):
        """
        remove the selected annotation from the ann data struct and
        the plot stff and redraw
        """

        thisann = popd(self.eegplot.annman.ann, self.selectedkey, None)
        if thisann is None:
            return

        self.eegplot.axes.patches.remove(thisann['rect'])
        self.selectedkey = None
        self.eegplot.draw()

        # Update Annotations menuitems sensitivity
        label = 'Create New'
        menuItemAnnCreateEdit = Shared.widgets.get_widget('menuItemAnnCreateEdit')
        menuItemAnnCreateEdit.get_children()[0].set_text(label)
        menuItemAnnDelete = Shared.widgets.get_widget('menuItemAnnDelete')
        menuItemAnnDelete.set_sensitive(0)

    def set_selected(self, newkey=None) :
        'selected is a start, end key; make that annotation the selected one'
        if newkey == self.selectedkey: return
            
        menuItemAnnCreateEdit = Shared.widgets.get_widget('menuItemAnnCreateEdit')
        menuItemAnnDelete = Shared.widgets.get_widget('menuItemAnnDelete')

        if self.selectedkey is not None:
            # unselect the old one if there is one
            rect = self.ann[self.selectedkey].get('rect')
            if rect is not None :
                rect.set_edgecolor('k')
                rect.set_linewidth(1)            

        if newkey is None:
            # Update Annotations menuitems sensitivity
            menuItemAnnDelete.set_sensitive(0)
        else :
            # now set the props of the new one
            rect = self.ann[newkey]['rect']
            rect.set_edgecolor('r')
            rect.set_linewidth(3)
            self.canvas.draw()

            # Update Annotations menuitems sensitivity
            menuItemAnnCreateEdit.get_children()[0].set_text('Edit Selected')
            menuItemAnnDelete.set_sensitive(1)

        self.selectedkey = newkey

    def start_resize(self, side) :
        self.resize = True
        self.resize_side = side
        self.ann[self.selectedkey]['rect'].set_visible(False)
        self.background = self.eegplot.canvas.copy_from_bbox(self.eegplot.axes.bbox)
        self.ann[self.selectedkey]['rect'].set_visible(True)

    def end_resize(self) :
        self.resize = False
        self.background = None
        self.eegplot.draw()
        
    def resize_selected(self, s, e) :
        rect = self.ann[self.selectedkey]['rect']
        rect.set_x(s)
        rect.set_width(e - s)

        # Update key if it changed.
        newkey = '%1.1f' % s, '%1.1f' % e
        if newkey <> self.selectedkey :
            self.ann[newkey] = self.ann[self.selectedkey]
            self.ann[newkey]['startTime'] = s
            self.ann[newkey]['endTime'] = e
            del self.ann[self.selectedkey]

            self.selectedkey = newkey

        self.eegplot.canvas.restore_region(self.background)
        self.eegplot.axes.draw_artist(rect)
        self.eegplot.canvas.blit(self.eegplot.axes.bbox)

    def update_annotations(self) :
        """
        Create new annotation rectangles on file load or navigation
        """
        tmin, tmax = self.eegplot.get_time_lim()

        keys = self.ann.keys()
        keys.sort()
        for key in keys :
            if not self.ann[key].get('visible') :
                rect = self.ann[key].get('rect')
                if rect is not None :
                    self.eegplot.axes.patches.remove(rect)
                    del self.ann[key]['rect']
                    if self.selectedkey == key :
                        self.set_selected()
                continue

            # Start or end of annotation box is in view
            s = self.ann[key]['startTime']
            e = self.ann[key]['endTime']
            if not ( (s > tmin and s < tmax) or
                     (e > tmin and e < tmax) ) : continue

            # Draw/Update annotation box.
            rect = self.ann[key].get('rect')
            if rect is None:
                rect = self._new_rect(s, e, alpha=0.5, zorder=3)
                self.ann[key]['rect'] = rect
            rect.set_facecolor(self.ann[key]['color'])

        self.eegplot.draw()
        
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
        self.canvas = canvas
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

        # Lock the selected electrode.
        self.lock_trode = False

        # Create a vertical cursor.
        self.cursor = Cursor(self.axes, useblit=True, linewidth=1, color='red')
        if eegviewrc.horizcursor == 'True' :
            self.cursor.horizOn = True
        else :
            self.cursor.horizOn = False
        if eegviewrc.vertcursor == 'True' :
            self.cursor.vertOn = True
        else :
            self.cursor.vertOn = False

        self.annman = AnnotationManager(self)

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
        elif event == Observer.LOCK_TRODE_TOGGLED :
            button = args[0]
            self.lock_trode = button.get_active()
            
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

        boxin = Bbox(
            Point(self.axes.viewLim.ll().x(), Value(-vset)),
            Point(self.axes.viewLim.ur().x(), Value(vset)))



        boxout = Bbox(
            Point(self.axes.bbox.ll().x(), Value(-72)),
            Point(self.axes.bbox.ur().x(), Value(72)))


        transOffset = get_bbox_transform(
            unit_bbox(),
            Bbox( Point( Value(0), self.axes.bbox.ll().y()),
                  Point( Value(1), self.axes.bbox.ur().y())
                  ))
        
        pairs = zip(self.indices, offsets)

        labeld = amp.get_dataind_dict()

        for ind, offset in pairs:

            trode = labeld[ind]

            color = self.get_color(trode)
            if self._selected==trode: color='r'
            trans = get_bbox_transform(boxin, boxout)

            thisLine = Line2D(t, data[:,ind],
                              color=color,
                              linewidth=0.75,
                              linestyle='-',
                              )
            thisLine.set_transform(trans)
            thisLine.set_data_clipping(False)
            trans.set_offset((0, offset), transOffset)
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
        
        # Update annotation boxes
        self.annman.update_annotations()

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

        
    def get_channel_at_point(self, x, y, select=True):
        "Get the EEG with the voltage trace nearest to x, y (window coords)"
        tmin, tmax = self.get_time_lim()
        dt = 1/self.decfreq

        t, yt = self.axes.transData.inverse_xy_tup( (x,y) )

        ind = int((t-tmin)/dt)

        
        ys = zeros( (len(self.lines), ), typecode = Int16)

        xdata = self.lines[0].get_xdata()
        if ind>=len(xdata): return None
        thisx = xdata[ind]
        for i, line in enumerate(self.lines):

            thisy = line.get_ydata()[ind]
            trans = line.get_transform()
            xt, yt = trans.xy_tup((thisx, thisy))
            ys[i] = yt

        ys = absolute(ys-y)
        matches = nonzero(ys==min(ys))

        ind = matches[0]
        labeld = self.eeg.amp.get_dataind_dict()
        trode = labeld[self.indices[ind]]
        gname, gnum = trode
        if select :
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
        self.eegplot = eegplot
        self.cmap = cm.jet
        # min and max power

    def make_spec(self, *args):
        selected = self.eegplot.get_selected()
        if selected is None:
            self.axes.cla()
            t = self.axes.text(
                0.5, 0.5,
                'Click on EEG channel for spectrogram (scroll mouse to expand)',
                verticalalignment='center',
                horizontalalignment='center',
                )
            t.set_transform(self.axes.transAxes)
            xmin, xmax = self.eegplot.get_time_lim()
            self.axes.set_xlim( [xmin, xmax] )
            self.axes.set_xticks( self.eegplot.axes.get_xticks()  )
            return

        flim = SpecPlot.flim
        clim = SpecPlot.clim

        torig, data, trode = selected
        gname, gnum = trode
        label = '%s %d' % (gname, gnum)
        Fs = self.eegplot.eeg.freq

        NFFT, Noverlap = (512, 477)

        self.axes.cla()
        xmin, xmax = self.eegplot.get_time_lim()
        xextent = xmin, xmax
        Pxx, freqs, t, im = self.axes.specgram(
            data, NFFT=NFFT, Fs=Fs, noverlap=Noverlap,
            cmap=self.cmap, xextent=xextent)

        if clim is not None:
            im.set_clim(clim[0], clim[1])

        t = t + min(torig)

        Z = 10*log10(Pxx)
        self.pmin = MLab.min(MLab.min(Z))
        self.pmax = MLab.max(MLab.max(Z))
        

        self.axes.set_xlim( [xmin, xmax] )
        self.axes.set_xticks( self.eegplot.axes.get_xticks()  )

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
    gladeFile = 'gui/main.glade'

    def __init__(self):
        if os.path.exists(self.gladeFile):
            theFile=self.gladeFile
        else:
            theFile = os.path.join(
                distutils.sysconfig.PREFIX,
                'share', 'pbrain', self.gladeFile)
        
        try: Shared.widgets = gtk.glade.XML(theFile)
        except:
            raise RuntimeError('Could not load glade file %s' % theFile)
        
        PrefixWrapper.__init__(self)
        self._isConfigured = False
        self.patient = None

        figsize = eegviewrc.figsize
        self.fig = Figure(figsize=figsize, dpi=72)

        self.canvas = FigureCanvas(self.fig)  # a gtk.DrawingArea
        self.canvas.set_size_request(600, 400)

        self.canvas.connect("scroll_event", self.scroll_event)
        self.canvas.show()

        #self.fig = Figure(figsize=(7,5), dpi=72)
        t = arange(0.0,50.0, 0.01)
        xlim = array([0,10])

        self.axes = self.fig.add_axes([0.075, 0.25, 0.9, 0.725], axisbg='#FFFFCC')

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
        self.canvas.mpl_connect('motion_notify_event', self.motion_notify_event)
        self.canvas.mpl_connect('button_press_event', self.button_press_event)
        self.canvas.mpl_connect('button_release_event', self.button_release_event)

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

        # Init Annotations menu sensitivity.
        menuItemAnnBrowser = Shared.widgets.get_widget('menuItemAnnBrowser')
        menuItemAnnBrowser.set_sensitive(0)
        menuItemAnnCreateEdit = Shared.widgets.get_widget('menuItemAnnCreateEdit')
        menuItemAnnCreateEdit.set_sensitive(0)
        menuItemAnnDelete = Shared.widgets.get_widget('menuItemAnnDelete')
        menuItemAnnDelete.set_sensitive(0)
        menuItemAnnHorizCursor = Shared.widgets.get_widget('menuItemAnnHorizCursor')
        menuItemAnnHorizCursor.set_sensitive(0)
        if eegviewrc.horizcursor == 'True' :
            menuItemAnnHorizCursor.set_active(1)
        else :
            menuItemAnnHorizCursor.set_active(0)
        menuItemAnnVertCursor = Shared.widgets.get_widget('menuItemAnnVertCursor')
        menuItemAnnVertCursor.set_sensitive(0)
        if eegviewrc.vertcursor == 'True' :
            menuItemAnnVertCursor.set_active(1)
        else :
            menuItemAnnVertCursor.set_active(0)

    def update_status_bar(self, msg):
        self.statbar.pop(self.statbarCID) 
        mid = self.statbar.push(self.statbarCID, 'Message: ' + msg)

    def menu_select_eeg(self, eeg):
        amp = eeg.get_amp()
        if amp.message is not None:
            simple_msg(amp.message, title='Warning',
                       parent=Shared.windowMain.widget)

        try: self.eegplot
        except AttributeError: pass
        else: Observer.observers.remove(self.eegplot)        

        try: self.specPlot
        except AttributeError: pass
        else: Observer.observers.remove(self.specPlot)        

        self.eegplot = EEGPlot(eeg, self.canvas)
        self.toolbar.set_eegplot(self.eegplot)
        self.specPlot = SpecPlot(self.axesSpec, self.canvas, self.eegplot)
        self.specMenu = self.make_spec_menu()
        eois = eeg.get_associated_files(atype=5, mapped=1)
        self.eoiMenu = self.make_context_menu(eois)
        self.eegplot.plot()
        return False

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
        success = self.eegplot.set_eoi(eoi)
        
        if success:
            tmin, tmax = self.eegplot.get_time_lim()
            self.eegplot.plot()
            self.eegplot.set_time_lim(tmin, tmax)
            self.eegplot.draw()
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

        menuItemSep = gtk.MenuItem()
        contextMenu.append(menuItemSep)
        menuItemSep.show()

        label = "Create New Annotation"
        menuItemAnnCreateEdit = gtk.MenuItem(label)
        menuItemAnnCreateEdit.connect("activate", self.on_menuItemAnnCreateEdit_activate)
        menuItemAnnCreateEdit.show()
        contextMenu.append(menuItemAnnCreateEdit)

        label = "Delete Annotation"
        menuItemAnnDelete = gtk.MenuItem(label)
        menuItemAnnDelete.connect("activate", self.on_menuItemAnnDelete_activate)
        menuItemAnnDelete.show()
        contextMenu.append(menuItemAnnDelete)

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
            success = self.eegplot.set_eoi(eoi)
            if success:
                tmin, tmax = self.eegplot.get_time_lim()
                self.eegplot.plot()
                self.eegplot.set_time_lim(tmin, tmax)
                self.eegplot.draw()

            d.destroy_dialog()
            return
        
        eoiActive = self.eegplot.get_eoi()
        eoiAll = self.eegplot.get_eeg().get_amp().to_eoi()
        d = Dialog_SelectElectrodes(trodes=eoiAll,
                                    ok_callback=ok_callback,
                                    selected=eoiActive
                                    )
        d.set_transient_for(self.widget)

    def save_eoi(self, menuitem, saveas):

        eoi = self.eegplot.get_eoi()
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
            pid=self.eegplot.get_eeg().get_pid()
            newName = m['filename']

            eoiNew = EOI()
            eoiNew.extend(eoi)
            
            def new_eoi_success():
                eeg = self.eegplot.get_eeg()
                success = self.eegplot.set_eoi(eoiNew)

                eoiNew.update_map(eeg.get_filename())
                eois = eeg.get_associated_files(atype=5, mapped=1)
                self.eoiMenu = self.make_context_menu(eois)
                dlgSave.hide_widget()
                simple_msg('%s successfully uploaded' % newName,
                              title='Congratulations',
                              parent=self.widget)
                if success: self.eegplot.plot()

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
        
        dlgSave = Dialog_SaveEOI(eoiActive=self.eegplot.get_eoi(),
                           eoisAll=self.eegplot.get_eeg().get_eois(),
                           ok_callback=ok_callback)
        dlgSave.get_widget().set_transient_for(self.widget)
        dlgSave.show_widget()

    def on_menuItemAnnCreateEdit_activate(self, event) :
        annman = self.eegplot.annman
        
        def ok_callback(params) :
            dlgAnnotate.hide_widget()

            # Add annotation to data structure
            key = '%1.1f' % params['startTime'], '%1.1f' % params['endTime']
            params = dlgAnnotate.get_params()

            # Set created and edited times.
            if annman.selectedkey is not None:
                created = annman.ann[key]['created']
                edited = datetime.today()
            else :
                created = datetime.today()
                edited = created

            # Keep some current values if they exist.
            visible, rect = 1, None
            old = annman.ann.get(key)
            if old is not None :
                visible = old.get('visible')
                rect = old.get('rect')

            annman.ann[key] = {
                'startTime'     : params['startTime'],
                'endTime'       : params['endTime'],
                'created'       : created,
                'edited'        : edited,
                'username'      : params['username'],
                'code'          : params['code'],
                'color'         : params['color'],
                'visible'	: visible,
                'annotation'    : params['annotation'],
                'rect'		: rect}

            # Write ann file.
            annman.ann.save_data()

            # Create new annotation box. 
            annman.update_annotations()

            # Update ann browser info
            annman.dlgbrowser.update_ann_info(key)

            # Turn off highlight box.
            annman.remove_highlight()

            return

        params = {}
        if annman.selectedkey is not None:
            params = annman.ann[annman.selectedkey]
        else:
            # Create new annotation
            hlight = annman.get_highlight()
            if hlight is None :
                params = {}
            else :
                start, end = annman.highlight_span()
                params = dict(startTime=start, endTime=end)

        dlgAnnotate = Dialog_Annotate(params, ok_callback)
        dlgAnnotate.get_widget().set_transient_for(self.widget)
        dlgAnnotate.show_widget()

    def on_menuItemAnnDelete_activate(self, event) :
        dlg = gtk.MessageDialog(type=gtk.MESSAGE_QUESTION,
                                buttons=gtk.BUTTONS_YES_NO,
                                message_format='Are you sure you wish to delete this annotation?')
        dlg.set_title('Delete Annotation')
        response = dlg.run()
        dlg.destroy()

        if response == gtk.RESPONSE_YES :
            self.eegplot.annman.remove_selected()
            self.eegplot.annman.ann.save_data()

    def on_menuItemAnnHorizCursor_activate(self, checkMenuItem) :
        if checkMenuItem.get_active() :
            self.eegplot.cursor.horizOn = True
            eegviewrc.horizcursor = True
        else :
            self.eegplot.cursor.horizOn = False
            eegviewrc.horizcursor = False

        return False

    def on_menuItemAnnVertCursor_activate(self, checkMenuItem) :
        if checkMenuItem.get_active() :
            self.eegplot.cursor.vertOn = True
            eegviewrc.vertcursor = True
        else :
            self.eegplot.cursor.vertOn = False
            eegviewrc.vertcursor = False

        return False

    def on_buttonSaveExcursion_clicked(self, event):
        self.eegplot.save_excursion()
        return False
    
    def on_buttonRestoreExcursion_clicked(self, event):
        self.eegplot.restore_excursion()
        self.eegplot.draw()
        return False
    
    def on_buttonJumpToTime_clicked(self, event):
        val = str2num_or_err(self['entryJumpToTime'].get_text(),
                            parent=self.widget)

        if val is None: return
        self.eegplot.set_time_lim(val)
        self.eegplot.draw()
        return False

    def expose_event(self, widget, event):
        return False
    
    def configure_event(self, widget, event):
        self._isConfigured = True
        return False

    def realize(self, widget):
        return False

    def motion_notify_event(self, event):
        try: self.eegplot
        except : return False

        if not event.inaxes: return

        # Motion within EEG axes
        if event.inaxes == self.axes:
            t, yt = event.xdata, event.ydata
            #t = float('%1.1f' % t)
            annman = self.eegplot.annman

            # Resize annotation.
            if event.button == 1 :
                if annman.resize :
                    s = annman.ann[annman.selectedkey]['startTime']
                    e = annman.ann[annman.selectedkey]['endTime']
                    if annman.resize_side == 0 :
                        s = t
                    else :
                        e = t
                    if s < e :
                        annman.resize_selected(s, e)
                else :
                    annman.set_selected()    
            else :
                # Change mouse cursor if over an annotation edge.
                selected, side = annman.over_edge(t)
                if selected[0] is not None :
                    self.widget.window.set_cursor(gdk.Cursor(gdk.SB_H_DOUBLE_ARROW))
                else :
                    self.widget.window.set_cursor(gdk.Cursor(gdk.LEFT_PTR))

            # Update status bar with time and electrode name and number
            trode = self.eegplot.get_channel_at_point(event.x, event.y, False)
            if trode is not None:
                gname, gnum = trode
                self.update_status_bar(
                    'Time  = %1.1f (s), Electrode %s%d' % (t, gname, gnum))

        # Motion within spectrum axes
        elif event.inaxes == self.axesSpec:
            t, f = event.xdata, event.ydata
            self.update_status_bar(
                'Time  = %1.1f (s), Freq = %1.1f (Hz)' % (t, f))

        return False

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
        
    def button_press_event(self, event):
        try: self.eegplot
        except AttributeError: return False

        if not event.inaxes: return
        
        self.buttonDown = event.button
        annman = self.eegplot.annman

        if event.button == 1 or event.button == 3 :
            if event.inaxes == self.axes:
                t, yt = event.xdata, event.ydata
                t = float('%1.1f' % t)

                if not annman.is_over_highlight(t) :
                    key = annman.over_annotation(t)
                    annman.remove_highlight()
                    annman.set_selected(key)
                    annman.dlgbrowser.update_ann_info(key)

        if event.button==1:
            if event.inaxes == self.axes:
                self.eegplot.cursor.visible = False
                t, yt = event.xdata, event.ydata

                # Start resize if edge of an annotation clicked.
                selected, side = annman.over_edge(t)
                if selected[0] is not None :
                    self.eegplot.annman.start_resize(side)
                    self.eegplot.annman.selector.visible = False

                # Select an electrode if not locked.
                if not self.eegplot.lock_trode :                        
                    trode = self.eegplot.get_channel_at_point(event.x, event.y)
                    if trode is not None:
                        gname, gnum = trode
                        self.update_status_bar('Electrode: %s%d' % (gname, gnum))

        if event.button==3:
            # right click brings up the context menu
            if event.inaxes == self.axes:
                menu = self.eoiMenu
            elif event.inaxes == self.axesSpec:
                menu = self.specMenu
            else:
                return False

            # Update popup menu items
            highsens =  annman.get_highlight() is not None
            selsens = self.eegplot.annman.selectedkey is not None
            if highsens: label = 'Create New Annotation'
            else: label = 'Edit Selected Annotation'

            menuItems = menu.get_children()
            menuItemAnnCreateEdit = menuItems[-2]
            menuItemAnnCreateEdit.get_children()[0].set_text(label)
            menuItemAnnDelete = menuItems[-1]
            menuItemAnnDelete.set_sensitive(selsens)

            menu.popup(None, None, None, 0, 0)

            return False

        return False

    def button_release_event(self, event):
        try: self.eegplot
        except AttributeError: return False

        annman = self.eegplot.annman

        # Write ann file
        if annman.resize :
            annman.ann.save_data()

        self.eegplot.cursor.visible = True
        annman.end_resize()
        annman.selector.visible = True
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

        return False

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

    def autoload(self, fullpath):
        """DEBUG only"""
        if fullpath :
            eeg = load_bmsi(fullpath)
            self.eegplot = EEGPlot(eeg, self.canvas)

            self.toolbar.set_eegplot(self.eegplot)
            self.eegplot.plot()
            eois = eeg.get_associated_files(atype=5, mapped=1)
            self.eoiMenu = self.make_context_menu(eois)

        return False

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
                else:
                    if eeg is None: return 
                    

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

            try: self.eegplot
            except AttributeError: pass
            else: Observer.observers.remove(self.eegplot)        
            try: self.specPlot
            except AttributeError: pass
            else: Observer.observers.remove(self.specPlot)        
                

            self.eegplot = EEGPlot(eeg, self.canvas)
            self.specPlot = SpecPlot(self.axesSpec, self.canvas, self.eegplot)
            self.specMenu = self.make_spec_menu()
            dlg.destroy()
            while gtk.events_pending(): gtk.main_iteration()
            self.toolbar.set_eegplot(self.eegplot)
            try: self.eegplot.plot()
            except:
                msg = exception_to_str('Could not read data:')
                error_msg(msg, title='Error',
                          parent=Shared.windowMain.widget)
                return

                
            eois = eeg.get_associated_files(atype=5, mapped=1)
            self.eoiMenu = self.make_context_menu(eois)
            return False

    def on_menuFileSave_activate(self, event):
        not_implemented(self.widget)

    def on_menuItemAnnBrowser_activate(self, event) :
        try : self.eegplot
        except : pass
        else :
            self.eegplot.annman.dlgbrowser.show_widget()

        return False

    def on_menuHelpAbout_activate(self, event):
        not_implemented(self.widget)

    def on_menuChannelWindow_activate(self, event):
        try: self.eegplot
        except AttributeError:
            simple_msg(
                'You must first select an EEG from the Patients menu',
                title='Error',
                parent=self.widget)
            return

        win = ChannelWin(eegplot=self.eegplot)
        win.show()

    def on_menuHistogramWindow_activate(self, event):
        try: self.eegplot
        except AttributeError:
            simple_msg(
                'You must first select an EEG from the Patients menu',
                title='Error',
                parent=self.widget)
            return

        win = HistogramWin(eegplot=self.eegplot)
        win.show()

    def on_menuAcorrWindow_activate(self, event):
        try: self.eegplot
        except AttributeError:
            simple_msg(
                'You must first select an EEG from the Patients menu',
                title='Error',
                parent=self.widget)
            return
        win = AcorrWin(eegplot=self.eegplot)
        win.show()

    def on_menuEmbedWindow_activate(self, event):
        try: self.eegplot
        except AttributeError:
            simple_msg(
                'You must first select an EEG from the Patients menu',
                title='Error',
                parent=self.widget)
            return
        from embed import EmbedWin
        embedWin = EmbedWin(eegplot=self.eegplot)
        embedWin.show()

    def on_menuView3DWindow_activate(self, event):
        try: self.eegplot
        except AttributeError:
            simple_msg(
                'You must first select an EEG from the Patients menu',
                title='Error',
                parent=self.widget)
            return
        from view3 import View3
        viewWin = View3(eegplot=self.eegplot)

        if viewWin.ok:
            viewWin.show()
        else:
            print >>sys.stderr, 'Got an error code from view3'

    def on_menuSpecWindow_activate(self, event):
        try: self.eegplot
        except AttributeError:
            simple_msg(
                'You must first select an EEG',
                title='Error',
                parent=self.widget)
            return

        specWin = SpecWin(eegplot=self.eegplot)
        specWin.show()                
        
    def on_menuComputeExportToCohstat_activate(self, event):
        try: self.eegplot
        except AttributeError:
            simple_msg(
                'You must first select an EEG from the Patients menu',
                title='Error',
                parent=self.widget)
            return
        eoi = self.eegplot.get_eoi()
        if len(eoi)==64: 
            d = Dialog_CohstatExport(self.eegplot.get_eeg(), eoi)
        else:
            d = Dialog_CohstatExport(self.eegplot.get_eeg())
        d.get_widget().set_transient_for(self.widget)
        d.show_widget()
        
        return False

def update_rc_and_die(*args):
    eegviewrc.lastdir = fmanager.get_lastdir()
    #eegviewrc.figsize = Shared.windowMain.fig.get_size_inches()
    eegviewrc.save()
    gtk.main_quit()

if __name__=='__main__':
    __import__('__init__')
    Shared.windowMain = MainWindow()
    Shared.windowMain.show_widget()

    Shared.windowMain.on_menuFilePreferences_activate(None)

    fullpath = ''
    args = sys.argv
    if len(args) > 1 :
        fullpath = args[1]
    Shared.windowMain.autoload(fullpath)
    Shared.windowMain.widget.connect('destroy', update_rc_and_die)
    Shared.windowMain.widget.connect('delete_event', update_rc_and_die)
    #Shared.windowMain['menubarMain'].hide()
    try: gtk.main()
    except KeyboardInterrupt:
        update_rc_and_die()
