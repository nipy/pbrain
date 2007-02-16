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

import gtk, gobject

from sets import Set

from scipy import array, zeros, ones, sort, absolute, sqrt, divide,\
     argsort, take, arange
from scipy import mean, std

from loc3djr.GtkGLExtVTKRenderWindowInteractor import GtkGLExtVTKRenderWindowInteractor
from loc3djr.plane_widgets import PlaneWidgetsXYZ 

from matplotlib.cbook import exception_to_str
from matplotlib.mlab import detrend_none, detrend_mean, detrend_linear,\
     window_none, window_hanning, log2
from pbrainlib.gtkutils import error_msg, simple_msg, make_option_menu,\
     get_num_value, get_num_range, get_two_nums, str2int_or_err,\
     OpenSaveSaveAsHBox, ButtonAltLabel

from shared import fmanager
from borgs import Shared

from utils import filter_grand_mean, all_pairs_eoi, cohere_bands, power_bands,\
     cohere_pairs, cohere_pairs_eeg, get_best_exp_params,\
     get_exp_prediction, read_cohstat

from matplotlib.backends.backend_gtkagg import FigureCanvasGTKAgg as FigureCanvas
from matplotlib.backends.backend_gtkagg import NavigationToolbar
from matplotlib.figure import Figure

from events import Observer

from autoplay_view3d_dialog import AutoPlayView3Dialog
from array_mapper import ArrayMapper
from image_manager import ImageManager
from grid_manager import GridManager
from mesh_manager import MeshManager

from mpl_windows import VoltageMapWin

from amp_dialog import AmpDialog
from data import Amp

import pickle

def dist(x,y):
    tmp = array(x)-array(y)
    return sqrt(sum(tmp**2))


        
    

