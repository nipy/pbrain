import sys, os, re
import gtk, gobject, pygtk
pygtk.require('2.0')


from matplotlib.numerix import arange

from matplotlib.cbook import exception_to_str
from matplotlib.mlab import detrend_none, detrend_mean, detrend_linear,\
     window_none, fftsurr, window_hanning, prctile #took out mean
import matplotlib.numerix as nx
from scipy import mean
from matplotlib.backends.backend_gtkagg import FigureCanvasGTKAgg as FigureCanvas
from matplotlib.backends.backend_gtk import NavigationToolbar2GTK

from matplotlib.figure import Figure

from pbrainlib.gtkutils import str2num_or_err, donothing_callback, \
     Dialog_FileSelection, Dialog_DirSelection, \
     simple_msg, ignore_or_act, not_implemented, \
     make_option_menu_from_strings

import CodeRegistry
from data import EOI
from utils import export_to_cohstat, filter_grand_mean, \
     all_pairs_eoi, cohere_bands, cohere_pairs_eeg, export_cohstat_xyz, \
     hilbert_phaser, synchrony, bandpass, gen_surrogate_data

from gladewrapper import PrefixWrapper
from shared import fmanager, eegviewrc
from borgs import Shared
from events import Observer

import tempfile
import pickle

import pylab


# use this if you want to store some information about the dialogs
# between calls.
storeParamsOnOK = {}

class Dialog_SelectElectrodes(gtk.Dialog):
    """
    CLASS: Dialog_SelectElectrodes
    DESCR: Select a subset of trodes and call ok_callback(selectedTrodes).

    trodes and selectedTrodes are a list of tuples; each tuple is
    (grdName, grdNum).
    
    """
    def __init__(self, trodes, ok_callback, selected=None):
        gtk.Dialog.__init__(self)

        self.set_title("Select electrodes")


        if selected is None: self.selected = EOI()
        else: self.selected = selected

        COLUMN_GRDNAME=0
        COLUMN_GRDNUM=1


        model = gtk.ListStore(gobject.TYPE_STRING,
                              gobject.TYPE_UINT)

        # a dictionary from [grdName][grdNum] keys to iters
        iterMap = {}
        for (grdName, grdNum) in trodes:
            iter = model.append()    
            model.set(iter,
                      COLUMN_GRDNAME, grdName,
                      COLUMN_GRDNUM,  grdNum)
            iterMap.setdefault(grdName, {})[grdNum]=iter



        # set up the treeview to do multiple selection
        treeview = gtk.TreeView(model)
        treeview.set_rules_hint(True)

        column = gtk.TreeViewColumn('Grid Name', gtk.CellRendererText(),
                                    text=COLUMN_GRDNAME)
        treeview.append_column(column)

        column = gtk.TreeViewColumn('Grid Number', gtk.CellRendererText(),
                                    text=COLUMN_GRDNUM)
        treeview.append_column(column)


        treeview.get_selection().set_mode(gtk.SELECTION_MULTIPLE)

        # select all the electrodes in the initially selected list
        treeViewSel = treeview.get_selection()
        for (grdName, grdNum) in self.selected:
            try: iter = iterMap[grdName][grdNum]
            except KeyError: continue
            treeViewSel.select_iter(iter)



        # when you click ok, call this function for each selected item
        def return_foreach(model, path, iter, selected):
            selected.append(
                (model.get_value(iter, COLUMN_GRDNAME),
                 model.get_value(iter, COLUMN_GRDNUM),                 
                 ))

        def getiter_foreach(model, path, iter, selected):
            selected.append(iter)

        def ok_clicked(event):
            trodes = []
            treeview.get_selection().selected_foreach(return_foreach, trodes)
            #print 'len trodes', len(trodes)
            #print trodes
            self.selected.set_electrodes(trodes)
            start, end = self.buffer.get_bounds()
            self.selected.description = self.buffer.get_text(start, end)
            ok_callback(self.selected)

        def invert_selection(*args):
            iters = []
            treeview.get_selection().selected_foreach(getiter_foreach, iters)
            treeview.get_selection().select_all()
            for iter in iters:
                treeview.get_selection().unselect_iter(iter)

        def changed(*args):
            iters = []
            treeview.get_selection().selected_foreach(getiter_foreach, iters)
            self.update_status_bar('Selected electrodes: %d' % len(iters))

        treeview.get_selection().connect("changed", changed)
            
        label = gtk.Label('Select electrodes from list')
        label.show()
        self.vbox.pack_start(label, False, False)
    
        sw = gtk.ScrolledWindow()
        sw.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        sw.set_policy(gtk.POLICY_NEVER,
                      gtk.POLICY_AUTOMATIC)

        sw.add(treeview)
        self.vbox.pack_start(sw)

        frame = gtk.Frame('Select')
        frame.show()
        frame.set_border_width(5)
        self.vbox.pack_start(frame, False, False)

        hbox = gtk.HBox()
        hbox.show()
        button = gtk.Button('All')
        button.connect(
            "clicked", lambda *args: treeview.get_selection().select_all() )
        hbox.pack_start(button)

        button = gtk.Button('None')
        button.connect(
            "clicked", lambda *args: treeview.get_selection().unselect_all() )
        hbox.pack_start(button)

        button = gtk.Button('Invert')
        button.connect("clicked", invert_selection )        
        hbox.pack_start(button)

        frame.add(hbox)

        frame = gtk.Frame('Description')
        frame.show()
        frame.set_border_width(5)
        self.vbox.pack_start(frame, False, False)

        textView = gtk.TextView()
        textView.show()

        self.buffer = gtk.TextBuffer()
        self.buffer.set_text(self.selected.description)
        textView.set_buffer(self.buffer)
        textView.set_editable(True)
        textView.set_cursor_visible(True)
        frame.add(textView)

        vbox = gtk.VBox()
        vbox.show()
        
        hbox = gtk.HBox()
        button = gtk.Button('OK')
        button.connect("clicked", ok_clicked )
        hbox.pack_start(button)

        button = gtk.Button('Cancel')
        button.connect("clicked", self.destroy_dialog)
        hbox.pack_start(button)
        vbox.pack_start(hbox)

        self.statbar = gtk.Statusbar()
        self.statbar.show()
        self.statbarCID = self.statbar.get_context_id(
            "Select electrode statusbar")

        vbox.pack_end(self.statbar)

        self.vbox.pack_end(vbox, False)

        self.set_default_size(175, 500)
        self.show_all()

    def get_selected(self):
        return self.selected


    def destroy_dialog(self, *args):
        self.destroy()
    

    def update_status_bar(self, msg):

        try: self.statbar.remove( self.statbarCID, self.statbarMID )
        except AttributeError: pass
            
        self.statbarMID = self.statbar.push(self.statbarCID, msg)
        return True

class Dialog_CohstatExport(PrefixWrapper):
    """
    CLASS: Dialog_CohstatExport
    DESCR: Exporting coherence statistics
    """
    prefix='dlgCE_'
    widgetName = 'dialogCohstatExport'

    def __init__(self, eeg, eoi=None):        
        PrefixWrapper.__init__(self)

        self.eeg = eeg
        # if the number of channels is already 64, select all for
        # cohstat, else select none

        self.eoi64=EOI() 
        if eoi is not None:
            if len(eoi) != 64:
                raise RuntimeError, 'eoi must have 64 electrodes'
            self.eoi64 = eoi
        elif eeg.channels==64:
            self.eoi64.set_electrodes(self.eeg.get_amp().to_eoi())

        if storeParamsOnOK.has_key(self.widgetName):
            self.set_params(storeParamsOnOK[self.widgetName])
        else:
            # set some defaults
            self['radiobuttonCoh'].set_active(1)
            self['checkbuttonGM'].set_active(0)
            self['entryFile'].set_text(
                os.path.join(fmanager.get_lastdir(), 'cohstat.dat'))

    def on_button64_clicked(self, event):
        """Launch the electrode selection dialog"""


        def select_callback(selected):
            """
            On OK, Make sure the number of electrodes is 64.  If it is,
            save the electrodes and kill the selection dialog
            """
            if len(selected) != 64:
                simple_msg(
                    'You must select exactly 64 electrodes for Cohstat.  ' +
                    "Don't blame me, talk to Fawaz",
                    title='Selection error',
                    parent=d)
                return
            #print 'setting eoi64', len(selected)
            self.eoi64.set_electrodes(selected)
            #print 'sett eoi64', len(self.eoi64)
            d.destroy_dialog()

        d = Dialog_SelectElectrodes(
            trodes=self.eeg.get_amp().to_eoi(),
            selected=self.eoi64,
            ok_callback=select_callback,
            )
        d.set_transient_for(self.widget)

    def on_buttonCohereParams_clicked(self, event):
        self._launch_coherepars_dialog()

    def _launch_coherepars_dialog(self):

        def ok_callback(coherePars):

            if self.eeg.get_num_samples() < 2*coherePars['NFFT']:
                simple_msg(
                """
Length of EEG=%d which is less than 2*NFFT=%d

This is illegal.
""" % ( self.eeg.get_num_samples(), 2*coherePars['NFFT']),
                title='Error', 
                parent=self.widget)
                return 
            d.hide_widget()
            
        d = Dialog_CoherenceParams(okCallback=ok_callback)
        d.show_widget()
        d.get_widget().set_transient_for(self.widget)
        
    def on_buttonPhaseParams_clicked(self, event):
        not_implemented(self.widget)

    def on_buttonBrowse_clicked(self, event):

        def ok_callback(dlg):
            fname = dlg.get_filename()
            fmanager.set_lastdir(fname)
            # make sure the file is writable
            try: test = file(fname, 'w')
            except IOError:
                simple_msg('Could not open %s for writing\n'  % fname +
                              'Please select another file.',
                              title='File selection error', 
                              parent=self.widget)
                return
            else: test.close()

            self['entryFile'].set_text(fname)
            dlg.destroy()

        d = Dialog_FileSelection(
            defaultDir=fmanager.get_lastdir(),
            okCallback=ok_callback,
            title='Select cohstat output file',
            parent=self.widget)

    def on_buttonLoc3d_clicked(self, event):

        def ok_callback(dlg):
            fname = dlg.get_filename()
            fmanager.set_lastdir(fname)
            # make sure the file is writable
            try: test = file(fname, 'r')
            except IOError:
                simple_msg('Could not open %s for reading\n'  % fname +
                           'Please select another file.',
                           title='File selection error', 
                           parent=self.widget)
                return
            else: test.close()

            self['entryLoc3DFile'].set_text(fname)
            dlg.destroy()

        d = Dialog_FileSelection(
            defaultDir=fmanager.get_lastdir(),
            okCallback=ok_callback,
            title='Select Loc3d Jr file',
            parent=self.widget)

    def on_buttonCancel_clicked(self, event):
        self.hide_widget()

    def get_params(self):
        m = {}

        try:
            #print 'get_params eoi64', len(self.eoi64)
            m['eoi64'] = self.eoi64
        except AttributeError:
            #print 'get_params eoi64 empty'
            m['eoi64'] = EOI()
        
        m['filter grand mean'] = self['checkbuttonGM'].get_active()

        if self['radiobuttonPhase'].get_active():
            m['cohere method'] = 'phase synchrony'
            # TODO: get params
        else:
            m['cohere method'] = 'coherence'
            d = Dialog_CoherenceParams()
            m['cohere pars'] = d.get_params()

        m['outfile'] = self['entryFile'].get_text()

        if self['entryMinTime'].get_text()=='': m['tmin'] = 0
        else:
            m['tmin'] = str2num_or_err(self['entryMinTime'].get_text(),
                                       label=self['labelMinTime'],
                                       parent=self.widget)
        if self['entryMaxTime'].get_text()=='': m['tmax'] = None
        else:
            m['tmax'] = str2num_or_err(self['entryMaxTime'].get_text(),
                                       label=self['labelMaxTime'],
                                       parent=self.widget)


        locfile = self['entryLoc3DFile'].get_text()

        try: fh = file(locfile, 'r')
        except IOError: m['loc3d'] = None
        else:
            d = {}
            for line in fh:
                vals = line.split(',')
                gname, gnum = vals[0].split()
                gnum = int(gnum)
                x, y, z = float(vals[1]), float(vals[2]), float(vals[3])
                d[(gname, gnum)] = x,y,z
            m['loc3d'] = d
        return m


    def set_params(self, m):

        self.eoi64 = m['eoi64']
        
        if m['filter grand mean']:
            self['checkbuttonGM'].set_active(1)

        if m['cohere method']=='phase synchrony':
            self['radiobuttonPhase'].set_active(1)
        else:
            self['radiobuttonCoh'].set_active(1)
            

        self['entryFile'].set_text(m['outfile'])

        if m['tmin'] is not None:
            self['entryMinTime'].set_text(str(m['tmin']))

        if m['tmax'] is not None:
            self['entryMaxTime'].set_text(str(m['tmax']))
            
        
    def on_buttonOK_clicked(self, event):
        #print 'len eoi64', len(self.eoi64)
        pars = self.get_params()
        
        if len(pars['eoi64'])!=64:
            simple_msg('You must first select 64 electrodes',
                          title='Error',
                          parent=self.widget)
            return


        
        #self['radiobuttonCoh'].get_active()
        if pars['cohere method'] is 'phase synchrony':
            simple_msg('Phase synchrony not yes implemented',
                          parent=self.widget)
            return
        
        coherePars = pars['cohere pars']

        if self.eeg.get_num_samples() < 2*coherePars['NFFT']:
            self._launch_coherepars_dialog()
            return
        
        indices = self.eoi64.to_data_indices(self.eeg.get_amp())
        
        # TODO: should I be operating on eeg.data here or a copy?
        if pars['filter grand mean']:
            self.eeg.data = filter_grand_mean(self.eeg.data)


        indMin, indMax = 0, self.eeg.get_num_samples()
        if pars['tmin'] is not None:
            indMin = max(indMin, int(pars['tmin']*self.eeg.freq))

        if pars['tmax'] is not None:
            indMax = min(indMax, int(pars['tmax']*self.eeg.freq))
        
        if indMax-indMin<2*coherePars['NFFT']:
            simple_msg(
                'NFFT too long for this time interval.  Please reduce NFFT\n',
                title='Error',
                parent=self.widget)
            return
            
        try: outfileHandle = file(pars['outfile'], 'wb')
        except IOError:
            simple_msg('Could not open %s for writing\n' % pars['outfile'],
                          title='Error',
                          parent=self.widget)
            return

        self.hide_widget()


        dlg = gtk.Dialog('Computing coherences', flags=gtk.DIALOG_MODAL)
        dlg.set_transient_for(Shared.windowMain.widget)
        dlg.show()

        progBar = gtk.ProgressBar()
        progBar.set_size_request(300, 40)

        progBar.set_text('Almost there...')
        progBar.set_fraction(0)
        progBar.show()
        dlg.vbox.pack_start(progBar)

        def progress_callback(frac,  msg):
            #print msg, frac
            progBar.set_text(msg)
            progBar.set_fraction(frac)
            while gtk.events_pending(): gtk.main_iteration()

        eoiPairs = all_pairs_eoi(self.eoi64)
        
        try:
            Cxy, Phase, freqs = cohere_pairs_eeg(
                self.eeg,
                eoiPairs,
                indMin = indMin,
                indMax = indMax,
                NFFT=coherePars['NFFT'],
                detrend=coherePars['detrend'],
                window=coherePars['window'],
                noverlap=coherePars['overlap'],
                preferSpeedOverMemory=1,
                progressCallback=progress_callback)
            bands = ( (1,4), (4,8), (8,12), (12,30), (30,55) )
            cxyBands, phaseBands = cohere_bands(
                Cxy, Phase, freqs, eoiPairs, bands,
                progressCallback=progress_callback)
            
            s = export_to_cohstat(cxyBands, phaseBands, eoiPairs)

        except RuntimeError, e:
            simple_msg(
                'Caught an error trying to compute coherence bands' +
                'for cohstat:\n\n%s' % e, parent=self.widget)
            return
        

        outfileHandle.write(s)
        outfileHandle.close()
        dlg.destroy()
        simple_msg('Cohstat data successfully written to\n' +\
                      'file %s' % pars['outfile'],
                      title='Congratulations',
                      parent=Shared.windowMain.widget)

        grd = self.eeg.get_grd()
        if grd  is not None:
            xyz = grd.get_xyz_for_eoi(self.eoi64)
            s = export_cohstat_xyz( [ xyz[trode] for trode in self.eoi64 ] )
            fh = file(pars['outfile']+'.xyz', 'wb')
            fh.write(s)
            fh.close()

        loc3d = pars['loc3d']

        if loc3d is not None:
            XYZ = []
            for trode in self.eoi64:
                try: XYZ.append(loc3d[trode])
                except KeyError:
                    simple_msg('No label in loc3djr file for %s' % trode,
                               title='Oops!',
                               parent=Shared.windowMain.widget)
                    XYZ = None
                    break
            if XYZ is not None:
                s = export_cohstat_xyz(XYZ)
                fh = file(pars['outfile']+'loc3d.xyz', 'wb')
                fh.write(s)
                fh.close()

        storeParamsOnOK[self.widgetName] = self.get_params()

