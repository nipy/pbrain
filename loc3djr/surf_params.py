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

from connect_filter import ConnectFilter
from decimate_filter import DecimateFilter

from color_seq import colorSeq

class SurfParams(Viewer):
    """
    CLASS: SurfParams
    DESCR:

      Public attrs:
    
      color       # a normed rgb
      intensity   # intensity to segment on
      label       # name of segment
      useConnect  # boolean, whether to use ConnectFilter
      useDecimate # boolean, whether to use DecimateFilter
      connect     # a ConnectFilter or None
      deci        # a DecimateFilter or None
      imageData   # default None
    """

    label, color  = colorSeq[0]
    intensity     = 3000

    useConnect    = True
    useDecimate   = False

    def __init__(self, renderer, interactor):

        self.connect = ConnectFilter()
        self.deci = DecimateFilter()
        self.marchingCubes = vtk.vtkMarchingCubes()

        self.prog = ProgressBarDialog(
            title='Rendering surface %s' % self.label,
            parent=None,
            msg='Marching cubes ....',
            size=(300,40),
                                 )
        def start(o, event):
            self.prog.show()
            while gtk.events_pending(): gtk.main_iteration()


        def progress(o, event):
            val = o.GetProgress()
            self.prog.bar.set_fraction(val)            
            while gtk.events_pending(): gtk.main_iteration()
            
        def end(o, event):
            self.prog.hide()
            while gtk.events_pending(): gtk.main_iteration()

        self.marchingCubes.AddObserver('StartEvent', start)
        self.marchingCubes.AddObserver('ProgressEvent', progress)
        self.marchingCubes.AddObserver('EndEvent', end)
        self.renderer = renderer
        self.interactor = interactor
        self.isoActor = None
        
        self.update_pipeline()

    def update_pipeline(self):

        if self.isoActor is not None:
            self.renderer.RemoveActor(self.isoActor)

        
        
        pipe = self.marchingCubes


        if self.useConnect:
            self.connect.SetInput( pipe.GetOutput())
            pipe = self.connect

        if self.useDecimate:
            self.deci.SetInput( pipe.GetOutput())
            pipe = self.deci

        if 0:
            plane = vtk.vtkPlane()
            clipper = vtk.vtkClipPolyData()
            polyData = pipe.GetOutput()

            clipper.SetInput(polyData)
            clipper.SetClipFunction(plane)
            clipper.InsideOutOff()
            pipe = clipper

            def callback(pw, event):
                pw.GetPlane(plane)
                self.interactor.Render()
            self.planeWidget = vtk.vtkImplicitPlaneWidget()
            self.planeWidget.SetInteractor(self.interactor)
            self.planeWidget.On()
            self.planeWidget.SetPlaceFactor(1.0)
            self.planeWidget.SetInput(polyData)
            self.planeWidget.PlaceWidget()
            self.planeWidget.AddObserver("InteractionEvent", callback)
        
        
        self.isoMapper = vtk.vtkPolyDataMapper()
        self.isoMapper.SetInput(pipe.GetOutput())
        self.isoMapper.ScalarVisibilityOff()

        self.isoActor = vtk.vtkActor()
        self.isoActor.SetMapper(self.isoMapper)
        self.renderer.AddActor(self.isoActor)
        self.update_properties()

    def set_image_data(self, imageData):
        print "SurfParams.set_image_data(", imageData,")"
        self.marchingCubes.SetInput(imageData)
        x1,x2,y1,y2,z1,z2 = imageData.GetExtent()
        sx, sy, sz = imageData.GetSpacing()
        if 0:
            self.planeWidget.PlaceWidget((x1*sx, x2*sx, y1*sy, y2*sy, z1*sz, z2*sz))

    def update_properties(self):
        self.marchingCubes.SetValue(0, self.intensity)
        self.isoActor.GetProperty().SetColor(self.color)

        if self.useConnect:  self.connect.update()
        if self.useDecimate: self.deci.update()

    def update_viewer(self, event, *args):
        if event=='set image data':
            imageData = args[0]
            self.set_image_data(imageData)       


    def __del__(self):
        if self.isoActor is not None:
            self.renderer.RemoveActor(self.isoActor)