class View3(gtk.Window, Observer):
    """
    CLASS: View3
    DESCR: Elaborate GUI window for visualizing structural MRI / CT / coherence data.
    """
    banddict =  {'delta':0, 'theta':1, 'alpha':2,
                 'beta':3, 'gamma':4, 'high':5}

    def __init__(self, eegplot):
        """
        View3 Initialization:

        - self.eegplot initialized from EEGPlot argument
        - self.amp initialized from self.eegplot, consists of list of [channelnum->electrode] mappings
          (e.g. [(1, 'PG', 1), (2, 'PG', 3), (3, 'PG', 5), (4, 'PG', 7), ...]
        - self.cnumDict is dictionary of channel numbers corresponding to self.amp, e.g.
          {('PG', 46): 23, ('C', 6): 98, ('FG', 31): 63, ... }
        - self.eoi is list of all electrodes [('PG', 1), ('PG', 3), ('PG', 5), ('PG', 7),...]
        - self.eoiPairs is all 2-element combinations of self.eoi elements. This has length (X*(X-1)/2).
        - self.selected may correspond to an individual user-selected electrode (see press_left(), toggled(), receive())
        - self.cohCache stores coherence values either from compute_coherence() or from receive() when 'Auto' is checked
        - self.filterGM: whether or not to filter (in some way) based on the computed grand mean
        - self.gridManager

        """
        print "View3.__init__()"
        gtk.Window.__init__(self)

        self.ok = False  # do not show if false
        
        self.eegplot = eegplot
        self.eeg = eegplot.get_eeg()
        self.amp = self.eeg.get_amp()
        self.cnumDict = self.amp.get_channel_num_dict()
        # this gets a copy of the EEGPlot EOI to start with
        self.eoi = eegplot.get_eoi()
        print "View3.__init__(): self.eoi is " , self.eoi
        self.eoiPairs = all_pairs_eoi(self.eoi)
        self.selected = None
        self.cohCache = None  # cache coherence results from other window

        self.csv_fname = None
        
        self.filterGM = eegplot.filterGM
        self.gridManager = None

        # XXX mcc self.meshManager this will handle the brain vtk mesh and orientation
        # the same way gridManager manages the markers (hopefully they
        # will not have to talk to each other too much or at all
        self.meshManager = None
        
        
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
        #interactor.set_size_request(W, int(W/1.3))
        interactor.set_size_request(W*2, W*2) # XXX mcc: hack. maybe try show()ing after add()
      
        interactor.show()
        interactor.Initialize()
        interactor.Start()
        interactor.AddObserver("ExitEvent", lambda o,e,x=None: x)

        self.renderer = vtk.vtkRenderer()
        interactor.GetRenderWindow().AddRenderer(self.renderer)
        self.interactor = interactor

        #self.set_title("View3 Window")
        self.set_border_width(10)

        vbox = gtk.VBox(spacing=3)
        self.add(vbox)
        vbox.show()

        hbox = gtk.HBox()
        hbox.show()
        hbox.set_spacing(3)

        self.imageManager = ImageManager(self.interactor, self.renderer)

        grd = self.eeg.get_loc3djr()

        if grd is not None:
            grd.fh.seek(0)
            ok = self.load_markers(infile=grd.fh)
        else:
            ok = self.load_markers()
        if not ok:
            return
        print "View3.__init__(): after load_markers(), self.eoi is " , self.eoi

        print "self.eeg.filename=", self.eeg.filename, "self.csv_fname=", self.csv_fname
        if (self.csv_fname):
            self.set_title("View3: " + self.eeg.filename + " " + self.csv_fname)

        
        toolbar1 = self.make_toolbar1()
        toolbar1.show()
        toolbar2 = self.make_toolbar2()
        toolbar2.show()

        # line connection attribute
        self.thresholdParams = 'pct.', 0.025


        if sys.platform != 'darwin':
            self.progBar = gtk.ProgressBar()
            self.progBar.set_size_request(10, 100)

            self.progBar.set_orientation(2)  # bottom-to-top
            self.progBar.set_fraction(0)
            self.progBar.show()

        vbox.pack_start(hbox, True, True)
        hbox.pack_start(toolbar1, False, False)
        hbox.pack_start(interactor, True, True)
        if sys.platform != 'darwin':
            hbox.pack_start(self.progBar, False, False)
        vbox.pack_end(toolbar2, False, False)

        # norm is a dictionary mapping band indices to
        # distance/coherence normalizations
        self.norm = {}  
        # text label attributes
        self.textOn = True


        self.interactor.Render()

        # only register when you are built
        Observer.__init__(self)

        self.ampAscii = None   # for external data
        self.ok = True

        # csv_save_electrodes: when saving coherence to EEG, which ones to save
        
        self.csv_save_electrodes = None


    def set_eoi(self, eoi):
        self.eoi = eoi
        self.cohCache = None
        self.eoiPairs = all_pairs_eoi(self.eoi)
        try: del self.cohereResults
        except AttributeError: pass

        try: del self.pxxResults
        except AttributeError: pass
        
    def press_left(self, *args):
        print "View3.press_left()!"
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
    
    def add_separator(self, toolbar):
        toolitem = gtk.SeparatorToolItem()
        toolitem.set_draw(True)
        #toolitem.set_expand(gtk.TRUE)
        toolitem.show_all()
        toolbar.insert(toolitem, -1)
        
    def add_toolbutton1(self, toolbar, icon_name, tip_text, tip_private, clicked_function, clicked_param1=None):
        iconSize = gtk.ICON_SIZE_SMALL_TOOLBAR
        iconw = gtk.Image()
        iconw.set_from_stock(icon_name, iconSize)
            
        toolitem = gtk.ToolButton()
        toolitem.set_icon_widget(iconw)
        toolitem.show_all()
        toolitem.set_tooltip(self.tooltips1, tip_text, tip_private)
        toolitem.connect("clicked", clicked_function, clicked_param1)
        toolitem.connect("scroll_event", clicked_function)
        toolbar.insert(toolitem, -1)

    def make_toolbar1(self):

        self.tooltips1 = gtk.Tooltips()

        toolbar1  = gtk.Toolbar()
        iconSize = gtk.ICON_SIZE_SMALL_TOOLBAR
        toolbar1.set_border_width(5)
        toolbar1.set_style(gtk.TOOLBAR_ICONS)
        toolbar1.set_orientation(gtk.ORIENTATION_VERTICAL)


        def show_grid_manager(button, *args):
            #print "show_grid_manager: args is " , args
            if self.gridManager is not None:
                self.gridManager.show()
            
        self.add_toolbutton1(toolbar1, gtk.STOCK_FLOPPY, 'Load .vtk/.reg file', 'Private', self.mesh_from_file)
        self.add_toolbutton1(toolbar1, gtk.STOCK_SAVE_AS, 'Save .reg file', 'Private', self.registration_to_file)
        self.add_toolbutton1(toolbar1, gtk.STOCK_PREFERENCES, 'Grid properties', 'Private', show_grid_manager)
        self.add_toolbutton1(toolbar1, gtk.STOCK_OPEN, 'Coherence from datafile', 'Private', self.coherence_from_file)
        self.add_toolbutton1(toolbar1, gtk.STOCK_SELECT_COLOR, 'Voltage map', 'Private', self.voltage_map)

        def compute_and_plot(*args):
            self.compute_coherence()
            self.plot_band()
            
        self.add_toolbutton1(toolbar1, gtk.STOCK_EXECUTE, 'Compute coherence', 'Private', compute_and_plot)
        self.add_toolbutton1(toolbar1, gtk.STOCK_PROPERTIES, 'Define coherence normalization window', 'Private', self.compute_norm_over_range)
        
        self.add_separator(toolbar1)
        self.add_toolbutton1(toolbar1, gtk.STOCK_CLEAR, 'Plot band connections', 'Private', self.plot_band, 'mouse1 color')

        self.add_separator(toolbar1)
        self.add_toolbutton1(toolbar1, gtk.STOCK_SAVE_AS, 'Save screenshot to file', 'Private', self.save_image)
        self.add_toolbutton1(toolbar1, gtk.STOCK_JUMP_TO, 'Automatically page the EEG', 'Private', self.auto_play)

        def close(*args):
            print "View3.close(): calling self.destroy()"
            self.destroy()

        self.add_toolbutton1(toolbar1, gtk.STOCK_QUIT, 'Close view 3D', 'Private', close)
        return toolbar1

    def add_toolitem2(self, toolbar, widget, tip_text):
        toolitem = gtk.ToolItem()
        toolitem.add(widget)
        toolitem.show_all()
        toolbar.insert(toolitem, -1)
        

    def make_toolbar2(self):
        """
        'toolbar2' is the bottom toolbar on the View3d window.
        
        self.buttonFollowEvents: the 'Auto' button
        """

        toolbar2  = gtk.Toolbar()
        iconSize = gtk.ICON_SIZE_SMALL_TOOLBAR
        toolbar2.set_border_width(5)
        #toolbar2.set_style(gtk.TOOLBAR_BOTH)
        toolbar2.set_style(gtk.TOOLBAR_ICONS)

        self._activeBand = 'delta'
        #def set_active_band(menuitem, label):
        #    self._activeBand = label
        #    self.plot_band()

        def set_active_band(combobox):
            model = combobox.get_model()
            index = combobox.get_active()
            label = model[index][0]

            self._activeBand = label
            self.plot_band()
            
            return
            
        bandMenu = make_option_menu(['delta', 'theta', 'alpha', 'beta', 'gamma', 'high'], func=set_active_band)
        #toolbar2.append_widget(bandMenu, 'The frequency band', '')
        self.add_toolitem2(toolbar2, bandMenu, 'The frequency band')


        def get_thresh_value(combobox):
            model = combobox.get_model()
            index = combobox.get_active()
            label = model[index][0]
            """
            get_thresh_value(): this function is called when the user
            selects one of the dropdown threshold types ('pct.', 'abs.', etc.)
            and enters a value. this type/value pair is stored in self.thresholdParams.
        
            self.thresholdParams is accessed in the following functions:
               - norm_by_distance()
               - plot_normed_data()
               - get_cutoff()
               - get_cxy_pxy_cutoff()
            """
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
            
            return
            
        #threshMenu, threshItemd  = make_option_menu(('pct.', 'abs.', 'STD', 'ratio', 'plot'), func=get_thresh_value)
        threshMenu = make_option_menu(['pct.', 'abs.', 'STD', 'ratio', 'plot'], func=get_thresh_value)
        #toolbar2.append_widget(threshMenu, 'The threshold type', '')
        self.add_toolitem2(toolbar2, threshMenu, 'The threshold type')


        def low_clicked(button):
            self._low = button.get_active()
            
        self._low = False
        button = gtk.CheckButton('Low')
        button.show()
        button.set_active(self._low)
        #toolbar2.append_widget(button, 'Only plot low', '')
        self.add_toolitem2(toolbar2,button, 'Only plot low')
        button.connect('toggled', low_clicked)

        self.entryMaxDist = gtk.Entry()
        self.entryMaxDist.show()
        self.entryMaxDist.set_text('None')
        self.entryMaxDist.set_width_chars(5)
        #toolbar2.append_widget(self.entryMaxDist, 'Maximum distace', '')
        self.add_toolitem2(toolbar2, self.entryMaxDist, 'Maximum distance')

        self.add_toolbutton1(toolbar2, gtk.STOCK_EXECUTE, 'Replot', 'Private', self.plot_band)

        self.add_separator(toolbar2)

        
        self.buttonFollowEvents = gtk.CheckButton('Auto')
        self.buttonFollowEvents.show()
        self.buttonFollowEvents.set_active(False)
        self.add_toolitem2(toolbar2, self.buttonFollowEvents, 'Automatically update figure in response to changes in EEG window')

        def toggled(button):
            
            if not button.get_active():
                self.selected = None
            else:
                selected = self.eegplot.get_selected()
                if selected is not None:
                    torig, data, trode = selected
                    gname, gnum = trode
                    self.selected = gname, gnum
                    self.plot_band()



        self.buttonSelected = gtk.CheckButton('Selected')
        self.buttonSelected.show()
        self.buttonSelected.set_active(False)
        self.add_toolitem2(toolbar2, self.buttonSelected, 'Only plot coherences with selected electrode')

        self.buttonSelected.connect('toggled', toggled)



        self.buttonPhase = gtk.CheckButton('Phase Threshold')
        self.buttonPhase.show()
        self.buttonPhase.set_active(True)
        print "dude buttonPhase"
        self.add_toolitem2(toolbar2, self.buttonPhase, 'Draw white pipes when abs(phase) is <0.1')

        def phase_toggled(button):
            if not self.cohereResults:
                return
            freqs, cxyBands, phaseBands = self.cohereResults
            self.draw_connections(cxyBands, phaseBands)
            if not button.get_active():
                self.draw_connections(cxyBands, phaseBands, phasethreshold=False)
            else:
                self.draw_connections(cxyBands, phaseBands, phasethreshold=True)

        self.buttonPhase.connect('toggled', phase_toggled)
        


        def show_image_prefs(widget, *args):
            self.imageManager.show_prefs()
            
        self.add_toolbutton1(toolbar2, gtk.STOCK_NEW, 'Image data preferences', 'Private', show_image_prefs)
        self.add_toolbutton1(toolbar2, gtk.STOCK_COPY, 'Dump coherences to CSV', 'Private', self.dump_csv)

        return toolbar2


    def dump_csv_radio_callback(self, widget, data):
        self.dumpCsvRadio = data


    def dump_csv(self, button, *args):
        'dump the coherences to csv'
		
        try: self.cohereResults
        except AttributeError:  self.compute_coherence()

        freqs, cxyBands, phaseBands = self.cohereResults

        vbox = gtk.VBox()
        button1 = gtk.RadioButton(None, 'save everything')
        button1.connect("toggled", self.dump_csv_radio_callback, "radio_all")
        button2 = gtk.RadioButton(button1, 'save only electrodes above threshold')
        button2.connect("toggled", self.dump_csv_radio_callback, "radio_threshold")
        button3 = gtk.RadioButton(button1, 'save only selected electrode')
        button3.connect("toggled", self.dump_csv_radio_callback, "radio_selected")
        
        vbox.pack_start(button1, True, True, 0)
        vbox.pack_start(button2, True, True, 0)
        vbox.pack_start(button3, True, True, 0)

        frame = gtk.Frame()
        frame.add(vbox)

        fmanager.add_widget(frame)
        
        self.dumpCsvRadio = 'radio_all'
        
        filename = fmanager.get_filename()
        if filename is None: return


        if ((self.dumpCsvRadio == 'radio_all') | (self.dumpCsvRadio == 'radio_selected')):
            keys = cxyBands.keys()
        
        if (self.dumpCsvRadio == 'radio_threshold'):
            ret = self.get_cxy_pxy_cutoff(cxyBands, phaseBands)
            if ret is None:
                print >>sys.stderr, 'ERROR: dump_csv w/ threshold: return is None'
                return None
            dvec, cvec, cxy, pxy, predicted, pars, normedvec, cutoff = ret

            maxd = self.entryMaxDist.get_text()
            try: maxd = float(maxd)
            except ValueError: maxd = None

            keys = self.get_supra_threshold_keys(len(self.eoi), cxy, pxy, cutoff, None, maxd)

        fh = file(filename, 'w')
        # this is a hack -- you should pass and parse the band data
        # structure.  Yes Michael, this means you
        print>>fh, 'E1,E2,delta 1-4,theta 4-8,alpha 8-12,beta 12-30,gamma 30-50,high gamma 70-100,delta phase,theta phase,alpha phase,beta phase,gamma phase,high gamma phase'
        keys.sort()
        dumpStrings = []
        for key in keys:
            e1, e2 = key
            e1_str = '%s %d'%e1 # convert e1 (name,num) to string
            e2_str = '%s %d'%e2 # convert e2 (name,num) to string           
            # make comman separated string of floats
            cxy = ','.join(['%f'%val for val in cxyBands[key]])
            pxy = ','.join(['%f'%val for val in phaseBands[key]])            
            # looks like
            # FG 1,FG 3,0.2,0.3,0.1,0.4,0.5,...
            if ((self.dumpCsvRadio == 'radio_all') | (self.dumpCsvRadio == 'radio_threshold')):
                dumpStrings.append('%s,%s,%s,%s'%(e1_str,e2_str,cxy,pxy))

            elif (self.dumpCsvRadio == 'radio_selected'):
                # if we are only dumping the selected electrode's pairs, invert the pair as necessary
                if (self.selected == e1):
                    dumpStrings.append('%s,%s,%s,%s'%(e1_str,e2_str,cxy,pxy))
                elif (self.selected == e2):
                    dumpStrings.append('%s,%s,%s,%s'%(e2_str,e1_str,cxy,pxy))
        dumpStrings.sort()
        for s in dumpStrings:
            print>>fh, s


        simple_msg('CSV file saved to %s'%filename)
        
    def voltage_map(self, button, *args):
        win = VoltageMapWin(self)
        win.show()

    
    def save_registration_as(self, fname):
        print "view3.save_registration_as(", fname,")"
        fh = file(fname, 'w')

        # XXX mcc: somehow get the transform for the VTK actor. aiieeee
        #xform = self.vtkactor.GetUserTransform()
        loc = self.meshManager.contours.GetOrigin()
        pos = self.meshManager.contours.GetPosition()
        scale = self.meshManager.contours.GetScale()
        mat = self.meshManager.contours.GetMatrix()
        orient = self.meshManager.contours.GetOrientation()
        
        print "View3.save_registration_as(): meshManager.contours has origin, pos, scale, mat, orient=", loc, pos, scale, mat, orient, "!!"


        def vtkmatrix4x4_to_array(vtkmat):
            scipy_array = zeros((4,4), 'd')

            for i in range(0,4):
                for j in range(0,4):
                    scipy_array[i][j] = mat.GetElement(i,j)

            return scipy_array

        scipy_mat = vtkmatrix4x4_to_array(mat)

        pickle.dump(scipy_mat, fh)
        fh.close()

    def registration_to_file(self, *args):
        print "View3.registration_to_file()"

            

        def ok_clicked(w):
            fname = dialog.get_filename()
            try: self.save_registration_as(fname)
            except IOError:
                error_msg('Could not save data to %s' % fname,
                          )
            else:
                self.fileName = fname
                dialog.destroy()
            
        dialog = gtk.FileSelection('Choose filename for registration .reg data file')
        dialog.ok_button.connect("clicked", ok_clicked)
        dialog.cancel_button.connect("clicked", lambda w: dialog.destroy())
        dialog.show()
        

    def mesh_from_file(self, *args):
        print "View3.mesh_from_file()"

        filename = fmanager.get_filename(title="Select .vtk mesh file")
        if filename is None: return
        if not os.path.exists(filename):
            error_msg('File %s does not exist' % filename, parent=dlg)
            return

        try: fh = file(filename)
        except IOError, msg:
            msg = exception_to_str('Could not open %s' % filename)
            error_msg(msg)
            return
        fh.close() #?

        # now also load the .reg file

        reg_filename = fmanager.get_filename(title="Select .reg registration file")
        if reg_filename is None: return
        if not os.path.exists(reg_filename):
            error_msg('File %s does not exist' % reg_filename, parent=dlg)
            return

        try: fh = file(reg_filename)
        except IOError, msg:
            msg = exception_to_str('Could not open %s' % reg_filename)
            error_msg(msg)
            return
        fh.close() #?

        self.load_mesh(filename, reg_filename)

        
        
        

    def coherence_from_file(self, *args):

        filename = fmanager.get_filename(title="Select .dat file")
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
        print "View3.coherence_from_file(): called read_cohstat(): cxy.keys=", cxy.keys()

        seen = {}
        for i,j in cxy.keys():
            seen[i] = 1
            seen[j] = 1
        channels = seen.keys()
        channels.sort()

        print "View3.coherence_from_file(): channels is ", channels, "NOT starting AmpDialog"

        amp_filename = fmanager.get_filename(title="Select .amp file")
        if amp_filename is None: return
        if not os.path.exists(amp_filename):
            error_msg('File %s does not exist' % amp_filename, parent=dlg)
            return

        try: fh = file(amp_filename)
        except IOError, msg:
            msg = exception_to_str('Could not open %s' % amp_filename)
            error_msg(msg)
            return

        def parse_amp_file(fh):
            amp_list = []
            while 1:
                line = fh.readline().strip()
                #print "line='%s'" % line
                if (line == None):
                    break
                if (line == ''):
                    break
                if (line[0] == '#'):
                    continue
                # every line should be like
                # [int] [letters] [int]
                # e.g. 1 FG 4
                vals = line.split()
                #print vals
                if (len(vals) == 1):
                    # empty channel.. ignore
                    print "parse_amp_file(): ignoring empty line ", vals
                    continue
                if (len(vals) != 3):
                    raise RuntimeError, 'Bad .amp file on line %s' % line
                # ok now make sure this channel is in self.eoi, otherwise
                # we don't want to try to plot that Cxy value later

                electrode = (vals[1], int(vals[2]))
                if electrode not in self.eoi:
                    print "View3.parse_amp_file(): skipping electrode ", electrode, ": not in self.eoi"
                    continue
                amp_list.append((int(vals[0]),vals[1], int(vals[2])))
            fh.close()
            return amp_list
        
        amplist_from_file = parse_amp_file(fh)
        amp = Amp()
        amp.set_channels(amplist_from_file)
        
        
        #ampDlg = AmpDialog(channels, self)
        #ampDlg.show()
        print "not running ampDlg"
        #amp = ampDlg.run()

        print "view3: ampdialog returned: amp is " , amp

        #amp = ampDlg.get_amp()
        if amp is None: return
        self.amp = amp
        # Convert the cyx, pxy to electrode dicts and filter out
        # channels not in the eoi

        d = amp.get_channelnum_dict()

        print "amp channelnum dict is like this=", d

        # make sure the keys agree
        Cxy = {}; Pxy = {}
        keys = cxy.keys()
        skipd = {}
        eoi = amp.to_eoi()
        self.set_eoi(eoi)

        for i,j in keys:
            if not d.has_key(i):
                skipd[i] = 1
                #print "skipping this cause key i=", i, " and .amp does not have that"
                continue
            if not d.has_key(j):
                skipd[j] = 1
                #print "skipping this cause key j=", j, " and .amp does not have that"
                continue
            key = d[i], d[j]

            Cxy[key] = cxy[(i,j)]
            Pxy[key] = pxy[(i,j)]


        skipped = skipd.keys()
        skipped.sort()
        if len(skipped):
            print >>sys.stderr, 'Skipping these electrodes not in eoi\n\t%s eoi'%skipped

        # ok but now we ALSO want to skip Cxy entries for channels that we don't have
        # csv points for
        
        self.cohereResults = None, Cxy, Pxy
        self.plot_band()


    def auto_play(self, *args):
        
        tmin, tmax = self.eegplot.get_time_lim()
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

    def load_mesh(self, mesh_filename, reg_filename):
        self.meshManager = MeshManager(self.interactor, self.renderer, mesh_filename, reg_filename)
        
    def load_markers(self, *args, **kwargs):

        infile = kwargs.get('infile', None)
        if infile is None:
            self.csv_fname = fmanager.get_filename(title='Enter marker filename: *.csv')
            if self.csv_fname is None: return

            try: infile = file(self.csv_fname, 'r')
            except IOError, msg:
                err = '\n'.join(map(str, msg))
                error_msg('Could not open %s for reading\n%s' % (self.csv_fname,err),
                          parent=self)
                self.gridManager.markers = None
                return

        print "View3.load_markers(): initializing GridManager(): self.eoi is uh ",self.eoi, "of length" , len(self.eoi)
        self.gridManager = GridManager(self.interactor, self.renderer, infile)
        if not self.gridManager.ok:
            return

        # here, we bring up a message if we have tried to load markers not in EOI.

        # "EOI" does not refer to which ones are specified in the
        # EEGPlot window, but instead just which electrodes are in the
        # BNI/EEG file. uhhhh

        # XXX: we may want to also make csv markers which are not in the
        # BNI/EEG file to look all small and greyed out. however
        # GridManager may have no access to the appropriate info.

        # validate the marker dict with eoi
        bad = []
        for key in self.eoi:
            if not self.gridManager.markerd.has_key(key):
                bad.append(key)

        if len(bad):
            print "View3.load_markers(): self.eegplot.get_eoi() is now " , self.eegplot.get_eoi()
            s = ', '.join(['%s %d'%key for key in bad])
            simple_msg('Ignoring these electrodes not in marker\n\t%s'%s)
            for key in bad:
                print "View3.load_markers(): removing key ", key ,"from self.eoi"
                self.eoi.remove(key)
            self.eoiPairs = all_pairs_eoi(self.eoi)
            print "View3.load_markers(): self.eegplot.get_eoi() is now " , self.eegplot.get_eoi()
            

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
                while gtk.events_pending(): gtk.main_iteration()

        

        if setTime is None:
            tmin, tmax = self.eegplot.get_time_lim()
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

        
        eeg = self.eegplot.get_eeg()
        dt = 1.0/eeg.freq

        t, data = self.eeg.get_data(tmin, tmax)

        Nt = len(t)
        NFFT = int(2**math.floor(log2(Nt)-2))
        print 'NFFT', NFFT
        NFFT = min(NFFT, 512)
        if self.filterGM:            
            data = filter_grand_mean(data)

        print "View3.compute_coherence(): self.eoiPairs = ", self.eoiPairs
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
    
    def plot_band(self, *args):
        bandind = self.get_band_ind()

        try: self.cohereResults
        except AttributeError:  self.compute_coherence()

        freqs, cxyBands, phaseBands = self.cohereResults
        print "plot_band(): len(cxyBands)= ", len(cxyBands)
        self.draw_connections(cxyBands, phaseBands)

        
        try: pxx = self.pxxResults
        except AttributeError: pass
        else:
            datad = dict([(key, 10*math.log10(vals[bandind])) for key, vals in pxx.items()])

            self.gridManager.scalarVals = []
            self.gridManager.set_scalar_data(datad)
        #print datad
        
        
    def norm_by_distance(self, Cxy, bandind=None, pars=None):
        """
        Convert the cxy dict to an array over the eoi pairs and
        compute the best exponential fit.  If the optimizer doesn't
        converge, it will raise an error and return None.
        """


        # Cxy is all pairs and their coherence values..
        print "View3.norm_by_distance(Cxy=", len(Cxy), " arrays, bandind=", bandind, "pars=", pars
        if bandind is None:
            bandind = self.get_band_ind()
            print "View3.norm_by_distance(): bandind calculated as ", bandind

        cvec = array([Cxy[key][bandind] for key in self.eoiPairs])
        print "View3.norm_by_distance(): cvec=", cvec.shape, "elements"
        dvec = array([dist(self.xyzd[e1], self.xyzd[e2])
                      for e1,e2 in self.eoiPairs])
        print "View3.norm_by_distance(): dvec=", dvec.shape, "elements"

        threshType, threshVal = self.thresholdParams
        if threshType=='abs.':
            predicted = ones(cvec.shape, 'd')
            return dvec, cvec, predicted, None
        
        print "View3.norm_by_distance(): pars=", pars
        if pars is None:
            f = file("getbestexp.pickle", "w")
            pars = get_best_exp_params(dvec, cvec)
            pickle.dump((dvec, cvec), f)
            f.close()
            print "View3.norm_by_distance(): pars calculated to be=", pars
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
        win.resize(800,400)
        tmin, tmax = self.eegplot.get_time_lim()
        win.set_title("View3: " + self.eeg.filename + " " + self.csv_fname + "\t" + self._activeBand + "\t" + str(tmin) +":" + str(tmax))
                

        vbox = gtk.VBox(spacing=3)
        win.add(vbox)
        vbox.show()


        fig = Figure(figsize=(7,5), dpi=72)

        self.canvas = FigureCanvas(fig)  # a gtk.DrawingArea
        self.canvas.show()
        vbox.pack_start(self.canvas, True, True)


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
                ax.plot(dvec, cutoff*ones(dvec.shape, 'd'), 'r-')

        else:

            ax1 = fig.add_subplot(211)
            ax1.set_title('Coherence vs distance')            
            ind = argsort(dvec)
            dsort = take(dvec, ind)
            psort = take(predicted, ind)
            ax1.plot(dvec, cvec, 'b,',
                     dsort, psort, 'g-')

            if threshType=='abs.':
                ax1.plot(dvec, cutoff*ones(dvec.shape, 'd'), 'r-')
            ax1.set_ylabel('Absolute')

            ax2 = fig.add_subplot(212)
            ax2.plot(dvec, normedvec, 'k,',
                     dsort, ones(dsort.shape, 'd'), 'g-')
            ax2.set_ylabel('Normalized')
            ax2.set_xlabel('Distance (cm)')            

            #print 'threshType', threshType
            if threshType in ('pct.', 'STD', 'ratio'):
                #print 'plotting line at', threshVal
                ax2.plot(dvec, cutoff*ones(dvec.shape, 'd'), 'r-')
                

        toolbar = NavigationToolbar(self.canvas, win)
        toolbar.show()
        vbox.pack_start(toolbar, False, False)
        win.show()
        

    def get_cutoff(self, normedvec):
        """
        get_cutoff(): examines self.thresholdParams and computes the appropriate
        cutoff value based on the threshold type/value.

        for example:
          - threshold type 'abs.' returns that precise value.
          - threshold type 'pct.' 
        

        """

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

        stored = self.norm.get(bandind, None)
         
        if stored is None:
            # compute local norm
            dvec, cvec, predicted, pars = self.norm_by_distance(Cxy)
            print "View3.get_cxy_pxy_cutoff(). stored: cvec=", cvec, "predicted=", predicted
            normedvec = divide(cvec, predicted)
            cutoff = self.get_cutoff(normedvec)
        else:
            pars, cutoff = stored
            dvec, cvec, predicted, tmp = self.norm_by_distance(Cxy, pars=pars)
            print "View3.get_cxy_pxy_cutoff(). stored: cvec=", cvec, "predicted=", predicted
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

    def get_supra_threshold_keys(self, N, cxy, pxy, cutoff, useSelected, maxd):
        """
        get_supra_threshold_keys(): abstracted function that returns a list
        of keys that are above or below a given cutoff mark (based on the
        threshold type/value). This is used by both draw_connections() and
        dump_csv().
        """
        returnKeys = []
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
                coherence = cxy[key]
                #print e1, e2, coherence, cutoff
                if self._low:
                    if coherence>cutoff: continue
                else:
                    if coherence<cutoff: continue

                #print 'get_supra_threshold_keys: found '
                #print e1, e2, coherence, cutoff

                returnKeys.append(key)
        
        return returnKeys
        
    def draw_connections(self, Cxy, Pxy, phasethreshold=True):
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
        
        self.gridManager.flush_connections()

        supra_threshold_keys = self.get_supra_threshold_keys(N, cxy, pxy, cutoff, useSelected, maxd)

        for key in supra_threshold_keys:
            (e1, e2) = key
            phase = pxy[key]
            # XXX mcc I think this is where the 'white pipes' come from..?
            if (phasethreshold==True):
                if abs(phase)<0.1: phasemap = None
                elif phase>0: phasemap = posphase  # 1 leads 2
                else: phasemap = negphase          # 2 leads 1
            else:
                if phase>0: phasemap = posphase  # 1 leads 2
                else: phasemap = negphase
            ok = self.gridManager.connect_markers(e1, e2, scalarfunc=phasemap)
            if not ok:
                error_msg('Giving up', parent=self)
                break
        self.interactor.Render()

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




                
        