class Dialog_CoherenceParams(PrefixWrapper):
    """
    CLASS: Dialog_CoherenceParams
    DESCR: Get the coherence params.  On OK, will call okCallback(m), where
    m is a dictionary

      m = {'NFFT' : integer power of 2,
           'overlap' : integer FFT segment overlap,
           'window' : windowing function, callable,
           'detrend' : detrending function, callable}

    """

    prefix = 'dlgCP_'
    widgetName = 'dialogCoherenceParams'
    def __init__(self, okCallback=donothing_callback):
        PrefixWrapper.__init__(self)
        self.okCallback = okCallback

        self['comboNFFT'].set_popdown_strings(
            [str(2**i) for i in range(4,17)])

        if storeParamsOnOK.has_key(self.widgetName):
            self.set_params(storeParamsOnOK[self.widgetName])
        else:
            self['radiobuttonWindowHanning'].set_active(1)
            self['radiobuttonDetrendNone'].set_active(0)
            self['comboNFFT'].entry.set_text('2048')

        
    def on_buttonOK_clicked(self, event):
        storeParamsOnOK[self.widgetName] = self.get_params()
        self.okCallback(self.get_params())


    def get_params(self):
        """
        Return a dictionary of coherence params
        """

        try: overlap = int(self['entryOverlap'].get_text())
        except ValueError:
            label = self['labelOverlap'].get_label()
            simple_msg('%s entry box must be an integer' % label,
                        parent=self.widget)
            return
            
        if self['radiobuttonWindowNone'].get_active():
            window = window_none
        else:
            window = window_hanning
            
        if self['radiobuttonDetrendNone'].get_active():
            detrend = detrend_none
        elif self['radiobuttonDetrendMean'].get_active():
            detrend = detrend_mean
        else:
            detrend = detrend_linear

        m = {'NFFT' : int(self['comboNFFT'].entry.get_text()),
             'overlap' : overlap,
             'window' : window,
             'detrend' : detrend}

        return m


    def set_params(self, m):

        self['entryOverlap'].set_text(str(m['overlap']))
    
        self['radiobuttonWindowNone'].set_active(
            m['window']==window_none)
            
        if m['detrend']==detrend_none:
            self['radiobuttonDetrendNone'].set_active(1)
            
        elif m['detrend']==detrend_mean:
            self['radiobuttonDetrendMean'].set_active(1)                     
        else:
            self['radiobuttonDetrendLinear'].set_active(1)

        
        self['comboNFFT'].entry.set_text(str(m['NFFT']))

class Dialog_EventRelatedSpec(PrefixWrapper):
    """
    CLASS: 
    DESCR: Get the event related spectrogram params.  On OK, will call
    okCallback(m), where m is a dictionary

      m = {'event_length': integer power of 2,
           'NFFT' : integer power of 2,
           'overlap' : integer FFT segment overlap,
           'window' : windowing function, callable,
           'detrend' : detrending function, callable}

    """

    prefix = 'dlgERSpec_'
    widgetName = 'dialogEventRelatedSpec'
    def __init__(self, okCallback=donothing_callback):
        PrefixWrapper.__init__(self)
        self.okCallback = okCallback

        self['combo_event_length'].set_popdown_strings(
            [str(2**i) for i in range(4,17)])

        self['comboNFFT'].set_popdown_strings(
            [str(2**i) for i in range(4,17)])

        if storeParamsOnOK.has_key(self.widgetName):
            self.set_params(storeParamsOnOK[self.widgetName])
        else:
            self['radiobuttonWindowHanning'].set_active(1)
            self['radiobuttonDetrendNone'].set_active(0)
            self['combo_event_length'].entry.set_text('512')
            self['comboNFFT'].entry.set_text('512')
            self['entryOverlap'].set_text('477')

        
    def on_buttonOK_clicked(self, event):
        print "Dialog_EventRelatedSpec.on_buttonOK_clicked()! get_params is ", self.get_params()
        storeParamsOnOK[self.widgetName] = self.get_params()
        self.okCallback(self.get_params())
        self.hide_widget()

    def on_buttonCancel_clicked(self, event):
        self.hide_widget()
        pass


    def get_params(self):
        """
        Return a dictionary of coherence params
        """

        try: overlap = int(self['entryOverlap'].get_text())
        except ValueError:
            label = self['labelOverlap'].get_label()
            simple_msg('%s entry box must be an integer' % label,
                        parent=self.widget)
            return
            
        if self['radiobuttonWindowNone'].get_active():
            window = window_none
        else:
            window = window_hanning
            
        if self['radiobuttonDetrendNone'].get_active():
            detrend = detrend_none
        elif self['radiobuttonDetrendMean'].get_active():
            detrend = detrend_mean
        else:
            detrend = detrend_linear

        m = {'event length' : int(self['combo_event_length'].entry.get_text()),
             'NFFT' : int(self['comboNFFT'].entry.get_text()),
             'overlap' : overlap,
             'window' : window,
             'detrend' : detrend}

        return m


    def set_params(self, m):

        self['entryOverlap'].set_text(str(m['overlap']))
    
        self['radiobuttonWindowNone'].set_active(
            m['window']==window_none)
            
        if m['detrend']==detrend_none:
            self['radiobuttonDetrendNone'].set_active(1)
            
        elif m['detrend']==detrend_mean:
            self['radiobuttonDetrendMean'].set_active(1)                     
        else:
            self['radiobuttonDetrendLinear'].set_active(1)

        
        self['comboNFFT'].entry.set_text(str(m['NFFT']))




class Dialog_Preferences(PrefixWrapper):
    """
    CLASS: Dialog_Preferences
    DESCR: 
    """
    prefix = 'dlgPref_'
    widgetName = 'dialogPreferences'
    def __init__(self, mysqlCallBack, dataManagerCallBack):
        PrefixWrapper.__init__(self)
        self._mysqlCallBack = mysqlCallBack
        self._dataManagerCallBack = dataManagerCallBack

    def on_buttonCacheDirBrowse_clicked(self, event):
        def browse_ok(dirDialog):
            dirName = dirDialog.get_filename()
            self['entryCacheDir'].set_text(dirName)
            fmanager.set_lastdir(dirName)
            dirDialog.destroy()        
            
        d = Dialog_DirSelection(
            self['entryCacheDir'].get_text(),
            okCallback=browse_ok,
            title='Select cache directory')


    def on_buttonOK_clicked(self, event):
        if self['radiobuttonUseWebOn'].get_active():
            self._mysql_connect()
            self._zope_connect()
        self.hide_widget()

    def get_params(self):
        m = {}
        m['zopeServer'] = self['entryZopeServer'].get_text().strip()
        m['zopeUser'] = self['entryZopeUser'].get_text().strip()
        m['zopePasswd'] = self['entryZopePass'].get_text().strip()
        m['zopeCacheDir'] = self['entryCacheDir'].get_text().strip()

        m['mysqlDatabase'] = self['entryMysqlDatabase'].get_text().strip()
        m['mysqlServer'] = self['entryMysqlServer'].get_text().strip()
        m['mysqlUser'] = self['entryMysqlUser'].get_text().strip()
        m['mysqlPasswd'] = self['entryMysqlPasswd'].get_text().strip()
        m['mysqlPort'] = int(self['entryMysqlPort'].get_text())
        return m


    def set_params(self, m):

        self['entryZopeServer'].set_text(m['zopeServer'])
        self['entryZopeUser'].set_text(m['zopeUser'])
        self['entryZopePass'].set_text(m['zopePasswd'])
        self['entryCacheDir'].set_text(m['zopeCacheDir'])

        self['entryMysqlDatabase'].set_text(m['mysqlDatabase'])
        self['entryMysqlServer'].set_text(m['mysqlServer'])
        self['entryMysqlUser'].set_text(m['mysqlUser'])
        self['entryMysqlPasswd'].set_text(m['mysqlPasswd'])
        self['entryMysqlPort'].set_text(str(m['mysqlPort']))


    def _zope_connect(self):
        m = self.get_params()
        user=m['zopeUser']
        passwd=m['zopePasswd']
        cachedir=m['zopeCacheDir']
        url = m['zopeServer']
        self._dataManagerCallBack(url, user, passwd, cachedir)
        return 1

    def _mysql_connect(self):

        m = self.get_params()
        if self['radiobuttonUseWebOn'].get_active():
            dbname = m['mysqlDatabase']
            host   = m['mysqlServer']
            user   = m['mysqlUser']
            passwd = m['mysqlPasswd']
            port   = m['mysqlPort']
            self._mysqlCallBack(dbname, host, user, passwd, port)

        return 1

class Dialog_SaveEOI(PrefixWrapper):
    """
    CLASS: Dialog_SaveEOI
    DESCR:
    """
    prefix = 'dlgSaveEOI_'
    widgetName = 'dialogSaveEOI'

    def __init__(self, eoiActive, eoisAll, ok_callback):
        PrefixWrapper.__init__(self)
        self.okCallback = ok_callback

        if storeParamsOnOK.has_key(self.widgetName):
            self.set_params(storeParamsOnOK[self.widgetName])
        else:
            #todo: fix file vs fullname for eoi
            names = [eoi.filename for eoi in eoisAll]
            self['comboExisting'].set_popdown_strings(names)
        self['comboExisting'].entry.set_text(eoiActive.filename)

    def on_buttonOK_clicked(self, event):
        storeParamsOnOK[self.widgetName] = self.get_params()
        self.okCallback(self.get_params())        

    def set_params(self, m):
        self['comboExisting'].entry.set_text(m['filename'])

    def get_params(self):
        return {'filename': self['comboExisting'].entry.get_text()}

class Dialog_Annotate(PrefixWrapper) :
    """
    CLASS: Dialog_Annotate
    DESCR:
    """
    prefix = 'dlgAnnotate_'
    widgetName = 'dialogAnnotate'

    def __init__(self, eegplot, annman, params={}, ok_callback=donothing_callback) :
        PrefixWrapper.__init__(self)

        self.eegplot = eegplot
        self.annman = annman
        self.ok_callback = ok_callback

        self.new = params.get('eoi') is None
        self.changed = False
        self.eoi = None

        def select_eoi(*args) :
            def ok_callback(eoi) :
                msg = None
                if eoi.description == '' :
                    msg = 'Please give a short description.'
                elif len(eoi) == 0 :
                    msg = 'Please select an EOI.'
                elif self.new and self.annman.eois.get(eoi.description) :
                    msg = 'An EOI with that description already exists; please choose another description.'
                if msg is not None :
                    mdlg = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                            buttons=gtk.BUTTONS_OK,
                                            message_format=msg)
                    mdlg.set_title('Warning')
                    mdlg.run()
                    mdlg.destroy()
                    return

                model = self['comboBoxEntryEOI'].get_model()
                if self.eoi :
                    model[-1] = [eoi.description]
                else :
                    model.append([eoi.description])
                # Set active to -1 first so the next set_active will
                # work even if the current active entry is selected.
                self['comboBoxEntryEOI'].set_active(-1)
                self['comboBoxEntryEOI'].set_active(len(model) - 1)

                self.eoi = eoi
                self.changed = True

                dlg.destroy_dialog()
                return

            eoiAll = self.eegplot.get_eeg().get_amp().to_eoi()
            eoiActive = None
            if not self.new :
                params = self.get_params()
                eoiActive = params.get('eoi')
            dlg = Dialog_SelectElectrodes(trodes=eoiAll,
                                          ok_callback=ok_callback,
                                          selected=eoiActive)
            dlg.set_transient_for(self.widget)

        # Make EOI combo box entry uneditable
        self['comboBoxEntryEOI'].child.set_editable(0)

        # Set EOI combo options
        if self['comboBoxEntryEOI'].get_model() is None :
            model = gtk.ListStore(str)
            for eoi in self.annman.eois.keys() :
                model.append([eoi])
            self['comboBoxEntryEOI'].set_model(model)
            self['comboBoxEntryEOI'].set_text_column(0)
            self['comboBoxEntryEOI'].set_active(0)

        self['buttonEOINewEdit'].connect('clicked', select_eoi)

        # Set code combo options
        if self['comboBoxEntryCode'].get_model() is None :
            model = gtk.ListStore(str)
            for code in CodeRegistry.get_code_from_registry('Annotation code').descs :
                model.append([code])
            self['comboBoxEntryCode'].set_model(model)
            self['comboBoxEntryCode'].set_text_column(0)
            self['comboBoxEntryCode'].set_active(0)

        # Set behavioral state combo options
        if self['comboBoxEntryState'].get_model() is None :
            model = gtk.ListStore(str)
            for state in CodeRegistry.get_code_from_registry('Behavioral State').descs :
                model.append([state])
            self['comboBoxEntryState'].set_model(model)
            self['comboBoxEntryState'].set_text_column(0)
            self['comboBoxEntryState'].set_active(0)

        # Doesn't seem to update; do it in eegview.py instead (before show)
        #self['hscaleAlpha'].set_value(.5)

        self.set_params(params)

    def set_params(self, params) :
        self.changed = False

        self['entryStartTime'].set_text('%1.1f' % params.get('startTime', 0.0))
        self['entryEndTime'].set_text('%1.1f' % params.get('endTime', 1.0))
        self['labelCreated'].set_text(params.get('created', ''))
        self['labelEdited'].set_text(params.get('edited', ''))
        self['entryUsername'].set_text(params.get('username', 'unknown'))

        # Set active eoi combo box entry
        if params.get('eoi') :
            model = self['comboBoxEntryEOI'].get_model()
            n = 0
            for rw in model :
                if rw[0] == params['eoi'].get_description() :
                    self['comboBoxEntryEOI'].set_active(n)
                    break
                n += 1
            self['buttonEOINewEdit'].set_label('Edit All')
            self.new = False
        else :
            self['comboBoxEntryEOI'].set_active(0)
            self['buttonEOINewEdit'].set_label('New')
            self.new = True

        # Set active code combo box entry
        if params.get('code') :
            model = self['comboBoxEntryCode'].get_model()
            n = 0
            for rw in model :
                if rw[0] == params.get('code', '') :
                    self['comboBoxEntryCode'].set_active(n)
                    break
                n += 1
        else :
            self['comboBoxEntryCode'].set_active(0)

        # Set active behavioral state combo box entry
        if params.get('state') :
            model = self['comboBoxEntryState'].get_model()
            n = 0
            for rw in model :
                if rw[0] == params.get('state', '') :
                    self['comboBoxEntryState'].set_active(n)
                    break
                n += 1
        else :
            self['comboBoxEntryState'].set_active(0)

        self['colorButton'].set_color(gtk.gdk.color_parse(params.get('color', '#ddddff')))
        self['hscaleAlpha'].set_value(params.get('alpha', 0.5))
        self['textViewAnnotation'].get_buffer().set_text(params.get('annotation', ''))
        self['checkButtonShrink'].set_active(params.get('shrink', 1))

    def get_params(self) :
        params = dict(startTime = float(self['entryStartTime'].get_text()),
                      endTime   = float(self['entryEndTime'].get_text()),
                      created   = self['labelCreated'].get_text(),
                      edited    = self['labelEdited'].get_text(),
                      username  = self['entryUsername'].get_text())

        # Get eoi description to look up in annman's eoi list.
        try : self.eegplot
        except :
            params['eoi'] = None
        else :
            description = ''
            c = self['comboBoxEntryEOI']
            model = c.get_model()
            active = c.get_active()
            if active >= 0 :
                description = model[active][0]
                if self.eegplot.annman.eois.get(description) :
                    params['eoi'] = self.eegplot.annman.eois[description]
                else :
                    params['eoi'] = self.eoi

        c = self['comboBoxEntryCode']
        model = c.get_model()
        active = c.get_active()
        if active >= 0 :
            params['code'] = model[active][0]
        else :
            params['code'] = ''

        c = self['comboBoxEntryState']
        model = c.get_model()
        active = c.get_active()
        if active >= 0 :
            params['state'] = model[active][0]
        else :
            params['state'] = ''

        color = self['colorButton'].get_color()
        params['color'] = '#%.2X%.2X%.2X' % (color.red / 256,
                                             color.green / 256,
                                             color.blue / 256)
        params['alpha'] = float(self['hscaleAlpha'].get_value())

        params['shrink'] = self['checkButtonShrink'].get_active()
        start, end = self['textViewAnnotation'].get_buffer().get_bounds()
        params['annotation'] = self['textViewAnnotation'].get_buffer().get_text(start, end)

        return params

    def on_buttonOK_clicked(self, event) :
        params = self.get_params()
        self.ok_callback(params)

    def on_buttonCancel_clicked(self, event) :
        # Remove the new eoi if any from the combo box.
        if self.eoi :
            model = self['comboBoxEntryEOI'].get_model()
            del model[-1]

        self.set_params(self.initParams)
        self.hide_widget()


