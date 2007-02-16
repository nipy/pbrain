from __future__ import division
import sys, os
import vtk

import gtk
from gtk import gdk

from pbrainlib.gtkutils import error_msg, simple_msg, ButtonAltLabel, \
     str2posint_or_err, str2posnum_or_err, ProgressBarDialog, make_option_menu
from matplotlib.cbook import Bunch

from events import EventHandler, UndoRegistry, Viewer
from markers import Marker
from shared import shared


class ConnectFilter(vtk.vtkPolyDataConnectivityFilter):
    """
    CLASS: ConnectFilter
    DESCR: Public attrs

      mode : the extraction mode as int
    """
    mode2num = {
        'Point Seeded Regions' : 1,
        'Cell Seeded Regions'  : 2,
        'Specified Regions'    : 3,
        'Largest Region'       : 4,
        'All Regions'          : 5,
        'Closest Point Region' : 6,
        }
    num2mode = dict([ (v,k) for k,v in mode2num.items()])
    mode = 5

    def __init__(self):
        prog = ProgressBarDialog(
            title='Rendering surface',
            parent=None,
            msg='Computing connectivity ....',
            size=(300,40),
            )

        def start(o, event):
            prog.show()
            while gtk.events_pending(): gtk.main_iteration()

        def progress(o, event):
            val = o.GetProgress()
            prog.bar.set_fraction(val)            
            while gtk.events_pending(): gtk.main_iteration()
            
        def end(o, event):
            prog.hide()
            while gtk.events_pending(): gtk.main_iteration()

        self.AddObserver('StartEvent', start)
        self.AddObserver('ProgressEvent', progress)
        self.AddObserver('EndEvent', end)

    def update(self):
        self.SetExtractionMode(self.mode)
    
