from __future__ import division
import sys, os
import vtk

import gtk
from gtk import gdk
from GtkGLExtVTKRenderWindowInteractor import GtkGLExtVTKRenderWindowInteractor

from pbrainlib.gtkutils import error_msg, simple_msg, ButtonAltLabel, \
     str2posint_or_err, str2posnum_or_err, ProgressBarDialog, make_option_menu
from matplotlib.cbook import Bunch

from events import EventHandler, UndoRegistry, Viewer
from markers import Marker
from shared import shared


class SurfRenderWindow(GtkGLExtVTKRenderWindowInteractor, Viewer):
    """
    CLASS: SurfRenderWindow
    DESCR: Upper right frame in loc3djr window - for the markers and later the surface renderings
    """

    def __init__(self, imageData=None):
        GtkGLExtVTKRenderWindowInteractor.__init__(self)
        EventHandler().attach(self)

        self.Initialize()
        self.Start()
        self.renderOn = True
        
        self.renderer = vtk.vtkRenderer()
        self.renWin = self.GetRenderWindow()
        self.renWin.AddRenderer(self.renderer)
        self.interactor = self.renWin.GetInteractor()
        self.renderer.SetBackground(0,0,0)
        self.textActors = {}
        
    def set_image_data(self, imageData):
        self.imageData = imageData
        if imageData is None: return
        center = imageData.GetCenter()
        spacing = imageData.GetSpacing()
        bounds = imageData.GetBounds()
        pos = center[0], center[1], center[2] - max(bounds)*2
        fpu = center, pos, (0,-1,0)
        self.set_camera(fpu)

    def get_camera_fpu(self):
        camera = self.renderer.GetActiveCamera()
        return (camera.GetFocalPoint(),
                camera.GetPosition(),
                camera.GetViewUp())

    def set_camera(self, fpu):
        camera = self.renderer.GetActiveCamera()
        focal, position, up = fpu
        camera.SetFocalPoint(focal)
        camera.SetPosition(position)
        camera.SetViewUp(up)
        self.renderer.ResetCameraClippingRange()
        self.Render()
                        
    def Render(self):
        if self.renderOn:
            GtkGLExtVTKRenderWindowInteractor.Render(self)
                
    def update_viewer(self, event, *args):
        if event=='render off':
            self.renderOn = 0
        elif event=='render on':
            self.renderOn = 1
            self.Render()
        elif event=='set image data':
            imageData = args[0]
            self.set_image_data(imageData)
            self.Render()
        elif event=='add marker':
            marker = args[0]
            self.add_marker(marker)
        elif event=='remove marker':
            marker = args[0]
            self.remove_marker(marker)
        elif event=='labels on':
            actors = self.textActors.values()
            for actor in actors:
                actor.VisibilityOn()
        elif event=='labels off':
            actors = self.textActors.values()
            for actor in actors:
                actor.VisibilityOff()

        self.Render()
    def add_marker(self, marker):

        self.renderer.AddActor(marker)

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
        textActor.SetCamera(self.renderer.GetActiveCamera())
        textActor.GetProperty().SetColor(marker.get_label_color())
        if EventHandler().get_labels_on():
            textActor.VisibilityOn()
        else:
            textActor.VisibilityOff()


        self.textActors[marker] = textActor
        self.renderer.AddActor(textActor)

    def remove_marker(self, marker):
        self.renderer.RemoveActor(marker)
        self.renderer.RemoveActor(self.textActors[marker])
        del self.textActors[marker]