class Dialog_AnnBrowser(PrefixWrapper) :
    """
    CLASS: Dialog_AnnBrowser
    DESCR:
    """
    prefix = 'dlgAnnBrowser_'
    widgetName = 'dialogAnnBrowser'

    def __init__(self, eegplot, annman, ok_callback=donothing_callback) :
        PrefixWrapper.__init__(self)
        self.ok_callback = ok_callback

        self.eegplot = eegplot
        self.annman = annman

        self.update_combo_entry_boxes()

        # Update annotation info if an annotation is currently selected.
        self.update_ann_info(self.annman.selectedkey)

    def show(self) :
        self.update_combo_entry_boxes()
        self.show_widget()

    def update_combo_entry_boxes(self) :
        # Set combo box EOI options
        model = gtk.ListStore(str)
        model.append(['Any'])
        for key in self.annman.eois.keys() :
            model.append([key])
        if self['comboBoxEntryEOIDescription'].get_model() is None :
            self['comboBoxEntryEOIDescription'].set_model(model)
            self['comboBoxEntryEOIDescription'].set_text_column(0)
            self['comboBoxEntryEOIDescription'].set_active(0)
        else :
            self['comboBoxEntryEOIDescription'].set_model(model)
        

        # Set combo box username options
        usernames = ['Any']
        ann = self.eegplot.eeg.get_ann()
        for a in ann.values() :
            if a['username'] not in usernames :
              usernames.append(a['username'])
        model = gtk.ListStore(str)
        for username in usernames :
            model.append([username])
        if self['comboBoxEntryUsername'].get_model() is None :
            self['comboBoxEntryUsername'].set_model(model)
            self['comboBoxEntryUsername'].set_text_column(0)
            self['comboBoxEntryUsername'].set_active(0)
        else :
            self['comboBoxEntryUsername'].set_model(model)

        # Set combo box code options
        if self['comboBoxEntryCode'].get_model() is None :
            codes = ['Any'] + CodeRegistry.get_code_from_registry('Annotation code').descs
            model = gtk.ListStore(str)
            for code in codes :
                model.append([code])
            self['comboBoxEntryCode'].set_model(model)
            self['comboBoxEntryCode'].set_text_column(0)
            self['comboBoxEntryCode'].set_active(0)

        # Set combo box behavioral state options
        if self['comboBoxEntryState'].get_model() is None :
            states = ['Any'] + CodeRegistry.get_code_from_registry('Behavioral State').descs
            model = gtk.ListStore(str)
            for state in states :
                model.append([state])
            self['comboBoxEntryState'].set_model(model)
            self['comboBoxEntryState'].set_text_column(0)
            self['comboBoxEntryState'].set_active(0)

    def get_search(self) :
        username = None
        c = self['comboBoxEntryUsername']
        model = c.get_model()
        active = c.get_active()
        if active >= 0 :
            username = model[active][0]
            if username == 'Any' : username = None
        else :
            username = None

        code = None
        c = self['comboBoxEntryCode']
        model = c.get_model()
        active = c.get_active()
        if active >= 0 :
            code = model[active][0]
            if code == 'Any' : code = None
        else :
            code = None

        return username, code

    def update_ann_info(self, key=None) :
        ann = self.eegplot.eeg.get_ann()

        if key :
            # Make widgets sensitive
            for widget in ['label1', 'label2', 'label3', 'label4', 'label5',
                           'label6', 'label7', 'label8', 'label9', 'label10',
                           'label11', 'label12',
                           'labelStartTime', 'labelEndTime',
                           'labelCreated', 'labelEdited',
                           'labelEOIDescription', 'comboBoxEntryEOI',
                           'labelUsername', 'labelCode', 'labelState',
                           'labelColor', 'labelAlpha',
                           'textViewAnnotation'] :
                self[widget].set_sensitive(True)

            # Update text
            s = '%1.1f' % ann[key]['startTime']
            self['labelStartTime'].set_text(s)
            e = '%1.1f' % ann[key]['endTime']
            self['labelEndTime'].set_text(e)

            self['labelCreated'].set_text(ann[key]['created'])
            self['labelEdited'].set_text(ann[key]['edited'])

            self['labelEOIDescription'].set_text(ann[key]['eoi'].get_description())
            model = gtk.ListStore(str)
            for trode in ann[key]['eoi'] :
                model.append([trode[0] + str(trode[1])])
            if self['comboBoxEntryEOI'].get_model() is None :
                self['comboBoxEntryEOI'].set_model(model)
                self['comboBoxEntryEOI'].set_text_column(0)
            else :
                self['comboBoxEntryEOI'].set_model(model)
            self['comboBoxEntryEOI'].child.set_text('')

            self['labelUsername'].set_text(ann[key]['username'])
            self['labelCode'].set_text(ann[key]['code'])
            self['labelState'].set_text(ann[key]['state'])

            self['labelColor'].set_text(ann[key]['color'])
            self['labelAlpha'].set_text('%1.2f' % ann[key]['alpha'])

            self['textViewAnnotation'].get_buffer().set_text(ann[key]['annotation'])

        else :
            # Make widgets not sensitive
            for widget in ['label1', 'label2', 'label3', 'label4', 'label5',
                           'label6', 'label7', 'label8', 'label9', 'label10',
                           'label11', 'label12',
                           'labelStartTime', 'labelEndTime',
                           'labelCreated', 'labelEdited',
                           'labelEOIDescription', 'comboBoxEntryEOI',
                           'labelUsername', 'labelCode', 'labelState',
                           'labelColor', 'labelAlpha',
                           'textViewAnnotation'] :
                self[widget].set_sensitive(False)

            # Update text
            self['labelStartTime'].set_text('0.0')
            self['labelEndTime'].set_text('0.0')
            self['labelUsername'].set_text('none')
            self['labelColor'].set_text('none')
            self['labelCode'].set_text('none')
            self['textViewAnnotation'].get_buffer().set_text('')

        # Update combo entry boxes in case a username was added or 
        # deleted.
        self.update_combo_entry_boxes()

    def jump_to_annotation(self, key) :
        ann = self.eegplot.eeg.get_ann()
        s = ann[key]['startTime']
        e = ann[key]['endTime']

        tmin, tmax = self.eegplot.get_time_lim()
        width = tmax - tmin
        news, newe = tmin, tmax
	if s < tmin or s > tmax:
            newWidth = e - s
            if newWidth < width :
                space = (width - newWidth) / 2.0
                if s - space < 0 :
                    news = 0
                else :
                    news = s - space
            else :
              news = s - .5
	if e > tmax :
	    if e > news + width :
                newe = e + .5
            else :
                newe = news + width
        elif e < tmin :
            newe = news + width

        self.eegplot.set_time_lim(news, newe, updateData = True)
	self.annman.update_annotations()
        self.annman.set_selected(key)

    def on_buttonShow_clicked(self, event) :
        ann = self.eegplot.eeg.get_ann()
        username, code = self.get_search()
        for key, annInfo in ann.items() :
            ok = 1
            if (username is not None
                and ann[key]['username'] <> username) :
                ok = 0
            if ok and (code is not None
                       and ann[key]['code'] <> code) :
                ok = 0
            if ok :
                ann[key]['visible'] = 1

        self.eegplot.annman.update_annotations()

        return False

    def on_buttonHide_clicked(self, event) :
        ann = self.eegplot.eeg.get_ann()
        username, code = self.get_search()
        for key, annInfo in ann.items() :
            ok = 1
            if (username is not None
                and ann[key]['username'] <> username) :
                ok = 0
            if ok and (code is not None
                       and ann[key]['code'] <> code) :
                ok = 0
            if ok :
                ann[key]['visible'] = 0

        self.eegplot.annman.update_annotations()

        return False

    def on_buttonFirst_clicked(self, event) :
        # Get first annotation
        username, code = self.get_search()
        ann = self.eegplot.eeg.get_ann()
        newkey = None
        keys = ann.keys()
        keys.sort()
        if username is None and code is None :
            newkey = keys[0]
        else :
            for key in keys :
                if not ann[key]['visible'] : continue
                ok = 1
                if (username is not None
                    and ann[key]['username'] <> username) :
                    ok = 0
                if ok and (code is not None
                           and ann[key]['code'] <> code) :
                    ok = 0
                if ok :
                    newkey = key
                    break

        # Jump to annotation
        if newkey is not None :
	    self.update_ann_info(newkey)
            self.jump_to_annotation(newkey)

    def on_buttonPrev_clicked(self, event) :
        if self.annman.selectedkey :
            username, code = self.get_search()
            ann = self.eegplot.eeg.get_ann()
            newkey = None
            keys = ann.keys()
            keys.sort()
            ind = keys.index(self.annman.selectedkey)
            if ind > 0 :
                ind -= 1
                while ind >= 0 :
                    if ann[keys[ind]]['visible'] :
                        ok = 1
                        if (username is not None
                            and ann[keys[ind]]['username'] <> username) :
                            ok = 0
                        if ok and (code is not None
                                   and ann[keys[ind]]['code'] <> code) :
                            ok = 0
                        if ok :
                            newkey = keys[ind]
                            break
                    ind -= 1

            if newkey is not None :
                self.update_ann_info(newkey)
                self.jump_to_annotation(newkey)

    def on_buttonNext_clicked(self, event) :
        if self.annman.selectedkey :
            username, code = self.get_search()
            ann = self.eegplot.eeg.get_ann()
            newkey = None
            keys = ann.keys()
            keys.sort()
            ind = keys.index(self.annman.selectedkey)
            if ind < len(keys) - 1 :
                ind += 1
                while ind < len(keys) :
                    if ann[keys[ind]]['visible'] :
                        ok = 1
                        if (username is not None
                            and ann[keys[ind]]['username'] <> username) :
                            ok = 0
                        if ok and (code is not None
                                   and ann[keys[ind]]['code'] <> code) :
                            ok = 0
                        if ok :
                            newkey = keys[ind]
                            break
                    ind += 1

            if newkey is not None :
                self.update_ann_info(newkey)
                self.jump_to_annotation(newkey)

    def on_buttonLast_clicked(self, event) :
        # Get last annotation of given code
        username, code = self.get_search()
        ann = self.eegplot.eeg.get_ann()
        newkey = None
        keys = ann.keys()
        keys.sort()
        keys.reverse()
        if username is None and code is None :
            newkey = keys[0]
        else :
            for key in keys :
                if not ann[key]['visible'] : continue
                ok = 1
                if (username is not None
                    and ann[key]['userrname'] <> username) :
                    ok = 0
                if ok and (code is not None
                           and ann[key]['code'] <> code) :
                    ok = 0
                if ok :
                    newkey = key
                    break

        # Jump to annotation
        if newkey is not None :
            self.update_ann_info(newkey)
            self.jump_to_annotation(newkey)

    def on_buttonClose_clicked(self, event) :
        self.ok_callback()


