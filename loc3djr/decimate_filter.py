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

# vtkDecimate is patented and no longer in VTK5. we will try vtkDecimatePro (argh)
# class DecimateFilter(vtk.vtkDecimate):
class DecimateFilter(vtk.vtkDecimatePro):
    """
    CLASS: DecimateFilter
    DESCR:
        
    Public attrs:
      targetReduction
      aspectRatio    
      initialError   
      errorIncrement 
      maxIterations  
      initialAngle   
    """

    fmts = {
      'targetReduction' : '%1.2f',
      'aspectRatio'     : '%1.1f',
      'initialError'    : '%1.5f',
      'errorIncrement'  : '%1.4f',      
      'maxIterations'   : '%d',
      'initialAngle'    : '%1.1f',
      }


    labels = {
        'targetReduction' : 'Target reduction',
        'aspectRatio'     : 'Aspect ratio',
        'initialError'    : 'Initial error',
        'errorIncrement'  : 'Error increment',
        'maxIterations'   : 'Maximum iterations',
        'initialAngle'    :'Initial angle',
        }

    converters = {
      'targetReduction' : str2posnum_or_err,
      'aspectRatio'     : str2posnum_or_err,
      'initialError'    : str2posnum_or_err,
      'errorIncrement'  : str2posnum_or_err,      
      'maxIterations'   : str2posint_or_err,
      'initialAngle'    : str2posnum_or_err,
        
        }
    targetReduction = 0.8
    aspectRatio     = 20 
    initialError    = 0.0005
    errorIncrement  = 0.001
    maxIterations   = 6
    initialAngle    = 30

    def __init__(self):
        prog = ProgressBarDialog(
            title='Rendering surface',
            parent=None,
            msg='Decimating data....',
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
        self.SetTargetReduction(self.targetReduction)
        self.SetAspectRatio(self.aspectRatio)
        self.SetInitialError(self.initialError)
        self.SetErrorIncrement(self.errorIncrement)
        self.SetMaximumIterations(self.maxIterations)
        self.SetInitialFeatureAngle(self.initialAngle)
                
