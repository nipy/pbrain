import sys, os
import gtk, gobject


#from matplotlib.numerix import arange
from scipy import arange

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


class Dialog_FilterElectrodes(gtk.Dialog):
    """

    Select a subset of trodes and call ok_callback(selectedTrodes).

    trodes and selectedTrodes are a list of tuples; each tuple is
    (grdName, grdNum).
    
    """
    def on_rectify_toggled(self, cell, path_str, model):
        print "Dialog_SelectElectrodes: cell=",cell, " path_str=", path_str, " model=", model
        # get selected column
        column = cell.get_data('column')

        # get toggled iter
        iter = model.get_iter_from_string(path_str)
        toggle_item = model.get_value(iter, column)

        print "toggle_item = ", toggle_item

        # do something with the value
        toggle_item = not toggle_item

        # set new value
        print "calling model.set(iter, column=", column, ", toggle_item=", toggle_item, ")"
        model.set(iter, column, toggle_item)



    def __init__(self, trodes, ok_callback, rectify_selected=None, hilbert_selected=None):
        gtk.Dialog.__init__(self)

        #print "Dialog_FilterElectrodes.__init__(", trodes, ok_callback, rectify_selected, hilbert_selected, ")"

        self.set_title("Filter electrodes")


        #if selected is None: self.selected = EOI()
        #else: self.selected = selected

        COLUMN_GRDNAME=0
        COLUMN_GRDNUM=1

        # rectify dialog
        COLUMN_RECTIFY=2
        # hilbert dialog
        COLUMN_HILBERT=3

        model = gtk.ListStore(gobject.TYPE_STRING,
                              gobject.TYPE_UINT,
                              gobject.TYPE_BOOLEAN,
                              gobject.TYPE_BOOLEAN)

        # a dictionary from [grdName][grdNum] keys to iters
        iterMap = {}
        print "hilbert_selected=",hilbert_selected
        for (grdName, grdNum) in trodes:
            toRectify = rectify_selected[(grdName, grdNum)]
            toHilbert = hilbert_selected[(grdName, grdNum)]
            #print "toRectify for ", (grdName, grdNum), " is ", toRectify
            #print "toHilbert for ", (grdName, grdNum), " is ", toHilbert
            iter = model.append()    
            model.set(iter,
                      COLUMN_GRDNAME, grdName,
                      COLUMN_GRDNUM,  grdNum,
                      COLUMN_RECTIFY, toRectify,
                      COLUMN_HILBERT, toHilbert)
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

        renderer = gtk.CellRendererToggle()
        renderer.set_data("column", COLUMN_RECTIFY) # mccXXX: why am I doing this
        renderer.connect("toggled", self.on_rectify_toggled, model)
        #renderer.set_property("active", True)
        column = gtk.TreeViewColumn('Rectify', renderer, active=COLUMN_RECTIFY) # XXX: why did I do that ?
        #column = gtk.TreeViewColumn('Rectify', renderer)
        column.set_fixed_width(50)
        column.set_clickable(True)
        treeview.append_column(column)
                                    
        renderer = gtk.CellRendererToggle()
        renderer.set_data("column", COLUMN_HILBERT) # mccXXX: why am I doing this
        renderer.connect("toggled", self.on_rectify_toggled, model)
        column = gtk.TreeViewColumn('Hilbert', renderer, active=COLUMN_HILBERT) # XXX: why did I do that ?
        column.set_fixed_width(50)
        column.set_clickable(True)
        treeview.append_column(column)
                                    


        treeview.get_selection().set_mode(gtk.SELECTION_NONE)

        # select all the electrodes in the initially selected list
        #treeViewSel = treeview.get_selection()
        #for (grdName, grdNum) in self.selected:
        #    try: iter = iterMap[grdName][grdNum]
        #    except KeyError: continue
        #    treeViewSel.select_iter(iter)

        # when you click ok, call this function for each selected item
        def return_foreach(model, path, iter, selected):
            selected.append(
                (model.get_value(iter, COLUMN_GRDNAME),
                 model.get_value(iter, COLUMN_GRDNUM),                 
                 model.get_value(iter, COLUMN_RECTIFY)))

        def getiter_foreach(model, path, iter, selected):
            selected.append(iter)

        def ok_clicked(event):
            filters = {}

            for row in model:
                print "ok_clicked(): row is ", row
                print "ok_clicked(): row[COLUMN_GRDNAME], row[COLUMN_RECTIFY] is ", row[COLUMN_GRDNAME], row[COLUMN_RECTIFY]

                filters[(row[COLUMN_GRDNAME], row[COLUMN_GRDNUM])] = {'rectify': row[COLUMN_RECTIFY], 'hilbert': row[COLUMN_HILBERT]}
                
            
            #treeview.get_selection().selected_foreach(return_foreach, trodes)
            #print 'len trodes', len(trodes)
            #print "trodes=",trodes

            #self.selected.set_electrodes(trodes)
            #start, end = self.buffer.get_bounds()
            #self.selected.description = self.buffer.get_text(start, end)
            ok_callback(filters)

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
            
        label = gtk.Label('Select filter(s) for active electrodes')
        label.show()
        self.vbox.pack_start(label, False, False)
    
        sw = gtk.ScrolledWindow()
        sw.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        sw.set_policy(gtk.POLICY_NEVER,
                      gtk.POLICY_AUTOMATIC)

        sw.add(treeview)
        self.vbox.pack_start(sw)

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