class Dialog_PhaseSynchrony(PrefixWrapper) :
    """
    CLASS: Dialog_PhaseSynchrony
    DESCR:
    """
    prefix = 'dlgPhaseSynchrony_'
    widgetName = 'dialogPhaseSynchrony'

    def __init__(self, eegplot, params={}, ok_callback=donothing_callback) :
        print "Dialog_PhaseSynchrony.__init__()"
        PrefixWrapper.__init__(self)

        self.eegplot = eegplot

        # Initialize EOI TreeView
        self.eois = {}
        if self['treeViewEOIs'].get_model() is None :
            cell = gtk.CellRendererText()
            col = gtk.TreeViewColumn("title", cell, text=0)
            self['treeViewEOIs'].append_column(col)

            # List available EOIs
            # XXX Add EOIs from annman, files, both, none?        

            model = gtk.ListStore(str)
            self['treeViewEOIs'].set_model(model)
        self['treeViewEOIs'].get_selection().set_mode(gtk.SELECTION_MULTIPLE)

        # Initialize Filters TreeView
        self.filters = {}
        if self['treeViewFilters'].get_model() is None :
            colNames = ['Name', 'Window Length', 'LPSF', 'LPCF', 'HPCF', 'HPSF', 'Frequency']
            for i, name in enumerate(colNames) :
                cell = gtk.CellRendererText()
                col = gtk.TreeViewColumn(name, cell, text=i)
                self['treeViewFilters'].append_column(col)

            # List available Filters
            # XXX Add filters
            if params.get('filters') is None :
                freq = eegplot.eeg.freq
                self.filters = {
                  'delta' : (2.0, ( 0.0,  2.0,  5.0,  8.0, freq)),
                  'theta' : (0.6, ( 2.0,  4.0,  8.0, 10.0, freq)),
                  'alpha' : (0.3, ( 5.0,  8.0, 12.0, 15.0, freq)),
                  'beta'  : (0.2, ( 9.0, 11.0, 30.0, 50.0, freq)),
                  'gamma' : (0.1, (25.0, 30.0, 50.0, 55.0, freq))}
            else :
                self.filters = params['filters'].copy()

            model = gtk.ListStore(str, str, str, str, str, str, str)
            for name, props in self.filters.items() :
                model.append([name, props[0], props[1][0],
                              props[1][1], props[1][2], props[1][3],
                              props[1][4]])
            self['treeViewFilters'].set_model(model)
        self['treeViewFilters'].get_selection().set_mode(gtk.SELECTION_MULTIPLE)

        # Set callbacks
        self['buttonEOIEdit'].connect('clicked', self.edit_eoi)
        self['buttonEOINew'].connect('clicked', self.new_eoi)
        self['buttonEOIDelete'].connect('clicked', self.delete_eois)
        self['buttonFilterEdit'].connect('clicked', self.edit_filter)
        self['buttonFilterNew'].connect('clicked', self.new_filter)
        self['buttonFilterDelete'].connect('clicked', self.delete_filters)
        self['radioButtonSurrDataNew'].connect('toggled', self.toggle_surr_data, 'new')
        self['radioButtonSurrDataLoad'].connect('toggled', self.toggle_surr_data, 'load')
        self['buttonSurrDataFileBrowse'].connect('clicked', self.browse_surr_data_file)
        self['buttonOutputFileBrowse'].connect('clicked', self.browse_output_file)
        self['buttonDisplayData'].connect('clicked', self.display_data)

        # Set default time range to be time limits in eeg window
        tmin, tmax = eegplot.get_time_lim()
        self['entrytMin'].set_text(str(tmin))
        self['entrytMax'].set_text(str(tmax))

        # List available filters

        # Set default surrogate file

    def edit_eoi(self, *args) :
        def ok_callback(eoi) :
            msg = None
            if eoi.description == '' :
                msg = 'Please give a short description.'
            elif len(eoi) == 0 :
                msg = 'Please select an EOI.'
            elif eoi.description != origDesc and self.eois.get(eoi.description) :
                msg = 'An EOI with that description already exists; please choose another description.'
            if msg is not None :
                mdlg = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                        buttons=gtk.BUTTONS_OK,
                                        message_format=msg)
                mdlg.set_title('Warning')
                mdlg.run()
                mdlg.destroy()
                return

            # Update EOI name if changed
            if origDesc != eoi.description :
                model.set_value(model.get_iter(pathlist[0]), 0, eoi.description)
                self.eois[eoi.description] = eoi
                del self.eois[origDesc]

            # Save new EOI in .eegviewrc

            dlgEOI.destroy_dialog()

            return

        # Get selected item
        sel = self['treeViewEOIs'].get_selection()
        msg = None
        if sel.count_selected_rows() == 0 :
            msg = 'Please select an EOI to edit.'
        elif sel.count_selected_rows() > 1 :
            msg = 'Please select one EOI to edit.'
        if msg is not None :
            mdlg = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                     buttons=gtk.BUTTONS_OK,
                                     message_format=msg)
            mdlg.set_title('Warning')
            mdlg.run()
            mdlg.destroy()
            return

        # Get current EOI
        (model, pathlist) = sel.get_selected_rows()
        origDesc = model.get_value(model.get_iter(pathlist[0]), 0)
        eoi = self.eois[origDesc]

        eoiAll = self.eegplot.get_eeg().get_amp().to_eoi()
        dlgEOI = Dialog_SelectElectrodes(trodes=eoiAll,
                                         selected=eoi,
                                         ok_callback=ok_callback)
        dlgEOI.set_transient_for(self.widget)

    def new_eoi(self, *args) :
        def ok_callback(eoi) :
            msg = None
            if eoi.description == '' :
                msg = 'Please give a short description.'
            elif len(eoi) == 0 :
                msg = 'Please select an EOI.'
            elif self.eois.get(eoi.description) :
                msg = 'An EOI with that description already exists; please choose another description.'
            if msg is not None :
                mdlg = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                         buttons=gtk.BUTTONS_OK,
                                         message_format=msg)
                mdlg.set_title('Warning')
                mdlg.run()
                mdlg.destroy()
                return

            # Append new EOI to TreeView model
            model = self['treeViewEOIs'].get_model()
            model.append([eoi.description])

            # Select the new EOI in TreeView
            sel = self['treeViewEOIs'].get_selection()
            sel.select_path(len(model) - 1)

            # Add new EOI to self
            self.eois[eoi.description] = eoi

            # Save new EOI in .eegviewrc

            dlgEOI.destroy_dialog()

            return

        eoiAll = self.eegplot.get_eeg().get_amp().to_eoi()
        dlgEOI = Dialog_SelectElectrodes(trodes=eoiAll,
                                         ok_callback=ok_callback)
        dlgEOI.set_transient_for(self.widget)

    def delete_eois(self, *args) :
        # Get selected item
        sel = self['treeViewEOIs'].get_selection()
        msg = None
        if sel.count_selected_rows() == 0 :
            msg = 'Please select EOIs to delete.'
            mdlg = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                     buttons=gtk.BUTTONS_OK,
                                     message_format=msg)
            mdlg.set_title('Warning')
            mdlg.run()
            mdlg.destroy()
            return

        # Confirm
        msg = 'Are you sure you wish to delete these EOIs?'
        mdlg = gtk.MessageDialog(type=gtk.MESSAGE_QUESTION,
                                 buttons=gtk.BUTTONS_YES_NO,
                                 message_format=msg)
        mdlg.set_title('Delete EOIs')
        response = mdlg.run()
        mdlg.destroy()
        if response == gtk.RESPONSE_YES :
            (model, pathlist) = sel.get_selected_rows()
            pathlist.reverse()
            for path in pathlist :
                iter = model.get_iter(path)
                desc = model.get_value(iter, 0)
                model.remove(model.get_iter(path))
                del self.eois[desc]

    def edit_filter(self, *args) :
        def ok_callback(props) :
            msg = None
            if props[0] != origFilterName and self.filters.get(props[0]) :
                msg = 'A filter with that name already exists; please choose another name.'
            if msg is not None :
                mdlg = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                        buttons=gtk.BUTTONS_OK,
                                        message_format=msg)
                mdlg.set_title('Warning')
                mdlg.run()
                mdlg.destroy()
                return

            # Update filter name if changed
            if origFilterName != props[0] :
                del self.filters[origFilterName]

            # Update filter properties
            self.filters[props[0]] = [props[1], props[2]]
            model.set_value(model.get_iter(pathlist[0]), 0, props[0])
            model.set_value(model.get_iter(pathlist[0]), 1, props[1])
            model.set_value(model.get_iter(pathlist[0]), 2, props[2][0])
            model.set_value(model.get_iter(pathlist[0]), 3, props[2][1])
            model.set_value(model.get_iter(pathlist[0]), 4, props[2][2])
            model.set_value(model.get_iter(pathlist[0]), 5, props[2][3])
            model.set_value(model.get_iter(pathlist[0]), 6, props[2][4])

            # Save new EOI in .eegviewrc

            dlgFilterProps.hide_widget()

            return

        # Get selected item
        sel = self['treeViewFilters'].get_selection()
        msg = None
        if sel.count_selected_rows() == 0 :
            msg = 'Please select an filter to edit.'
        elif sel.count_selected_rows() > 1 :
            msg = 'Please select one filter to edit.'
        if msg is not None :
            mdlg = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                     buttons=gtk.BUTTONS_OK,
                                     message_format=msg)
            mdlg.set_title('Warning')
            mdlg.run()
            mdlg.destroy()
            return

        # Get current filter
        (model, pathlist) = sel.get_selected_rows()
        origFilterName = model.get_value(model.get_iter(pathlist[0]), 0)
        props = self.filters[origFilterName]

        # Pop up filter properties dialog box
        dlgFilterProps = Dialog_FilterProps(
                           props=[origFilterName, props[0], props[1]],
                           ok_callback=ok_callback)
        dlgFilterProps.widget.set_transient_for(self.widget)
        dlgFilterProps.show_widget()

    def new_filter(self, *args) :
        def ok_callback(props) :
            msg = None
            if props[0] is '' :
                msg = 'Please provide a name.'
            elif self.filters.get(props[0]) :
                msg = 'A filter with that name already exists; please choose another name.'
            if msg is not None :
                mdlg = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                         buttons=gtk.BUTTONS_OK,
                                         message_format=msg)
                mdlg.set_title('Warning')
                mdlg.run()
                mdlg.destroy()
                return

            # Append new filter to TreeView model
            model = self['treeViewFilters'].get_model()
            model.append([props[0], props[1], props[2][0], props[2][1], 
                          props[2][2], props[2][3], props[2][4]])

            # Select the new filter in TreeView
            sel = self['treeViewFilters'].get_selection()
            sel.select_path(len(model) - 1)

            # Add new filter to self
            self.filters[props[0]] = [props[1], props[2]]

            # Save new Filter in .eegviewrc

            dlgFilterProps.hide_widget()

            return

        dlgFilterProps = Dialog_FilterProps(ok_callback=ok_callback)
        dlgFilterProps.widget.set_transient_for(self.widget)
        dlgFilterProps.show_widget()

    def delete_filters(self, *args) :
        # Get selected item
        sel = self['treeViewFilters'].get_selection()
        msg = None
        if sel.count_selected_rows() == 0 :
            msg = 'Please select filters to delete.'
            mdlg = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                     buttons=gtk.BUTTONS_OK,
                                     message_format=msg)
            mdlg.set_title('Warning')
            mdlg.run()
            mdlg.destroy()
            return

        # Confirm
        msg = 'Are you sure you wish to delete these filters?'
        mdlg = gtk.MessageDialog(type=gtk.MESSAGE_QUESTION,
                                 buttons=gtk.BUTTONS_YES_NO,
                                 message_format=msg)
        mdlg.set_title('Delete Filters')
        response = mdlg.run()
        mdlg.destroy()
        if response == gtk.RESPONSE_YES :
            (model, pathlist) = sel.get_selected_rows()
            pathlist.reverse()
            for path in pathlist :
                iter = model.get_iter(path)
                name = model.get_value(iter, 0)
                model.remove(model.get_iter(path))
                del self.filters[name]

    def new_surr_data(self, *args) :
        def ok_callback(surrogateProps) :
            msg = None
            if msg is not None :
                mdlg = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                         buttons=gtk.BUTTONS_OK,
                                         message_format=msg)
                mdlg.set_title('Warning')
                mdlg.run()
                mdlg.destroy()
                return

            # Create an EOI of only subdural trodes (i.e., no scalp trodes)
            subdurals = set(['FG', 'PG', 'IF', 'AT', 'ST'])
            trodes = [(name, num) for name, num in self.eegplot.eeg.get_amp().to_eoi() if name in subdurals]
            ecog = EOI(electrodes=trodes)
            ecog.sort()

            # Check if output file exists
            outputFile = surrogateProps['outputFile']
            if os.path.exists(outputFile) :
                msg = 'Output file already exists.  Overwrite?'
                mdlg = gtk.MessageDialog(type=gtk.MESSAGE_QUESTION,
                                         buttons=gtk.BUTTONS_YES_NO,
                                         message_format=msg)
                mdlg.set_title('Overwrite File?')
                response = mdlg.run()
                mdlg.destroy()
                if response == gtk.RESPONSE_NO :
                    return

            # Generate surrogate data
            # Create filters
            filters = {}
            for name, props in surrogateProps['filters'].items() :
                filters[name] = (props[0],
                                 bandpass(props[1][0], props[1][1],
                                          props[1][2], props[1][3],
                                          props[1][4]))
            tmin = surrogateProps['tMin']
            tmax = surrogateProps['tMax']
            surrData = gen_surrogate_data(self.eegplot.eeg, 
                         tmin, tmax,
                         ecog, filters, 
                         surrogateProps['numPairs'])
            pickle.dump((tmin, tmax, trodes, surrogateProps['filters'], surrData),
                        open(outputFile, 'w'))

            self['entrySurrDataFile'].set_text(surrogateProps['outputFile'])

            dlgSurrogateData.hide_widget()

            return

        surrogateProps = {'filters'  : self.filters,
                          'tMin'     : self['entrytMin'].get_text(),
                          'tMax'     : self['entrytMax'].get_text(),
                          'numPairs' : 20,
                          'outputFile' : 'surrdata_name_' + self['entrytMin'].get_text() + '-' + self['entrytMax'].get_text() + '_20.pickle'}
        dlgSurrogateData = Dialog_SurrogateData(surrogateProps, ok_callback)
        dlgSurrogateData.widget.set_transient_for(self.widget)
        dlgSurrogateData.show_widget()

    def toggle_surr_data(self, radioButton, mode) :
        if radioButton.get_active() :
            if mode == 'new' :
                self['labelSurrDataFile'].set_label('<b>Output Pickle File:</b> ')
                self['labelSurrDataNumPairs'].set_sensitive(True)
                self['entrySurrDataNumPairs'].set_sensitive(True)
            elif mode == 'load' :
                self['labelSurrDataFile'].set_label('<b>Input Pickle File:</b> ')
                self['labelSurrDataNumPairs'].set_sensitive(False)
                self['entrySurrDataNumPairs'].set_sensitive(False)

    def browse_surr_data_file(self, *args) :
        def ok_callback(dirDialog):
            filename = dirDialog.get_filename()
            self['entrySurrDataFile'].set_text(filename)
            dirDialog.destroy()

        d = Dialog_FileSelection(
            defaultDir=fmanager.get_lastdir(),
            okCallback=ok_callback,
            title='Select surrogate data file',
            parent=self.widget)

    def browse_output_file(self, *args) :
        def ok_callback(dirDialog):
            filename = dirDialog.get_filename()
            self['entryOutputFile'].set_text(filename)
            dirDialog.destroy()

        d = Dialog_FileSelection(
            defaultDir=fmanager.get_lastdir(),
            okCallback=ok_callback,
            title='Select phase synchrony output file',
            parent=self.widget)

    def display_data(self, *args, **kwargs) :
        outputFile = self['entryOutputFile'].get_text()
        msg = None
        try : sync = pickle.load(file(outputFile, 'r'))
        except IOError, inst :
            msg = 'Error loading surrogate data file: %s' % inst[1]
        except :
            msg = 'Error loading surrogate data file: %s' % sys.exc_info()[1].args[0]

        # Report error message
        if msg is not None :
            mdlg = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                     buttons=gtk.BUTTONS_OK,
                                     message_format=msg)
            mdlg.set_title('Warning')
            mdlg.run()
            mdlg.destroy()
            return

        dlgPhaseSynchronyPlot = Dialog_PhaseSynchronyPlot(self.eegplot, sync=sync)
        dlgPhaseSynchronyPlot.show_widget()

    def on_buttonOK_clicked(self, event):
        msg = None

        # Check valid time range
        try : tmin = float(self['entrytMin'].get_text())
        except ValueError, inst : msg = 'Please enter a valid minimum time.'
        if msg is None :
            try : tmax = float(self['entrytMax'].get_text())
            except ValueError, inst : msg = 'Please enter a valid maximum time.'

        # Check surrogate data entry values
        if msg is None :
            surrDataFile = self['entrySurrDataFile'].get_text()

            if self['radioButtonSurrDataNew'].get_active() :
                if surrDataFile == '' :
                    msg = 'Please select an output surrogate data file.'

                if msg is None :
                    try : numPairs = int(self['entrySurrDataNumPairs'].get_text())
                    except ValueError, inst : msg = 'Please enter a valid number of surrogate data pairs.'

            elif self['radioButtonSurrDataLoad'].get_active() :
                if surrDataFile == '' :
                    msg = 'Please select an input surrogate data file.'

        # Check output file value
        outputFile = self['entryOutputFile'].get_text()
        if msg is None and outputFile == '' :
            msg = 'Please select an output data file.'

        # Report error message
        if msg is not None :
            mdlg = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                     buttons=gtk.BUTTONS_OK,
                                     message_format=msg)
            mdlg.set_title('Warning')
            mdlg.run()
            mdlg.destroy()
            return

        # Check for existing files.
        # Check if output surrogate data file already exists
        if self['radioButtonSurrDataNew'].get_active() \
           and os.path.exists(surrDataFile) :
            msg = 'Surrogate data output file already exists.  Overwrite?'
            mdlg = gtk.MessageDialog(type=gtk.MESSAGE_QUESTION,
                                     buttons=gtk.BUTTONS_YES_NO,
                                     message_format=msg)
            mdlg.set_title('Overwrite File?')
            response = mdlg.run()
            mdlg.destroy()
            if response == gtk.RESPONSE_NO :
                return

        # Check if output file already exists
        if os.path.exists(outputFile) :
            msg = 'Output file already exists.  Overwrite?'
            mdlg = gtk.MessageDialog(type=gtk.MESSAGE_QUESTION,
                                     buttons=gtk.BUTTONS_YES_NO,
                                     message_format=msg)
            mdlg.set_title('Overwrite File?')
            response = mdlg.run()
            mdlg.destroy()
            if response == gtk.RESPONSE_NO :
                return

        dlgStatusBox = Dialog_StatusBox(title='Phase Synchrony Status')
        dlgStatusBox.widget.show_now()
        dlgStatusBox.autoconnect()
        # dlgStatusBox.show_widget()

        # Create filters
        filters = {}
        for name, props in self.filters.items() :
            filters[name] = (props[0],
                             bandpass(props[1][0], props[1][1],
                                      props[1][2], props[1][3],
                                      props[1][4]))

        # Create an EOI of only subdural trodes (i.e., no scalp trodes)
        # XXX Surrogates are generated from a random set of trodes 
        # selected from the entire set of subdural trodes.  Is this 
        # appropriate?
        subdurals = set(['FG', 'PG', 'IF', 'AT', 'ST'])
        trodes = [(name, num) for name, num in self.eegplot.eeg.get_amp().to_eoi() if name in subdurals]
        ecog = EOI(electrodes=trodes)
        ecog.sort()

        # Get data
        t, data = self.eegplot.eeg.get_data(tmin, tmax)
        e2i = self.eegplot.eeg.get_amp().get_electrode_to_indices_dict()

        surrResults = {}

        # Create new surrogate data
        if self['radioButtonSurrDataNew'].get_active() :
            dlgStatusBox.append('Generating new surrogate data\n')

            # Extract random pairs from the data
            randInds = (nx.mlab.rand(numPairs, 2) * len(ecog)).astype(nx.Int)
            e2i = self.eegplot.eeg.get_amp().get_electrode_to_indices_dict()
            for i, pair in enumerate(randInds) :
                # Get indices into data
                ie1, ie2 = pair
                i1 = e2i[ecog[ie1]]
                i2 = e2i[ecog[ie2]]

                dlgStatusBox.append('  Computing surrogate %d of %d: %s, %s: ' % (i, numPairs, ecog[ie1], ecog[ie2])) 
                # Generate surrogate data
                surr1 = fftsurr(data[:,i1], window=window_hanning)
                surr2 = fftsurr(data[:,i2], window=window_hanning)

                # Generate filtered surrogate data
                for j, tup in enumerate(filters.items()) :
                    band, info = tup
                    winLen, filter = info

                    dlgStatusBox.append('%s ' % band)

                    fsurr1 = filter(surr1)
                    fsurr2 = filter(surr2)

                    # Compute phase diffs
                    psurr1 = hilbert_phaser(fsurr1)
                    psurr2 = hilbert_phaser(fsurr2)
                    pdiff = psurr1 - psurr2

                    # Compute windowed stddev in each band
                    winLen = self.filters[band][0]
                    freq = self.eegplot.eeg.freq
                    nWin = int(winLen * freq) # num samples in window
                    numWin, rem = divmod(len(pdiff), nWin) # num windows
                    sigma = nx.mlab.std(nx.resize(pdiff[:numWin * nWin], (numWin, nWin)), 1)

                    surrResults[ecog[ie1], ecog[ie2], band] = sigma
                dlgStatusBox.append('\n')

            # Write results
            fh = file(surrDataFile, 'w')
            pickle.dump(surrResults, fh)
            fh.close()

        elif self['radioButtonSurrDataLoad'].get_active() :
            try : surrResults = pickle.load(file(surrDataFile, 'r'))
            except IOError, inst :
                msg = 'Error loading surrogate data file: %s' % inst[1]
            except :
                msg = 'Error loading surrogate data file: %s' % sys.exc_info()[1].args[0]

            # Check surrogate data
            # XXX

            # Report error message
            if msg is not None :
                mdlg = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                         buttons=gtk.BUTTONS_OK,
                                         message_format=msg)
                mdlg.set_title('Warning')
                mdlg.run()
                mdlg.destroy()
                return

            dlgStatusBox.append('Loaded surrogate data\n')

        dlgStatusBox.append('Pooling surrogates over time')

        # Compute synchrony in each band
        surrd = {}
        i0, j0 = None, None
        items = surrResults.items()
        items.sort()
        for key, val in items :
            i, j, band = key
            if i != i0 and j != j0 :
                dlgStatusBox.append('\n  Computing synchrony: %s, %s: %s ' % (i, j, band))
                i0 = i
                j0 = j
            else :
                dlgStatusBox.append('%s ' % band)

            sync = 1. / (1 + sigma)
            surrd.setdefault(band, []).extend(sync)
        dlgStatusBox.append('\n')

        # Compute surrogate percentiles in each band
        ptiled = {}
        dlgStatusBox.append ('  Computing percentiles: ')
        for band in self.filters.keys() :
            ptiled[band] = prctile(surrd[band], (90, 95, 99))
            dlgStatusBox.append('%s ' % band)
        dlgStatusBox.append('\n')

        # Create time vectors - time points at center of each window, step by winLen
        timed = {}
        dlgStatusBox.append('Creating time vectors: ')
        for band, info in filters.items() :
            dlgStatusBox.append('%s ' % band)

            winLen, filter = info
            nWin = int(winLen * self.eegplot.eeg.freq)
            numWin, rem = divmod(data.shape[0], nWin)
            timed[band] = nx.arange(numWin) * winLen + winLen / 2.
        dlgStatusBox.append('\n')

        # Filter each trode in data and get phases
        dlgStatusBox.append('Filtering EEG signals\n')
        phased = {}
        for i, e in enumerate(ecog) :
            dlgStatusBox.append('  Filtering signal %d of %d: %s: ' % (i + 1, len(ecog), str(e)))
            for band, info in filters.items() :
                dlgStatusBox.append('%s ' % band)

                winLen, filter = info
                s = filter(data[:, e2i[e]])
                phased[(e, band)] = hilbert_phaser(s)
            dlgStatusBox.append('\n')

        # Compute synchrony probabilities for all electrode pairs in each band
        dlgStatusBox.append('Computing synchrony between all pairs of electrodes\n')
        syncd = {}
        output = []
        pairs = all_pairs_eoi(ecog)
        for i, pair in enumerate(pairs) :
            e1, e2 = pair
            dlgStatusBox.append('  Computing synchrony probability %d of %d: %s, %s: ' % (i + 1, len(pairs), e1, e2))
            for band, info in filters.items() :
                dlgStatusBox.append('%s ' % band)

                # Compute phase difference
                p1 = phased[(e1, band)]
                p2 = phased[(e2, band)]
                pdiff = p1 - p2

                # Compute windowed stddev
                winLen, filter = info
                nWin = int(winLen * self.eegplot.eeg.freq)
                numWin, rem = divmod(len(pdiff), nWin)
                sigma = nx.mlab.std(nx.resize(pdiff[:numWin*nWin], (numWin, nWin)), 1)

                # Compute synchrony in time range
                t = timed[band]
                ind = nx.nonzero(nx.logical_and(t >= tmin, t<= tmax))
                sync = nx.take(1. / (1 + sigma), ind)
                syncd[e1, e2, band] = sync

                # Get surrogate threshold
                threshold = ptiled[band][0]

                # Compute probability of synchronous event
                frac = len(nx.nonzero(sync > threshold)) / float(len(ind))
                output.append((frac, (e1, e2)))
            dlgStatusBox.append('\n')

        # Order output
        output.sort()
        output.reverse()

        # Determine in which foci events occurred

        # Output synchrony data
        pickle.dump(syncd, open(outputFile, 'w'))

        # Output text to display
        tmpfile = tempfile.mktemp()
        fh = file(tmpfile, 'w')
        print >> fh, 'e1,e2, sync, frac'
        for frac, pair in output :
            e1, e2 = pair
            print >> fh, '%s,%s, %1.3f' % (e1, e2, frac)
        os.system('gedit ' + tmpfile)


