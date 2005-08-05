import sys, os
import gtk, gobject


from Numeric import arange

from matplotlib.cbook import enumerate, exception_to_str
from matplotlib.mlab import detrend_none, detrend_mean, detrend_linear,\
     window_none, window_hanning
from pbrainlib.gtkutils import str2num_or_err, donothing_callback, \
     Dialog_FileSelection, Dialog_DirSelection, \
     simple_msg, ignore_or_act, not_implemented, \
     make_option_menu_from_strings

import CodeRegistry
from data import EOI
from utils import export_to_cohstat, filter_grand_mean, \
     all_pairs_eoi, cohere_bands, cohere_pairs_eeg, export_cohstat_xyz

from gladewrapper import PrefixWrapper
from shared import fmanager, eegviewrc
from borgs import Shared
from events import Observer
# use this if you want to store some information about the dialogs
# between calls.
storeParamsOnOK = {}


class Dialog_SelectElectrodes(gtk.Dialog):
    """

    Select a subset of trodes and call ok_callback(selectedTrodes).

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
            print trodes
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
        return gtk.TRUE



class Dialog_CohstatExport(PrefixWrapper):
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
            while gtk.events_pending(): gtk.mainiteration()

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
    Get the coherence params.  On OK, will call okCallback(m), where
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


class Dialog_Preferences(PrefixWrapper):
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
    prefix = 'dlgAnnotate_'
    widgetName = 'dialogAnnotate'

    def __init__(self, eegplot, params={}, ok_callback=donothing_callback) :
        PrefixWrapper.__init__(self)

        self.ok_callback = ok_callback
        self.eegplot = eegplot

        def select_eoi(*args) :
            def ok_callback(eoi) :
                if eoi.description == '' :
                    # Require a description.
                    mdlg = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                            buttons=gtk.BUTTONS_OK,
                                            message_format='Please give a short description.')
                    mdlg.set_title('Warning')
                    mdlg.run()
                    mdlg.destroy()
                    return

                if not self.eegplot.annman.eois.get(eoi.description) :
                    model = self['comboBoxEntryEOI'].get_model()
                    model.append([eoi.description])
                    self['comboBoxEntryEOI'].set_active(len(model) - 1)

                self.eegplot.annman.add_eoi(eoi)

                dlg.destroy_dialog()
                return

            eoiAll = self.eegplot.get_eeg().get_amp().to_eoi()
            eoiActive = params['eoi']
            dlg = Dialog_SelectElectrodes(trodes=eoiAll,
                                          ok_callback=ok_callback,
                                          selected=eoiActive)
            dlg.set_transient_for(self.widget)

        # Set EOI combo options
        if self['comboBoxEntryEOI'].get_model() is None :
            model = gtk.ListStore(str)
            for eoi in self.eegplot.annman.eois.keys() :
                model.append([eoi])
            self['comboBoxEntryEOI'].set_model(model)
            self['comboBoxEntryEOI'].set_text_column(0)
            self['comboBoxEntryEOI'].set_active(0)

        self['buttonEOISelect'].connect('clicked', select_eoi)

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
        self['entryStartTime'].set_text('%1.1f' % params.get('startTime', 0.0))
        self['entryEndTime'].set_text('%1.1f' % params.get('endTime', 1.0))
        self['entryUsername'].set_text(params.get('username', 'unknown'))
        self['colorButton'].set_color(gtk.gdk.color_parse(params.get('color', '#ddddff')))
        self['hscaleAlpha'].set_value(params.get('alpha', 0.0))
        self['textViewAnnotation'].get_buffer().set_text(params.get('annotation', ''))

        # Set active eoi combo box entry
        if params.get('eoi') :
            print '*', params['eoi']
            model = self['comboBoxEntryEOI'].get_model()
            n = 0
            for rw in model :
                if rw[0] == params['eoi'].get_description() :
                    self['comboBoxEntryEOI'].set_active(n)
                n += 1
        else :
            self['comboBoxEntryEOI'].set_active(0)

        # Set active code combo box entry
        if params.get('code') :
            model = self['comboBoxEntryCode'].get_model()
            n = 0
            for rw in model :
                if rw[0] == params.get('code', '') :
                    self['comboBoxEntryCode'].set_active(n)
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
                n += 1
        else :
            self['comboBoxEntryState'].set_active(0)

    def get_params(self) :
        params = {}
        params['startTime'] = float(self['entryStartTime'].get_text())
        params['endTime'] = float(self['entryEndTime'].get_text())
        params['username'] = self['entryUsername'].get_text()

        # Get eoi description to look up in annman's eoi list.
        description = ''
        c = self['comboBoxEntryEOI']
        model = c.get_model()
        active = c.get_active()
        if active >= 0 :
            description = model[active][0]
        try : self.eegplot
        except :
            params['eoi'] = None
        else :
            params['eoi'] = self.eegplot.annman.eois[description]

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

        start, end = self['textViewAnnotation'].get_buffer().get_bounds()
        params['annotation'] = self['textViewAnnotation'].get_buffer().get_text(start, end)

        return params

    def on_buttonOK_clicked(self, event) :
        params = self.get_params()
        self.ok_callback(params)

class Dialog_AnnBrowser(PrefixWrapper) :
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
        # Set combo box username options
        usernames = ['Any']
        ann = self.eegplot.eeg.get_ann()
        for a in ann.values() :
            if a['username'] not in usernames :
              usernames.append(a['username'])
        model = gtk.ListStore(str)
        for username in usernames :
            model.append([username])
        self['comboBoxEntryUsername'].set_model(model)
        if self['comboBoxEntryCode'].get_model() is None :
            self['comboBoxEntryUsername'].set_text_column(0)
            self['comboBoxEntryUsername'].set_active(0)

        # Set combo box code options
        if self['comboBoxEntryCode'].get_model() is None :
            codes = ['Any'] + CodeRegistry.get_code_from_registry('Annotation code').descs
            model = gtk.ListStore(str)
            for code in codes :
                model.append([code])
            self['comboBoxEntryCode'].set_model(model)
            self['comboBoxEntryCode'].set_text_column(0)
            self['comboBoxEntryCode'].set_active(0)

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
            for widget in ['label1', 'label2', 'label3', 'label4', 'label5', 'label6',
                           'labelStartTime', 'labelEndTime',
                           'labelUsername', 'labelCode', 'labelColor',
                           'textViewAnnotation'] :
                self[widget].set_sensitive(True)

            # Update text
            s = '%1.1f' % ann[key]['startTime']
            self['labelStartTime'].set_text(s)
            e = '%1.1f' % ann[key]['endTime']
            self['labelEndTime'].set_text(e)
            self['labelUsername'].set_text(ann[key]['username'])
            self['labelColor'].set_text(ann[key]['color'])
            self['labelCode'].set_text(ann[key]['code'])
            self['textViewAnnotation'].get_buffer().set_text(ann[key]['annotation'])

        else :
            # Make widgets not sensitive
            for widget in ['label1', 'label2', 'label3', 'label4', 'label5', 'label6',
                           'labelStartTime', 'labelEndTime',
                           'labelUsername', 'labelCode', 'labelColor',
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

class Dialog_EEGParams(PrefixWrapper):
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
    idleID = None
    ind = 0
    direction = 1
    lastSteps = None

    def __init__(self, tmin, tmax, twidth, quitHook=None):
        Observer.__init__(self)
        gtk.Dialog.__init__(self, 'Auto play')

        self.tmin = tmin
        self.tmax = tmax
        self.twidth = twidth
        self.quitHook = None
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
        self.entryMin.set_text('0.0')

        
        self.entryMax = gtk.Entry()
        self.entryMax.show()
        self.entryMax.set_width_chars(10)
        self.entryMax.set_text('%1.1f' % tmax )

        self.entryStep = gtk.Entry()
        self.entryStep.show()
        self.entryStep.set_width_chars(10)
        self.entryStep.set_activates_default(True)
        self.entryStep.set_text('10.0')

        table = gtk.Table(2,3)
        table.show()
        table.set_row_spacings(4)
        table.set_col_spacings(4)

        table.attach(self.labelMin,  0, 1, 0, 1)
        table.attach(self.labelMax,  0, 1, 1, 2)
        table.attach(self.labelStep, 0, 1, 2, 3)

        table.attach(self.entryMin,  1, 2, 0, 1)
        table.attach(self.entryMax,  1, 2, 1, 2)
        table.attach(self.entryStep, 1, 2, 2, 3)
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

            


        def set_filename(*args):
            fname = fmanager.get_filename()
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

    def update_status_bar(self):

        self.statbar.pop(self.statbarCID) 
        mid = self.statbar.push(
            self.statbarCID,
            'Playing time step %d of %d'% (self.ind, len(self.steps)) )
        
        
    def recieve(self, *args): pass

    def forward(self, *args):
        self.stop()
        good = self.setpars()
        if not good: return gtk.FALSE
        self.direction = 1
        self.idleID = gtk.idle_add(self.scroll)


    def back(self, *args):
        self.stop()
        good = self.setpars()
        if not good: return gtk.FALSE
        self.direction = -1
        self.idleID = gtk.idle_add(self.scroll)
        return gtk.TRUE

    def stop(self, *args):
        if self.idleID is None: return 
        gtk.idle_remove(self.idleID)
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
            self.broadcast(Observer.SET_TIME_LIM, thisMin, thisMax)
            self.ind += self.direction

            if self.checkButtonMovie.get_active():
                self.broadcast(Observer.SAVE_FRAME, fname)
            return gtk.TRUE
        else:
            self.stop()
            self.ind=0
            return gtk.FALSE


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



        self.steps = arange(valMin, valMax-self.twidth+0.001, valStep)
        #print valMin, valMax, valStep, self.twidth, len(self.steps)
        if self.steps != self.lastSteps:
            self.ind = 0
        self.lastSteps = self.steps

        return True

    


class SpecProps(gtk.Dialog):
    def __init__(self):
        gtk.Dialog.__init__(self, 'Specwin properties')

        boxWid = 12

        table=gtk.Table(2,2)
        table.set_col_spacings(3)
        table.set_row_spacings(3)
        table.show()
        self.vbox.add(table)

        
        l = gtk.Label('Freq. min')
        l.show()
        e = gtk.Entry()
        e.set_text('0.0')
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
        e.set_text('100.0')
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