class Dialog_PhaseSynchronyPlot(PrefixWrapper) :
    """
    CLASS: Dialog_PhaseSynchronyPlot
    DESCR:
    """
    prefix = 'dlgPhaseSynchronyPlot_'
    widgetName = 'dialogPhaseSynchronyPlot'

    def __init__(self, eegplot, *args, **kwargs) :
        print "Dialog_PhaseSynchronyPlot.__init__()"
        PrefixWrapper.__init__(self)

        self.eegplot = eegplot

        print "uhhh self['vbox'] is ", self['vbox']
        #for some reason self['vbox'] is None if we've already opened and closed the phasesynchrony window once!! -eli
        # Add figure canvas
        vbox = self['vbox']
        self.fig = Figure()
        self.axesSignals = self.fig.add_subplot(311, ylabel="signal")
        self.axesSignals.grid(True)
        self.axesFiltered = self.fig.add_subplot(312, ylabel="filtered")
        self.axesFiltered.grid(True)
        self.axesSync = self.fig.add_subplot(313, ylabel="sync")
        self.axesSync.grid(True)
        self.canvas = FigureCanvas(self.fig)
        print "Dialog_PhaseSynchronyPlot(): self.fig=", self.fig, "self.canvas=", self.canvas
        self.canvas.set_size_request(0, 0)
        self.canvas.show()
        vbox.pack_start(self.canvas, True, True)

        # Add navigation toolbar
        toolbar = NavigationToolbar2GTK(self.canvas, self.widget)
        vbox.pack_start(toolbar, False, False)

        # Create electrode and bands list
        self.sync = None
        self.time = None
        trodes = []
        if kwargs.has_key('sync') and kwargs.has_key('time') :
            self.sync = kwargs['sync']
            self.time = kwargs['time']
            for e1, e2, band in self.sync.keys() :
                if e1 not in trodes :
                    trodes.append(e1)
            trodes.sort()
        else :
            # XXX mcc: this seems like a hack
            #subdurals = set(['FG', 'PG', 'IF', 'AT', 'ST'])
            #trodes = [(name, num) for name, num in self.eegplot.eeg.get_amp().to_eoi() if name in subdurals]
            trodes = [(name, num) for name, num in self.eegplot.eeg.get_amp().to_eoi()]

        self.ptiled = None

        # Get filters
        if kwargs.has_key('filters') :
            self.filters = params['filters'].copy()
        else :
            freq = eegplot.eeg.freq
            self.filters = {
              'delta' : (2.0, ( 0.0,  2.0,  5.0,  8.0, freq)),
              'theta' : (0.6, ( 2.0,  4.0,  8.0, 10.0, freq)),
              'alpha' : (0.3, ( 5.0,  8.0, 12.0, 15.0, freq)),
              'beta'  : (0.2, ( 9.0, 11.0, 30.0, 50.0, freq)),
              'gamma' : (0.1, (25.0, 30.0, 50.0, 55.0, freq))}

        # Initialize Filters TreeView
        if self['treeViewFilters'].get_model() is None :
            colNames = ['Name', 'Window Length', 'LPSF', 'LPCF', 'HPCF', 'HPSF', 'Frequency']
            for i, name in enumerate(colNames) :
                cell = gtk.CellRendererText()
                col = gtk.TreeViewColumn(name, cell, text=i)
                self['treeViewFilters'].append_column(col)

            model = gtk.ListStore(str, str, str, str, str, str, str)
            for name, props in self.filters.items() :
                model.append([name, props[0], props[1][0],
                              props[1][1], props[1][2], props[1][3],
                              props[1][4]])
            self['treeViewFilters'].set_model(model)
        self['treeViewFilters'].get_selection().set_mode(gtk.SELECTION_MULTIPLE)

        # Get start and end times
        tmin, tmax = self.eegplot.get_time_lim()
        if kwargs.has_key('Tmin') and kwargs.has_key('Tmax'):
            tmin = kwargs['Tmin']
            tmax = kwargs['Tmax']

        # Fill signal combo boxes
        if self['comboBoxEntrySignal1'].get_model() is None :
            model = gtk.ListStore(str)
            #print "XXX mcc: trodes are " , trodes
            for trode in trodes :
                #print "XXX mcc: adding trode " , trode
                model.append([trode[0] + str(trode[1])]) 
            self['comboBoxEntrySignal1'].set_model(model)
            self['comboBoxEntrySignal1'].set_text_column(0)
            self['comboBoxEntrySignal1'].set_active(0)
        if self['comboBoxEntrySignal2'].get_model() is None :
            model = gtk.ListStore(str)
            for trode in trodes :
                model.append([trode[0] + str(trode[1])])
            self['comboBoxEntrySignal2'].set_model(model)
            self['comboBoxEntrySignal2'].set_text_column(0)
            self['comboBoxEntrySignal2'].set_active(0)

        # Fill in filter combo box
        if self['comboBoxEntryBand'].get_model() is None :
            model = gtk.ListStore(str)
            self['comboBoxEntryBand'].set_model(model)
            self.update_filter_combo_box()
            self['comboBoxEntryBand'].set_text_column(0)
            self['comboBoxEntryBand'].set_active(0)

        # Fill in tmin and tmax entries
        self['entryTmin'].set_text(str(tmin))
        self['entryTmax'].set_text(str(tmax))
        self['entrySurrDataTmin'].set_text(str(tmin))
        self['entrySurrDataTmax'].set_text(str(tmax))

        # Set file loaded notification label
	self['labelSurrDataNotif'].set_text('')

        # Fill in surrogate data method combo box
#        if self['comboBoxEntrySurrMethod'].get_model() is None :
#            model = gtk.ListStore(str)
#            methods = ('Use random pairs of electrodes',
#                       'Use this pair of electrodes')
#            for method in methods : 
#                model.append([method])
#            self['comboBoxEntrySurrMethod'].set_model(model)
#            self['comboBoxEntrySurrMethod'].set_text_column(0)
#            self['comboBoxEntrySurrMethod'].set_active(0)

        # Initialize EOI TreeView
        self.eois = {}
        if self['treeViewEOIs'].get_model() is None :
            cell = gtk.CellRendererText()
            col = gtk.TreeViewColumn('title', cell, text=0)
            self['treeViewEOIs'].append_column(col)
            model = gtk.ListStore(str)
            self['treeViewEOIs'].set_model(model)
        self['treeViewEOIs'].get_selection().set_mode(gtk.SELECTION_MULTIPLE)

        self['buttonClearSurrData'].set_sensitive(False)

        # Set callbacks
        self['buttonFilterEdit'].connect('clicked', self.edit_filter)
        self['buttonFilterNew'].connect('clicked', self.new_filter)
        self['buttonFilterDelete'].connect('clicked', self.delete_filters)
        self['buttonUpdateSignals'].connect('clicked', self.update_signals)
        self['buttonUpdateTime'].connect('clicked', self.update_time)
        self['buttonSyncFileBrowse'].connect('clicked', self.browse_sync_file)
        self['buttonSyncFileWrite'].connect('clicked', self.write_sync_file)
        self['radioButtonSurrDataNew'].connect('toggled', self.toggle_surr_data, 'new')
        self['radioButtonSurrDataLoad'].connect('toggled', self.toggle_surr_data, 'load')
        self['buttonSurrDataFileBrowse'].connect('clicked', self.browse_surr_data_file)
        self['buttonNewLoadSurrData'].connect('clicked', self.new_load_surr_data)
        self['buttonClearSurrData'].connect('clicked', self.clear_surr_data)
        self['buttonComputeSyncProb'].connect('clicked', self.compute_sync_prob)
        self['buttonEOIEdit'].connect('clicked', self.edit_eoi)
        self['buttonEOINew'].connect('clicked', self.new_eoi)
        self['buttonEOIDelete'].connect('clicked', self.delete_eois)

    def update_filter_combo_box(self) :
        c = self['comboBoxEntryBand']
        model = c.get_model()
        model.clear()
        filters = self.filters.keys()
        filters.sort()
        for filter in filters :
            model.append([filter])

    def update_signals(self, *args) :
        msg = None

        e2i = self.eegplot.eeg.get_amp().get_electrode_to_indices_dict()

        # Get trode 1
        c = self['comboBoxEntrySignal1']
        model = c.get_model()
        active = c.get_active()
        if active == -1 :
            trode1 = c.child.get_text()
        else :
            trode1 = model[active][0]
        m = re.match('^([^\d]+)(\d+)$', trode1)
        if m is None :
            msg = 'Please select a valid electrode 1.'
        else :
            trode1 = (m.group(1), int(m.group(2)))
            if not e2i.has_key(trode1) :
                msg = 'Selected electrode 1 does not exist.'

        # Get trode 2
        if msg is None :
            c = self['comboBoxEntrySignal2']
            model = c.get_model()
            active = c.get_active()
            if active == -1 :
                trode2 = c.child.get_text()
            else :
                trode2 = model[active][0]
            m = re.match('^([^\d]+)(\d+)$', trode2)
            if m is None :
                msg = 'Please select a valid electrode 2.'
            else :
                trode2 = (m.group(1), int(m.group(2)))
                if not e2i.has_key(trode2) :
                    msg = 'Selected electrode 2 does not exist.'

        # Get band
        if msg is None :
            c = self['comboBoxEntryBand']
            model = c.get_model()
            active = c.get_active()
            if active == -1 :
                band = c.child.get_text()
            else :
                band = model[active][0]
            if not self.filters.has_key(band) :
                msg = 'Selected filter does not exist.'

        # Get overlap
        if msg is None :
            try : overlap = float(self['entryOverlap'].get_text())
            except ValueError, inst : msg = 'Please enter a valid overlap.'

        # Check if overlap equals filter window
        if self.filters[band][0] == overlap :
           msg = 'Warning: The selected filter has a window length equal to the overlap.\n\nSurrogate data can not be computed.'

        if msg is not None :
            mdlg = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                    buttons=gtk.BUTTONS_OK,
                                    message_format=msg)
            mdlg.set_title('Warning')
            mdlg.run()
            mdlg.destroy()
            return

        sync = None
        time = None
        # xxx should probably remove self.sync
        if self.sync is None :
            # Get xlim
            tmin = float(self['entryTmin'].get_text())
            tmax = float(self['entryTmax'].get_text())

            # Get data
#            t, data = self.eegplot.eeg.get_data(0, self.eegplot.eeg.get_tmax())
            # XXX mcc: what is this tmax_real crap (5 lines commented)
            #tmax_real = self.eegplot.eeg.get_tmax()
            #if tmin < 10 : tmin = 0
            #else : tmin = tmin - 10
            #if tmax + 10 > tmax_real : tmax = tmax_real
            #else : tmax = tmax + 10
            print "Dialog_PhaseSynchronyPlot.update_signals: get_data(", tmin, ",", tmax, ")"
            t, data = self.eegplot.eeg.get_data(tmin, tmax)

            # Get signal 1
            s1 = data[:, e2i[trode1]]
            s1 = detrend_linear(s1)

            # Get signal 2
            s2 = data[:, e2i[trode2]]
            s2 = detrend_linear(s2)

            # Plot signals
            self.axesSignals.cla()
            self.axesSignals.grid(True)
            self.axesSignals.plot(t, s1, t, s2)
            self.axesSignals.set_xlim(tmin, tmax)

            # Get filtered signals
            props = self.filters[band]
            print "Dialog_PhaseSynchronyPlot.update_signals(): props=", props
            winLen = props[0]
            filter = bandpass(props[1][0], props[1][1], props[1][2], 
                              props[1][3], props[1][4]) #bandpass returns a function, see bandpass in utils.py
            f1 = filter(s1)
            f2 = filter(s2)
            print "Dialog_PhaseSynchronyPlot.update_signals(): filter=", f1, f2, ". filtering..."
            
            # Plot filtered signals
            self.axesFiltered.cla()
            self.axesFiltered.grid(True)
            self.axesFiltered.plot(t, f1, t, f2)
            self.axesFiltered.set_xlim(tmin, tmax)

            # Comput synchrony
            print "Dialog_PhaseSynchronyPlot.update_signals(): calling synchrony()"
            sync, time = synchrony(f1, f2, t, self.filters[band][0], self.eegplot.eeg.freq, overlap)
            #the utils.py synchrony function seems valid, but I still don't understand why the first 10% of it is off from the rest. -eli

#            sync = []
#            time = []
#            winLen = self.filters[band][0]
#            freq = self.eegplot.eeg.freq
#            nWin = int(winLen * freq) # num samples in window
#            numWin, rem = divmod(len(pdiff), nWin) # num windows
#            sigma = nx.mlab.std(nx.resize(pdiff[:numWin * nWin], (numWin, nWin)), 1)
#            sync = 1. / (1 + sigma)

            # Create time vector
#            time = nx.arange(numWin) * winLen + winLen / 2.
        else :
            sync = self.sync
            time = self.time

        # Plot synchrony
        self.axesSync.cla()
        self.axesSync.grid(True)
        self.axesSync.plot(time, sync, color='k')
        self.axesSync.set_ylim([-0.1, 1.1]) # XXX added by mcc at vtowle's behest

        self.axesSync.text(.75, .75, 'Mean: %f' % mean(sync),
                           color='b',
                           transform = self.axesSync.transAxes)
        # Plot significance level
        if self.ptiled is not None :
            thresh = self.ptiled[band]
            l = self.axesSync.axhline(y=thresh, color='r')
            self.axesSync.text(.75, .75, 'Threshold: %f' % thresh,
                               color='r',
                               transform = self.axesSync.transAxes)

        self.update_time()

        self.canvas.draw()

    def update_time(self, *args) :
        # Get ylim
        tmin = float(self['entryTmin'].get_text())
        tmax = float(self['entryTmax'].get_text())

        self.axesSignals.set_xlim(tmin, tmax)
        self.axesFiltered.set_xlim(tmin, tmax)
        self.axesSync.set_xlim(tmin, tmax)

        self.canvas.draw()

    def browse_sync_file(self, *args) :
        def ok_callback(dirDialog) :
            filename = dirDialog.get_filename()
            self['entrySyncFile'].set_text(filename)
            dirDialog.destroy()

        d = Dialog_FileSelection(
              defaultDir = fmanager.get_lastdir(),
              okCallback = ok_callback,
              title = 'Select Synchrony Output File',
              parent = self.widget)

    def write_sync_file(self, *args) :
        syncFile = self['entrySyncFile'].get_text()
        if syncFile == '' :
            msg = 'Please enter a synchrony output file name.'
            mdlg = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                     buttons=gtk.BUTTONS_OK,
                                     message_format=msg)
            mdlg.set_title('Warning')
            mdlg.run()
            mdlg.destroy()
            return

        # Check if file exists
        if os.path.exists(syncFile) :
            msg = 'Synchrony output file already exists.  Overwrite?'
            mdlg = gtk.MessageDialog(type=gtk.MESSAGE_QUESTION,
                                     buttons=gtk.BUTTONS_YES_NO,
                                     message_format=msg)
            mdlg.set_title('Overwrite File?')
            response = mdlg.run()
            mdlg.destroy()
            if response == gtk.RESPONSE_NO :
                return

        fh = file(syncFile, 'w')

        # Get trodes
        c = self['comboBoxEntrySignal1']
        model = c.get_model()
        active = c.get_active()
        if active == -1 :
            trode1 = c.child.get_text()
        else :
            trode1 = model[active][0]

        c = self['comboBoxEntrySignal2']
        model = c.get_model()
        active = c.get_active()
        if active == -1 :
            trode2 = c.child.get_text()
        else :
            trode2 = model[active][0]
        
        print >> fh, '# Synchrony Output'
        print >> fh, '# Signals: %s, %s' % (trode1, trode2)

        lines = self.axesSync.get_lines()
        xdata = lines[0].get_xdata()
        ydata = lines[0].get_ydata()
        for data in zip(xdata, ydata) :
            print >> fh, "%f, %f" % (data[0], data[1])

        fh.close()

    def edit_filter(self, *args) :
        def ok_callback(props) :
            msg = None
            if props[0] != origFilterName and self.filters.get(props[0]) :
                msg = 'A filter with that name already exists; please choose another name.'
            if msg is not None :
                mdlg = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                        buttons=gtk.BUTTONS_OK,
                                        message_format=msg)
                mdlg.set_title('Warning')
                mdlg.run()
                mdlg.destroy()
                return

            # Update filter name if changed
            if origFilterName != props[0] :
                del self.filters[origFilterName]

            # Update filter properties
            self.filters[props[0]] = [props[1], props[2]]
            model.set_value(model.get_iter(pathlist[0]), 0, props[0])
            model.set_value(model.get_iter(pathlist[0]), 1, props[1])
            model.set_value(model.get_iter(pathlist[0]), 2, props[2][0])
            model.set_value(model.get_iter(pathlist[0]), 3, props[2][1])
            model.set_value(model.get_iter(pathlist[0]), 4, props[2][2])
            model.set_value(model.get_iter(pathlist[0]), 5, props[2][3])
            model.set_value(model.get_iter(pathlist[0]), 6, props[2][4])

            # update filter combo box
            self.update_filter_combo_box()                    

            # Save new EOI in .eegviewrc

            dlgFilterProps.hide_widget()

            return

        # Get selected item
        sel = self['treeViewFilters'].get_selection()
        msg = None
        if sel.count_selected_rows() == 0 :
            msg = 'Please select an filter to edit.'
        elif sel.count_selected_rows() > 1 :
            msg = 'Please select one filter to edit.'
        if msg is not None :
            mdlg = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                     buttons=gtk.BUTTONS_OK,
                                     message_format=msg)
            mdlg.set_title('Warning')
            mdlg.run()
            mdlg.destroy()
            return

        # Get current filter
        (model, pathlist) = sel.get_selected_rows()
        origFilterName = model.get_value(model.get_iter(pathlist[0]), 0)
        props = self.filters[origFilterName]

        # Pop up filter properties dialog box
        dlgFilterProps = Dialog_FilterProps(
                           props=[origFilterName, props[0], props[1]],
                           ok_callback=ok_callback)
        dlgFilterProps.widget.set_transient_for(self.widget)
        dlgFilterProps.show_widget()

    def new_filter(self, *args) :
        def ok_callback(props) :
            msg = None
            if props[0] is '' :
                msg = 'Please provide a name.'
            elif self.filters.get(props[0]) :
                msg = 'A filter with that name already exists; please choose another name.'
            if msg is not None :
                mdlg = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                         buttons=gtk.BUTTONS_OK,
                                         message_format=msg)
                mdlg.set_title('Warning')
                mdlg.run()
                mdlg.destroy()
                return

            # Append new filter to TreeView model
            model = self['treeViewFilters'].get_model()
            model.append([props[0], props[1], props[2][0], props[2][1],
                          props[2][2], props[2][3], props[2][4]])

            # Select the new filter in TreeView
            sel = self['treeViewFilters'].get_selection()
            sel.select_path(len(model) - 1)

            # Add new filter to self
            self.filters[props[0]] = [props[1], props[2]]

            # update filter combo box
            self.update_filter_combo_box()

            # Save new Filter in .eegviewrc

            dlgFilterProps.hide_widget()

            return

        dlgFilterProps = Dialog_FilterProps(ok_callback=ok_callback)
        dlgFilterProps.widget.set_transient_for(self.widget)
        dlgFilterProps.show_widget()

    def delete_filters(self, *args) :
        # Get selected item
        sel = self['treeViewFilters'].get_selection()
        msg = None
        if sel.count_selected_rows() == 0 :
            msg = 'Please select filters to delete.'
            mdlg = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                     buttons=gtk.BUTTONS_OK,
                                     message_format=msg)
            mdlg.set_title('Warning')
            mdlg.run()
            mdlg.destroy()
            return

        # Confirm
        msg = 'Are you sure you wish to delete these filters?'
        mdlg = gtk.MessageDialog(type=gtk.MESSAGE_QUESTION,
                                 buttons=gtk.BUTTONS_YES_NO,
                                 message_format=msg)
        mdlg.set_title('Delete Filters')
        response = mdlg.run()
        mdlg.destroy()
        if response == gtk.RESPONSE_YES :
            names = []
            (model, pathlist) = sel.get_selected_rows()
            pathlist.reverse()
            for path in pathlist :
                iter = model.get_iter(path)
                name = model.get_value(iter, 0)
                names.append(name)
                model.remove(model.get_iter(path))
                del self.filters[name]

            # update filter combo box
            self.update_filter_combo_box()                    

    def edit_eoi(self, *args) :
        def ok_callback(eoi) :
            msg = None
            if eoi.description == '' :
                msg = 'Please give a short description.'
            elif len(eoi) == 0 :
                msg = 'Please select an EOI.'
            elif eoi.description != origDesc and self.eois.get(eoi.description) :
                msg = 'An EOI with that description already exists; please choose another description.'
            if msg is not None :
                mdlg = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                        buttons=gtk.BUTTONS_OK,
                                        message_format=msg)
                mdlg.set_title('Warning')
                mdlg.run()
                mdlg.destroy()
                return

            # Update EOI name if changed
            if origDesc != eoi.description :
                model.set_value(model.get_iter(pathlist[0]), 0, eoi.description)
                self.eois[eoi.description] = eoi
                del self.eois[origDesc]

            # Save new EOI in .eegviewrc

            dlgEOI.destroy_dialog()

            return

        # Get selected item
        sel = self['treeViewEOIs'].get_selection()
        msg = None
        if sel.count_selected_rows() == 0 :
            msg = 'Please select an EOI to edit.'
        elif sel.count_selected_rows() > 1 :
            msg = 'Please select one EOI to edit.'
        if msg is not None :
            mdlg = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                     buttons=gtk.BUTTONS_OK,
                                     message_format=msg)
            mdlg.set_title('Warning')
            mdlg.run()
            mdlg.destroy()
            return

        # Get current EOI
        (model, pathlist) = sel.get_selected_rows()
        origDesc = model.get_value(model.get_iter(pathlist[0]), 0)
        eoi = self.eois[origDesc]

        eoiAll = self.eegplot.get_eeg().get_amp().to_eoi()
        dlgEOI = Dialog_SelectElectrodes(trodes=eoiAll,
                                         selected=eoi,
                                         ok_callback=ok_callback)
        dlgEOI.set_transient_for(self.widget)

    def new_eoi(self, *args) :
        def ok_callback(eoi) :
            msg = None
            if eoi.description == '' :
                msg = 'Please give a short description.'
            elif len(eoi) == 0 :
                msg = 'Please select an EOI.'
            elif self.eois.get(eoi.description) :
                msg = 'An EOI with that description already exists; please choose another description.'
            if msg is not None :
                mdlg = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                         buttons=gtk.BUTTONS_OK,
                                         message_format=msg)
                mdlg.set_title('Warning')
                mdlg.run()
                mdlg.destroy()
                return

            # Append new EOI to TreeView model
            model = self['treeViewEOIs'].get_model()
            model.append([eoi.description])

            # Select the new EOI in TreeView
            sel = self['treeViewEOIs'].get_selection()
            sel.select_path(len(model) - 1)

            # Add new EOI to self
            self.eois[eoi.description] = eoi

            # Save new EOI in .eegviewrc

            dlgEOI.destroy_dialog()

            return

        eoiAll = self.eegplot.get_eeg().get_amp().to_eoi()
        dlgEOI = Dialog_SelectElectrodes(trodes=eoiAll,
                                         ok_callback=ok_callback)
        dlgEOI.set_transient_for(self.widget)

    def delete_eois(self, *args) :
        # Get selected item
        sel = self['treeViewEOIs'].get_selection()
        msg = None
        if sel.count_selected_rows() == 0 :
            msg = 'Please select EOIs to delete.'
            mdlg = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                     buttons=gtk.BUTTONS_OK,
                                     message_format=msg)
            mdlg.set_title('Warning')
            mdlg.run()
            mdlg.destroy()
            return

        # Confirm
        msg = 'Are you sure you wish to delete these EOIs?'
        mdlg = gtk.MessageDialog(type=gtk.MESSAGE_QUESTION,
                                 buttons=gtk.BUTTONS_YES_NO,
                                 message_format=msg)
        mdlg.set_title('Delete EOIs')
        response = mdlg.run()
        mdlg.destroy()
        if response == gtk.RESPONSE_YES :
            (model, pathlist) = sel.get_selected_rows()
            pathlist.reverse()
            for path in pathlist :
                iter = model.get_iter(path)
                desc = model.get_value(iter, 0)
                model.remove(model.get_iter(path))
                del self.eois[desc]

    def toggle_surr_data(self, radioButton, mode) :
        names = ['labelSurrDataNumPairs', 'entrySurrDataNumPairs',
                 'labelSurrDataPtile', 'entrySurrDataPtile',
                 'labelSurrDataTime', 'entrySurrDataTmin', 
                   'labelSurrDataTimeDash', 'entrySurrDataTmax',
                 'labelSurrDataOverlap', 'entrySurrDataOverlap']
                 
        if radioButton.get_active() :
            if mode == 'new' :
                for name in names :
                    self[name].set_sensitive(True)
                self['labelSurrDataFile'].set_label('<b>Output Pickle File:</b> ')
                self['buttonNewLoadSurrData'].set_label('Create New Surrogate Data')
            elif mode == 'load' :
                for name in names :
                    self[name].set_sensitive(False)
                self['labelSurrDataFile'].set_label('<b>Input Pickle File:</b> ')
                self['buttonNewLoadSurrData'].set_label('Load Surrogate Data')

    def browse_surr_data_file(self, *args) :
        def ok_callback(dirDialog):
            filename = dirDialog.get_filename()
            self['entrySurrDataFile'].set_text(filename)
            dirDialog.destroy()

        d = Dialog_FileSelection(
            defaultDir=fmanager.get_lastdir(),
            okCallback=ok_callback,
            title='Select surrogate data file',
            parent=self.widget)

    def new_load_surr_data(self, *args) :
        surrDataFile = self['entrySurrDataFile'].get_text()

        ptiled = {}

        # Create new surrogate data
        if self['radioButtonSurrDataNew'].get_active() :
            if not self.check_surr_data() :
                return

            numPairs = int(self['entrySurrDataNumPairs'].get_text())
            ptile = float(self['entrySurrDataPtile'].get_text())
            tmin = float(self['entrySurrDataTmin'].get_text())
            tmax = float(self['entrySurrDataTmax'].get_text())
            overlap = float(self['entrySurrDataOverlap'].get_text())

            # Create status dialog box
            dlgStatusBox = Dialog_StatusBox(title='Phase Synchrony Status')
            dlgStatusBox.widget.show_now()
            dlgStatusBox.autoconnect()
            dlgStatusBox.append('Generating new surrogate data\n')

#            method = self['comboBoxEntrySurrMethod'].get_text_column()
            method = 0
            surrd = {}
            if method == 0 :
                surrd = self.surr_data_all_pairs(numPairs, tmin, tmax, overlap, dlgStatusBox)
            elif method == 1 :
                surrd = self.surr_data_pair(numPairs, tmin, tmax, overlap, dlgStatusBox)

            # Compute surrogate percentiles in each band
            dlgStatusBox.append ('  Computing percentiles: ')
            for band in self.filters.keys() :
                ptiled[band] = prctile(surrd[band], ptile)
                dlgStatusBox.append('%s ' % band)
            dlgStatusBox.append('\n')

            # Write surrogate data pickle file
            fh = file(surrDataFile, 'w')
            pickle.dump((numPairs, ptile, tmin, tmax, overlap, ptiled), fh)
            fh.close()

        # Load surrogate data
        elif self['radioButtonSurrDataLoad'].get_active() :
            msg = None
            if surrDataFile == '' :
                msg = 'Please select an input surrogate data file.'

            # Report error message
            if msg is not None :
                mdlg = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                         buttons=gtk.BUTTONS_OK,
                                         message_format=msg)
                mdlg.set_title('Warning')
                mdlg.run()
                mdlg.destroy()
                return

            # Load surrogate data pickle file
            fh = file(surrDataFile, 'r')
            numPairs, ptile, tmin, tmax, overlap, ptiled = pickle.load(fh)
            fh.close()

            # Set widget text
            self['entrySurrDataNumPairs'].set_text(str(numPairs))
            self['entrySurrDataPtile'].set_text(str(ptile))
            self['entrySurrDataTmin'].set_text(str(tmin))
            self['entrySurrDataTmax'].set_text(str(tmax))
            self['entrySurrDataOverlap'].set_text(str(overlap))

        self.ptiled = ptiled

        # Set file loaded notification label
        self['labelSurrDataNotif'].set_text('<span foreground="red">Surrogate Data File Loaded: %s</span>' % self['entrySurrDataFile'].get_text())
        self['labelSurrDataNotif'].set_use_markup(True)

        # Get currently selected band
        c = self['comboBoxEntryBand']
        model = c.get_model()
        active = c.get_active()
        band = model[active][0]

        # Plot significance level
        thresh = self.ptiled[band]
        self.axesSync.axhline(y=thresh, color='r')
        self.axesSync.text(.75, .75, 'Threshold: %f' % thresh,
                           color='r',
                           transform = self.axesSync.transAxes)

        self['buttonClearSurrData'].set_sensitive(True)

        # Set limits
        self.update_time()

        self.canvas.draw()

    def check_surr_data(self, check_files=True) :
        msg = None

        surrDataFile = self['entrySurrDataFile'].get_text()
        ptile = float(self['entrySurrDataPtile'].get_text())
        numPairs = int(self['entrySurrDataNumPairs'].get_text())
        tmin = float(self['entrySurrDataTmin'].get_text())
        tmax = float(self['entrySurrDataTmax'].get_text())
        overlap = float(self['entrySurrDataOverlap'].get_text())
            
        try : numPairs = int(numPairs)
        except ValueError, inst : msg = 'Please enter a valid number of pairs.'
        if msg is None :
            try : ptile = float(ptile)
            except ValueError, inst : msg = 'Please enter a valid percentile.'
        if msg is None :
            try : tmin = float(tmin)
            except ValueError, inst : msg = 'Please enter a valid minimum time.'
        if msg is None :
            try : tmax = float(tmax)
            except ValueError, inst : msg = 'Please enter a valid maximum time.'
        if msg is None :
            try : overlap = float(overlap)
            except ValueError, inst : msg = 'Please enter a valid overlap.'
        if check_files and msg is None and surrDataFile == '' :
            msg = 'Please select an output surrogate data file.'

        # Check if overlap equals filter window
        names = []
        for name, props in self.filters.items() :
            if props[0] == overlap :
                names.append(name)
        if len(names) :
            msg = "Warning: The following filters have a window length equal to the overlap: %s.\n\nSurrogate data can not be computed." % ', '.join(names)

        # Report error message
        if msg is not None :
            mdlg = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                     buttons=gtk.BUTTONS_OK,
                                     message_format=msg)
            mdlg.set_title('Warning')
            mdlg.run()
            mdlg.destroy()
            return False

        # Check if output file already exists
        else :
            if check_files :
                if msg is None and os.path.exists(surrDataFile) :
                    msg = 'Surrogate data output file already exists.  Overwrite?'
                    mdlg = gtk.MessageDialog(type=gtk.MESSAGE_QUESTION,
                                             buttons=gtk.BUTTONS_YES_NO,
                                             message_format=msg)
                    mdlg.set_title('Overwrite File?')
                    response = mdlg.run()
                    mdlg.destroy()
                    if response == gtk.RESPONSE_NO :
                        return False

        return True

    def surr_data_all_pairs(self, numPairs, tmin, tmax, overlap, dlgStatusBox) :
        # Create filters
        filters = {}
        for name, props in self.filters.items() :
            filters[name] = (props[0],
                             bandpass(props[1][0], props[1][1],
                                      props[1][2], props[1][3],
                                      props[1][4]))

        # Get data
        tmax_real = self.eegplot.eeg.get_tmax()
        if tmin < 10 : tmin = 0
        else : tmin = tmin - 10
        if tmax + 10 > tmax_real : tmax = tmax_real
        else : tmax = tmax + 10
        print tmin, tmax
        t, data = self.eegplot.eeg.get_data(tmin, tmax)
        e2i = self.eegplot.eeg.get_amp().get_electrode_to_indices_dict()

        # Create an EOI of only subdural trodes (i.e., no scalp trodes)
        # XXX Surrogates are generated from a random set of trodes
        # selected from the entire set of subdural trodes.  Is this
        # appropriate?
        subdurals = set(['FG', 'PG', 'IF', 'AT', 'ST'])
        trodes = [(name, num) for name, num in self.eegplot.eeg.get_amp().to_eoi() if name in subdurals]
        ecog = EOI(electrodes=trodes)
        ecog.sort()

        # Extract random pairs from the data
        surrd = {}
        randInds = (nx.mlab.rand(numPairs, 2) * len(ecog)).astype(nx.Int)
        for i, pair in enumerate(randInds) :
            # Get indices into data
            ie1, ie2 = pair
            i1 = e2i[ecog[ie1]]
            i2 = e2i[ecog[ie2]]

            dlgStatusBox.append('  Computing surrogate %d of %d: %s, %s: ' % (i, numPairs, ecog[ie1], ecog[ie2]))

            # Generate surrogate data
            surr1 = fftsurr(data[:,i1], window=window_hanning)
            surr2 = fftsurr(data[:,i2], window=window_hanning)

            # Generate filtered surrogate data
            for j, tup in enumerate(filters.items()) :
                band, info = tup
                winLen, filter = info
                dlgStatusBox.append('%s ' % band)

                fsurr1 = filter(surr1)
                fsurr2 = filter(surr2)

                winLen = self.filters[band][0]
                freq = self.eegplot.eeg.freq
                sync, time = synchrony(fsurr1, fsurr2, None, winLen, freq, overlap)
                surrd.setdefault(band, []).extend(sync)

            dlgStatusBox.append('\n')

        return surrd

    def get_surr_data_pair(self, numPairs, dlgStatusBox) :
      'xxx'

    def clear_surr_data(self, *args) :
        self.ptiled = None

        self['labelSurrDataNotif'].set_text('')
        self['buttonClearSurrData'].set_sensitive(False)

        self.update_signals()

    def compute_sync_prob(self, *args) :
        if not self.check_surr_data(False) :
           return

        dlgStatusBox = Dialog_StatusBox(title='Phase Synchrony Status')

        # Create new surrogate data
        if self.ptiled is None :
            dlgStatusBox.widget.show_now()
            dlgStatusBox.autoconnect()
            dlgStatusBox.append('Generating new surrogate data\n')

            numPairs = self['entrySurrDataNumPairs'].get_text()
            ptile = self['entrySurrDataPtile'].get_text()
            overlap = self['entrySurrDataOverlap'].get_text()
            surrd = self.surr_data_pair(numPairs, tmin, tmax, overlap, dlgStatusBox)

            # Compute surrogate percentiles in each band
            dlgStatusBox.append ('  Computing percentiles: ')
            for band in self.filters.keys() :
                ptiled[band] = prctile(surrd[band], ptile)
                dlgStatusBox.append('%s ' % band)
            dlgStatusBox.append('\n')
            self.ptiled = ptiled

            # xxx Write surr data?

        # Use loaded surrogate data
        else :
            dlgStatusBox.widget.show_now()
            dlgStatusBox.autoconnect()
            dlgStatusBox.append('Using loaded surrogate data\n')
        
        # Create filters
        filters = {}
        for name, props in self.filters.items() :
            filters[name] = (props[0],
                             bandpass(props[1][0], props[1][1],
                                      props[1][2], props[1][3],
                                      props[1][4]))

        # Create an EOI of only subdural trodes (i.e., no scalp trodes)
        # XXX Surrogates are generated from a random set of trodes
        # selected from the entire set of subdural trodes.  Is this
        # appropriate?
        subdurals = set(['FG', 'PG', 'IF', 'AT', 'ST'])
        trodes = [(name, num) for name, num in self.eegplot.eeg.get_amp().to_eoi() if name in subdurals]
        ecog = EOI(electrodes=trodes)
        ecog.sort()

        # Get tmin and tmax from surr data inputs
        # xxx may not be set if using loaded surr data
        tmin = float(self['entrySurrDataTmin'].get_text())
        tmax = float(self['entrySurrDataTmax'].get_text())

        # Get data
        tmax_real = self.eegplot.eeg.get_tmax()
        if tmin < 10 : tmin = 0
        else : tmin = tmin - 10
        if tmax + 10 > tmax_real : tmax = tmax_real
        else : tmax = tmax + 10
        t, data = self.eegplot.eeg.get_data(tmin, tmax)
        e2i = self.eegplot.eeg.get_amp().get_electrode_to_indices_dict()

        # Filter each trode in data and get phases
        dlgStatusBox.append('Filtering EEG signals\n')
        filterd = {}
        for i, e in enumerate(ecog) :
            dlgStatusBox.append('  Filtering signal %d of %d: %s: ' % (i + 1, len(ecog), str(e)))
            for band, info in filters.items() :
                dlgStatusBox.append('%s ' % band)

                winLen, filter = info
                filterd[(e, band)] = filter(data[:, e2i[e]])
            dlgStatusBox.append('\n')

        dlgStatusBox.append('Computing synchrony between all pairs of electrodes\n')

        # Compute synchrony probabilities for all electrode pairs in each band
        output = {}
        for band, info in filters.items() :
            output[band] = []

        pairs = all_pairs_eoi(ecog)
        stopNum = 0
        for i, pair in enumerate(pairs) :
#            if stopNum == 100 : break
            e1, e2 = pair
            dlgStatusBox.append('  Computing synchrony probability %d of %d: %s, %s: ' % (i + 1, len(pairs), e1, e2))
            for band, info in filters.items() :
                dlgStatusBox.append('%s ' % band)

                # Compute synchrony between pair of filtered signals
                sync, time = synchrony(filterd[(e1, band)], filterd[(e2, band)], t, self.filters[band][0], self.eegplot.eeg.freq)

                # Get surrogate threshold
                threshold = self.ptiled[band]

                # Compute probability of synchronous event
                frac = len(nx.nonzero(sync > threshold)) / float(len(sync))
                output[band].append((frac, (e1, e2)))
            dlgStatusBox.append('\n')
            stopNum = stopNum + 1

        for band, probs in output.items() :
            # Order probs
            probs.sort()
            probs.reverse()

            # Output text to display
            focal = []
            nonfocal = []
            tmpfile = tempfile.mktemp()
            fh = file(tmpfile, 'w')
            print >> fh, '# Band: %s' % band
            print >> fh, '# e1,e2, eoi1,eoi2, frac'
            for frac, pair in probs :
                e1, e2 = pair

                # Determine EOI
                eoi1 = 'None'
                eoi2 = 'None'
                for name, eoi in self.eois.items() :
                    if e1 in eoi : eoi1 = name
                    if e2 in eoi : eoi2 = name

                if eoi1 != 'None' and eoi2 != 'None' :
                    focal.append(frac)
                else :
                    nonfocal.append(frac)

                print >> fh, '%s,%s, %s,%s, %1.3f' % (e1, e2, eoi1, eoi2, frac)
            fh.close()

            # Display synchrony probabilities in gedit
            pid = os.fork()
            if not pid :
                os.system('gedit ' + tmpfile)
                sys.exit(0)

            # Display histogram
            pylab.figure()
            if len(nonfocal) > 0 :
                n, bins, pnonfocal = pylab.hist(nonfocal, bins=40, facecolor='yellow', normed=True)
            if len(focal) > 0 :
                n, bins, pfocal = pylab.hist(focal, bins=20, facecolor='blue', normed=True, alpha=.6)
            pylab.legend((pnonfocal[0], pfocal[0]), ('Nonfocal', 'Focal'))
            pylab.xlabel('Fraction of Synchronous Events')
            pylab.ylabel('Density')
            pylab.title('%s band: Focal Versus Nonfocal Synchronous Events' % band)
            pylab.show()


class Dialog_StatusBox(PrefixWrapper) :
    """
    CLASS: Dialog_StatusBox
    DESCR:
    """
    prefix = 'dlgStatusBox_'
    widgetName = 'dialogStatusBox'

    def __init__(self, title='Status', text='') :
        PrefixWrapper.__init__(self)

        self.widget.set_title(title)

        self.scrolling = True

        self['checkButtonStopScrolling'].connect('toggled', self.toggle_scrolling)

        buffer = self['textView'].get_buffer()

        start_iter = buffer.get_start_iter()
        end_iter = buffer.get_end_iter()
        buffer.delete(start_iter, end_iter)
        buffer.insert(start_iter, text)
        self.update()
            
    def update(self) :
        if self.scrolling :
            buffer = self['textView'].get_buffer()
            iter = buffer.get_iter_at_line(buffer.get_line_count())
            self['textView'].scroll_to_iter(iter, 0.05, True, 0.0, 1.0)

        while gtk.events_pending() :
            gtk.main_iteration()

    def append(self, text) :
        buffer = self['textView'].get_buffer()
        iter = buffer.get_end_iter()
        buffer.insert(iter, text)
        self.update()

    def toggle_scrolling(self, *args) :
      if self['checkButtonStopScrolling'].get_active() :
          self.scrolling = False
      else :
          self.scrolling = True


class Dialog_FilterProps(PrefixWrapper) :
    """
    CLASS: Dialog_FilterProps
    DESCR:
    """
    prefix = 'dlgFilterProps_'
    widgetName = 'dialogFilterProps'

    def __init__(self, props=['', 0.0, (0.0, 0.0, 0.0, 0.0, 0.0)], ok_callback=donothing_callback) :
        PrefixWrapper.__init__(self)

        self.ok_callback = ok_callback

        # Set default values
        self['entryName'].set_text(props[0])
        self['entryWinLen'].set_text(str(props[1]))
        self['entryLpsf'].set_text(str(props[2][0]))
        self['entryLpcf'].set_text(str(props[2][1]))
        self['entryHpcf'].set_text(str(props[2][2]))
        self['entryHpsf'].set_text(str(props[2][3]))
        self['entryFreq'].set_text(str(props[2][4]))

    def on_buttonOK_clicked(self, event) :
        msg = None
        params = []
        try : winLen = float(self['entryWinLen'].get_text())
        except ValueError, inst : msg = inst[0]
        for prop in ['lpsf', 'lpcf', 'hpsf', 'hpcf', 'freq'] :
            key = 'entry' + prop.title()
            try : params.append(float(self[key].get_text()))
            except ValueError, inst : msg = inst[0]
        if msg is not None :
            mdlg = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                     buttons=gtk.BUTTONS_OK,
                                     message_format=msg)
            mdlg.set_title('Warning')
            mdlg.run()
            mdlg.destroy()
            return

        props = [self['entryName'].get_text(), winLen, params]
        self.ok_callback(props)


class Dialog_SurrogateData(PrefixWrapper) :
    """
    CLASS: Dialog_SurrogateData
    DESCR:
    """
    prefix = 'dlgSurrogateData_'
    widgetName = 'dialogSurrogateData'

    def __init__(self, surrogateProps={}, ok_callback=donothing_callback) :
        PrefixWrapper.__init__(self)

        self.ok_callback = ok_callback

        # Set default values
        self['entryNumPairs'].set_text(str(surrogateProps.get('numPairs', '')))
        self['entryOutputFile'].set_text(surrogateProps.get('outputFile', ''))

        # Initialize Filters TreeView
        self.filters = {}
        if self['treeViewFilters'].get_model() is None :
            colNames = ['Name', 'Window Length', 'LPSF', 'LPCF', 'HPCF', 'HPSF', 'Frequency']
            for i, name in enumerate(colNames) :
                cell = gtk.CellRendererText()
                col = gtk.TreeViewColumn(name, cell, text=i)
                self['treeViewFilters'].append_column(col)

            model = gtk.ListStore(str, str, str, str, str, str, str)
            self['treeViewFilters'].set_model(model)

        # Delete filter treeview rows
        model = self['treeViewFilters'].get_model()
        iter = model.get_iter_first()
        if iter is not None :
          ok = model.remove(iter)
          while ok :
              ok = model.remove(iter)

        # Add filters
        if surrogateProps.get('filters') is not None :
            self.filters = surrogateProps['filters']
        for name, props in self.filters.items() :
            model.append([name, props[0], props[1][0], props[1][1], 
                          props[1][2], props[1][3], props[1][4]])
        self['treeViewFilters'].get_selection().set_mode(gtk.SELECTION_MULTIPLE)

        # Set default time range to be time limits in eeg window
        if surrogateProps.get('tMin') is not None :
            self['entrytMin'].set_text(str(surrogateProps['tMin']))
        if surrogateProps.get('tMax') is not None :
            self['entrytMax'].set_text(str(surrogateProps['tMax']))

        # Set button click callbacks
        self['buttonFilterEdit'].connect('clicked', self.edit_filter)
        self['buttonFilterNew'].connect('clicked', self.new_filter)
        self['buttonFilterDelete'].connect('clicked', self.delete_filters)
        self['buttonOutputFileBrowse'].connect('clicked', self.browse_output_file)

    def edit_filter(self, *args) :
        def ok_callback(props) :
            msg = None
            if props[0] is '' :
                msg = 'Please provide a name.'
            elif props[0] != origFilterName and self.filters.get(props[0]) :
                msg = 'A filter with that name already exists; please choose another name.'
            if msg is not None :
                mdlg = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                        buttons=gtk.BUTTONS_OK,
                                        message_format=msg)
                mdlg.set_title('Warning')
                mdlg.run()
                mdlg.destroy()
                return

            # Update filter name if changed
            if origFilterName != props[0] :
                del self.filters[origFilterName]

            # Update filter properties
            self.filters[props[0]] = [props[1], props[2]]
            model.set_value(model.get_iter(pathlist[0]), 0, props[0])
            model.set_value(model.get_iter(pathlist[0]), 1, props[1])
            model.set_value(model.get_iter(pathlist[0]), 2, props[2][0])
            model.set_value(model.get_iter(pathlist[0]), 3, props[2][1])
            model.set_value(model.get_iter(pathlist[0]), 4, props[2][2])
            model.set_value(model.get_iter(pathlist[0]), 5, props[2][3])
            model.set_value(model.get_iter(pathlist[0]), 6, props[2][4])

            dlgFilterProps.hide_widget()

            return

        # Get selected item
        sel = self['treeViewFilters'].get_selection()
        msg = None
        if sel.count_selected_rows() == 0 :
            msg = 'Please select an filter to edit.'
        elif sel.count_selected_rows() > 1 :
            msg = 'Please select one filter to edit.'
        if msg is not None :
            mdlg = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                     buttons=gtk.BUTTONS_OK,
                                     message_format=msg)
            mdlg.set_title('Warning')
            mdlg.run()
            mdlg.destroy()
            return

        # Get current filter
        (model, pathlist) = sel.get_selected_rows()
        origFilterName = model.get_value(model.get_iter(pathlist[0]), 0)
        props = self.filters[origFilterName]

        dlgFilterProps = Dialog_FilterProps(
                           props=[origFilterName, props[0], props[1]],
                           ok_callback=ok_callback)
        dlgFilterProps.widget.set_transient_for(self.widget)
        dlgFilterProps.show_widget()

    def new_filter(self, *args) :
        def ok_callback(props) :
            msg = None
            if props[0] is '' :
                msg = 'Please provide a name.'
            elif self.filters.get(props[0]) :
                msg = 'A filter with that name already exists; please choose another name.'
            if msg is not None :
                mdlg = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                         buttons=gtk.BUTTONS_OK,
                                         message_format=msg)
                mdlg.set_title('Warning')
                mdlg.run()
                mdlg.destroy()
                return

            # Append new filter to TreeView model
            model = self['treeViewFilters'].get_model()
            model.append([props[0], props[1], props[2][0], props[2][1],
                          props[2][2], props[2][3], props[2][4]])

            # Select the new filter in TreeView
            sel = self['treeViewFilters'].get_selection()
            sel.select_path(len(model) - 1)

            # Add new filter to self
            self.filters[props[0]] = [props[1], props[2]]

            dlgFilterProps.hide_widget()

            return

        dlgFilterProps = Dialog_FilterProps(ok_callback=ok_callback)
        dlgFilterProps.widget.set_transient_for(self.widget)
        dlgFilterProps.show_widget()

    def delete_filters(self, *args) :
        # Get selected item
        sel = self['treeViewFilters'].get_selection()
        msg = None
        if sel.count_selected_rows() == 0 :
            msg = 'Please select filters to delete.'
            mdlg = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                     buttons=gtk.BUTTONS_OK,
                                     message_format=msg)
            mdlg.set_title('Warning')
            mdlg.run()
            mdlg.destroy()
            return

        # Confirm
        msg = 'Are you sure you wish to delete these filters?'
        mdlg = gtk.MessageDialog(type=gtk.MESSAGE_QUESTION,
                                 buttons=gtk.BUTTONS_YES_NO,
                                 message_format=msg)
        mdlg.set_title('Delete Filters')
        response = mdlg.run()
        mdlg.destroy()
        if response == gtk.RESPONSE_YES :
            (model, pathlist) = sel.get_selected_rows()
            pathlist.reverse()
            for path in pathlist :
                iter = model.get_iter(path)
                name = model.get_value(iter, 0)
                model.remove(model.get_iter(path))
                del self.filters[name]

    def browse_output_file(self, *args) :
        def ok_callback(dirDialog):
            filename = dirDialog.get_filename()
            self['entryOutputFile'].set_text(filename)
            dirDialog.destroy()

        d = Dialog_FileSelection(
            defaultDir=fmanager.get_lastdir(),
            okCallback=ok_callback,
            title='Select surrogate data output file',
            parent=self.widget)

    def on_buttonOK_clicked(self, event) :
        surrogateProps = {}
        surrogateProps['filters'] = self.filters

        msg = None
        try : surrogateProps['tMin'] = float(self['entrytMin'].get_text())
        except ValueError, inst : msg = errstr[0]
        try : surrogateProps['tMax'] = float(self['entrytMax'].get_text())
        except ValueError, inst : msg = errstr[0]
        try : surrogateProps['numPairs'] = int(self['entryNumPairs'].get_text())
        except ValueError, inst : msg = errstr[0]
        surrogateProps['outputFile'] = self['entryOutputFile'].get_text()

        if msg is not None :
            mdlg = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                     buttons=gtk.BUTTONS_OK,
                                     message_format=msg)
            mdlg.set_title('Warning')
            mdlg.run()
            mdlg.destroy()
            return

        self.ok_callback(surrogateProps)


class Dialog_EEGParams(PrefixWrapper):
    """
    CLASS: Dialog_EEGParams
    DESCR:
    """
    prefix = 'dlgEEG_'
    widgetName = 'dialogEEG'
    def __init__(self, fullpath, callback):
        self._inited = False
        PrefixWrapper.__init__(self)
        
        self.callback = callback
        self.ftypeCode = CodeRegistry.get_code_from_registry('EEG file type')
        self.stypeCode = CodeRegistry.get_code_from_registry('EEG type')
        self.stateCode = CodeRegistry.get_code_from_registry('Behavioral State')
        

        self.stypeMenu = self['optionmenuSeizuretype']
        self.ftypeMenu = self['optionmenuFiletype']
        self.stateMenu = self['optionmenuState']

        menu, self.ftypeItemd = make_option_menu_from_strings(
            self.ftypeCode.descs)
        self.ftypeMenu.set_menu(menu)

        menu, self.stypeItemd = make_option_menu_from_strings(
            self.stypeCode.descs)
        self.stypeMenu.set_menu(menu)

        menu, self.stateItemd = make_option_menu_from_strings(
            self.stateCode.descs)
        self.stateMenu.set_menu(menu)

        base, fname = os.path.split(fullpath)
        self['entryFilename'].set_text(fname)


        self._inited = True

    def on_buttonOK_clicked(self, event):
        pars = self.get_params()
        storeParamsOnOK[self.widgetName] = pars
        self.callback(pars)        

    def get_params(self):
        if not self._inited:
            return {
                'filename'        : '',
                'date'            : '0000-00-00 00:00:00',
                'description'     : '',
                'channels'        : 128,
                'freq'            : 400,
                'classification'  : 99,
                'file_type'       : 1,
                'behavior_state'  : 99,
                }
        
        stypeItem = self.stypeMenu.get_menu().get_active()
        seizureType =  self.stypeCode.to_code[self.stypeItemd[stypeItem]]

        ftypeItem = self.ftypeMenu.get_menu().get_active()
        fileType =  self.ftypeCode.to_code[self.ftypeItemd[ftypeItem]]

        stateItem = self.stateMenu.get_menu().get_active()
        stateType =  self.stateCode.to_code[self.stateItemd[stateItem]]
        
        return {
            'filename'        : self['entryFilename'].get_text().strip(),
            'date'            : self['entryDate'].get_text().strip(),
            'description'     : self['entryDesc'].get_text().strip(),
            'channels'        : int(self['entryNumchan'].get_text()),
            'freq'            : int(self['entrySamplefreq'].get_text()),
            'classification'  : seizureType,
            'file_type'       : fileType,
            'behavior_state'  : stateType,
            }

        return {'name': 'John'}



class AutoPlayDialog(gtk.Dialog, Observer):
    """
    CLASS: AutoPlayDialog
    DESCR:
    """
    idleID = None
    ind = 0
    direction = 1
    lastSteps = None

    def __init__(self, tmin, tmax, twidth, newLength, scalarDisplay, quitHook=None):
        Observer.__init__(self)
        gtk.Dialog.__init__(self, 'Auto play')

        self.eegtmin = tmin
        self.eegtmax = tmax
        self.eegtwidth = twidth
        self.newLength = newLength
        #save the original eeg argdata
        
        self.tmin = tmin
        self.tmax = tmax
        self.twidth = twidth
        self.quitHook = None
        
        if scalarDisplay["scalardisplay"]: #update the movie box for scalar driving possibility
            radioGrp = None
            button = gtk.RadioButton(radioGrp)
            button.set_label('Page EEG')
            button.set_active(True)
            button.connect('clicked', self.page_changed)
            self.buttonPageEEG = button
            self.buttonPageEEG.show()
        
            button = gtk.RadioButton(button)
            button.set_label('Page Scalar Data')
            button.connect('clicked', self.page_changed)
            self.buttonPageScalar = button
            self.buttonPageScalar.show()
            
            button = gtk.RadioButton(button)
            button.set_label("Page Both")
            button.connect('clicked', self.page_changed)
            self.buttonPageBoth = button
            self.buttonPageBoth.show()
            self.newlength = twidth #make sure we don't page eeg-style
        
        vbox = self.vbox

        self.labelMin = gtk.Label('Min time')
        self.labelMin.show()

        self.labelMax = gtk.Label('Max time')
        self.labelMax.show()

        self.labelStep = gtk.Label('Time intv.')
        self.labelStep.show()

        self.entryMin = gtk.Entry()
        self.entryMin.show()
        self.entryMin.set_width_chars(10)
        self.entryMin.set_text('%1.1f' % tmin)

        
        self.entryMax = gtk.Entry()
        self.entryMax.show()
        self.entryMax.set_width_chars(10)
        self.entryMax.set_text('%1.1f' % tmax )

        self.entryStep = gtk.Entry()
        self.entryStep.show()
        self.entryStep.set_width_chars(10)
        self.entryStep.set_activates_default(True)
        self.entryStep.set_text('%1.1f' %twidth)

        table = gtk.Table(2,5)
        table.show()
        table.set_row_spacings(4)
        table.set_col_spacings(4)

        table.attach(self.labelMin,  0, 1, 0, 1)
        table.attach(self.labelMax,  0, 1, 1, 2)
        table.attach(self.labelStep, 0, 1, 2, 3)

        table.attach(self.entryMin,  1, 2, 0, 1)
        table.attach(self.entryMax,  1, 2, 1, 2)
        table.attach(self.entryStep, 1, 2, 2, 3)
        if scalarDisplay["scalardisplay"]:
            table.attach(self.buttonPageEEG, 0,1,3,4)
            table.attach(self.buttonPageScalar,1,2,3,4) 
            table.attach(self.buttonPageBoth,1,2,4,5)
        self.vbox.pack_start(table, True, True)

        buttonBack = self.add_button(gtk.STOCK_GO_BACK, gtk.RESPONSE_REJECT)
        buttonStop = self.add_button(gtk.STOCK_STOP, gtk.RESPONSE_CANCEL)
        buttonPlay = self.add_button(gtk.STOCK_GO_FORWARD, gtk.RESPONSE_OK)
        buttonQuit = self.add_button(gtk.STOCK_QUIT, gtk.RESPONSE_CLOSE)

        buttonStop.connect("clicked", self.stop)
        buttonPlay.connect("clicked", self.forward)
        buttonBack.connect("clicked", self.back)
        buttonQuit.connect("clicked", self.quit)
        #self.set_default_response(gtk.RESPONSE_OK)

        frame = gtk.Frame('Movies')
        frame.show()
        frame.set_border_width(5)
        vbox.pack_start(frame, False, False)

        hbox = gtk.HBox()
        hbox.show()
        hbox.set_spacing(3)
        
        frame.add(hbox)
        self.scalarDisplay = scalarDisplay

        def set_filename(*args):
            #fname = fmanager.get_filename()
            dialog = gtk.FileChooserDialog("Save Movie As...",
                                          None,
                                          gtk.FILE_CHOOSER_ACTION_SAVE,
                                          (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                          gtk.STOCK_OPEN, gtk.RESPONSE_OK))
            dialog.set_default_response(gtk.RESPONSE_OK)
            response = dialog.run()
            if response == gtk.RESPONSE_OK:
                fname = dialog.get_filename()
            dialog.destroy()

            if fname is None: return
            self.entryMovie.set_text(fname)

            # try and write a dummy file to fname to make sure the dir
            # is writable
            tmpfile = fname + 'tmp'
            try: file(tmpfile, 'w').write('123')
            except IOError:
                error_msg('Basepath %s does not appear to be writable' % fname,
                          parent=self)
                return
            else:
                os.remove(tmpfile)

            
        buttonSave = gtk.Button(stock=gtk.STOCK_SAVE)
        buttonSave.show()
        buttonSave.connect('clicked', set_filename)
        hbox.pack_start(buttonSave, False, False)

        
        self.entryMovie = gtk.Entry()
        self.entryMovie.show()
        hbox.pack_start(self.entryMovie, True, True)

        def check_filename(*args):
            if self.checkButtonMovie.get_active() and not self.entryMovie.get_text():
                set_filename()
                
        self.checkButtonMovie = gtk.CheckButton('Save images')
        self.checkButtonMovie.show()
        self.checkButtonMovie.connect('toggled', check_filename)
        hbox.pack_start(self.checkButtonMovie, False, False)

        self.statbar = gtk.Statusbar()
        self.statbar.show()
        self.statbarCID = self.statbar.get_context_id('my stat bar')
        vbox.pack_end(self.statbar, False, False)

    def page_changed(self, *args):
        print "AUTOPAGE: driver changed to ", args[0]
        if self.buttonPageScalar.get_active():
            self.tmin = self.scalarDisplay["tmin"]
            self.tmax = self.scalarDisplay["tmax"]
            self.twidth = self.scalarDisplay["tstep"]
        if self.buttonPageEEG.get_active():
            self.tmin = self.eegtmin
            self.tmax = self.eegtmax
            self.twidth = self.eegtwidth
        self.entryMin.set_text('%1.1f' % self.tmin )
        self.entryMax.set_text('%1.1f' % self.tmax )
        self.entryStep.set_text('%1.1f' % self.twidth )
            #the above lines update the default data in the text boxes in the dialog for the scalar array mapper as opposed to the eeg tracer or vice versa
            
    def update_status_bar(self):

        self.statbar.pop(self.statbarCID) 
        mid = self.statbar.push(
            self.statbarCID,
            'Playing time step %d of %d'% (self.ind, len(self.steps)) )
        
        
    def recieve(self, *args): pass

    def forward(self, *args):
        self.stop()
        good = self.setpars()
        if not good: return False
        self.direction = 1
        self.idleID = gobject.idle_add(self.scroll)


    def back(self, *args):
        self.stop()
        good = self.setpars()
        if not good: return False
        self.direction = -1
        self.idleID = gobject.idle_add(self.scroll)
        return True

    def stop(self, *args):
        if self.idleID is None: return 
        gobject.source_remove(self.idleID)
        self.idleID = None

    def quit(self, *args):
        self.stop()
        self.destroy()
        if self.quitHook is not None:
            self.quitHook()
        
    def scroll(self, *args):
        fname = '%s%05d' % (self.entryMovie.get_text(), self.ind)
        #print 'fname', fname
        self.update_status_bar()
        if self.ind>=0 and self.ind<len(self.steps):
            thisMin = self.steps[self.ind]
            thisMax = thisMin + self.twidth
            self.view3.offset = self.steps[self.ind]
            print "DIALOGS SET VIEW3 OFFSET to ", self.view3.offset
            #decide who to send the signal to
            if self.scalarDisplay["scalardisplay"]:
                #if the scalar option is available, choose between them: 
                if self.buttonPageScalar.get_active():
                    self.broadcast(Observer.SET_SCALAR, thisMin, thisMax)
                else:
                    #self.broadcast(Observer.SET_TIME_LIM, thisMin, thisMax)
                    self.view3.compute_coherence()
                    self.view3.plot_band()
                
            else: #otherwise just broadcast the eeg driver sig
                #self.broadcast(Observer.SET_TIME_LIM, thisMin, thisMax)
                self.view3.compute_coherence()
                self.view3.plot_band()
            #update the data (actual scrolling step):
            self.ind += self.direction
            
            if self.checkButtonMovie.get_active():
                self.broadcast(Observer.SAVE_FRAME, fname)
            return True
        else:
            self.stop()
            self.ind=0
            return False


    def setpars(self, *args):
        
        valMin = str2num_or_err(
            self.entryMin.get_text(), self.labelMin, parent=self)
        if valMin is None: return False
        valMax = str2num_or_err(
            self.entryMax.get_text(), self.labelMax, parent=self)
        if valMax is None: return False
        valStep = str2num_or_err(
            self.entryStep.get_text(), self.labelStep, parent=self)
        if valStep is None: return False



        self.steps = arange(valMin, valMax-self.newLength+0.001, valStep)
        #so if scalar data is driving, self.newlength = self.twidth
        #but otherwise, we want the last step to be no less than newlength from the end of the sweep length
        #where valmax is passed in as sweep length from the NFFT var in view3
        print "SETPARS!", valMin, valMax, valStep, self.twidth, len(self.steps), self.steps #DEBUG
	    #print self.steps
	    #print self.lastSteps
        #if self.steps != self.lastSteps:
        #    self.ind = 0
	    #the above were giving me trouble and don't seem very useful -eli
        self.lastSteps = self.steps

        return True


class SpecProps(gtk.Dialog):
    """
    CLASS: SpecProps
    DESCR:
    """
    def __init__(self):
        gtk.Dialog.__init__(self, 'Specwin properties')

        self.freqMin = None
        self.freqMax = None
        self.colorMin = None
        self.colorMax = None

        boxWid = 12

        table=gtk.Table(2,2)
        table.set_col_spacings(3)
        table.set_row_spacings(3)
        table.show()
        self.vbox.add(table)

        
        l = gtk.Label('Freq. min')
        l.show()
        e = gtk.Entry()
        if (self.freqMin == None):
            e.set_text('0.0')
        else:
            e.set_text(str(self.freqMin))
        e.set_width_chars(boxWid)
        e.show()
        self.entryFMin = e
        table.attach(l, 0, 1, 0, 1,
                     xoptions=gtk.SHRINK, yoptions=gtk.SHRINK)
        table.attach(e, 1, 2, 0, 1,
                     xoptions=gtk.FILL, yoptions=gtk.SHRINK)

        l = gtk.Label('Freq. max')
        l.show()
        e = gtk.Entry()
        if (self.freqMax == None):
            e.set_text('100.0')
        else:
            e.set_text(str(self.freqMax))
        e.set_width_chars(boxWid)
        e.show()
        self.entryFMax = e
        table.attach(l, 0, 1, 1, 2,
                     xoptions=gtk.SHRINK, yoptions=gtk.SHRINK)
        table.attach(e, 1, 2, 1, 2,
                     xoptions=gtk.FILL, yoptions=gtk.SHRINK)


        l = gtk.Label('Color min')
        l.show()
        e = gtk.Entry()
        e.set_width_chars(boxWid)
        e.show()
        self.entryCMin = e
        table.attach(l, 0, 1, 2, 3,
                     xoptions=gtk.SHRINK, yoptions=gtk.SHRINK)
        table.attach(e, 1, 2, 2, 3,
                     xoptions=gtk.FILL, yoptions=gtk.SHRINK)

        l = gtk.Label('Color max')
        l.show()
        e = gtk.Entry()

        e.set_width_chars(boxWid)
        e.show()
        self.entryCMax = e
        table.attach(l, 0, 1, 3, 4,
                     xoptions=gtk.SHRINK, yoptions=gtk.SHRINK)
        table.attach(e, 1, 2, 3, 4,
                     xoptions=gtk.FILL, yoptions=gtk.SHRINK)

        self.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        self.add_button(gtk.STOCK_APPLY, gtk.RESPONSE_APPLY)
        self.add_button(gtk.STOCK_OK, gtk.RESPONSE_OK)
        self.set_default_response(gtk.RESPONSE_OK)

    def validate(self, *args):
        """
        Call this before closing/hiding dialog; if valid you can call
        get_clim or get_flim
        """
        v = str2num_or_err(self.entryFMin.get_text(), 'Freq min')
        if v is None: return False
        self.freqMin = v
        v = str2num_or_err(self.entryFMax.get_text(), 'Freq max')
        if v is None: return False
        self.freqMax = v
        v = str2num_or_err(self.entryCMin.get_text(), 'Color min')
        if v is None: return False
        self.colorMin = v
        v = str2num_or_err(self.entryCMax.get_text(), 'Color max')
        if v is None: return False
        self.colorMax = v
        return True

    def get_clim(self):
        return self.colorMin, self.colorMax

    def get_flim(self):
        return self.freqMin, self.freqMax

    def set_clim(colorMin, colorMax):
        self.colorMin = colorMin
        self.colorMax = colorMax
        
    def set_flim(freqMin, freqMax):
        self.freqMin = freqMin
        self.freqMax = freqMax
        
