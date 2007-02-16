"""
This code is based on GtkVTKRenderWindow written by Prabhu
Ramachandran that ships with VTK.

The extensions here allow the use of gtkglext rather than gtkgl and
pygtk-2 rather than pygtk-0.  It requires pygtk-2.0.0 or later.

John Hunter jdhunter@ace.bsd.uchicago.edu
"""


import time, math, sys
import gtk
import gtk.gtkgl
from gtk import gdk
import vtk

        
class GtkGLExtVTKRenderWindowBase(gtk.gtkgl.DrawingArea):
    """
    CLASS: GtkGLExtVTKRenderWindowBase
    DESCR: This is used by the image_reader Preview window and nowhere else.
    The GtkGLExtVTKRenderWindowInteractor is used in the MarkerWindowInteractor and SurfRenderWindow
    """
    def __init__(self, *args):
        gtk.gtkgl.DrawingArea.__init__(self)
        self.set_double_buffered(False)

        self._RenderWindow = vtk.vtkRenderWindow()
        # private attributes
        self.__Created = 0

        # used by the LOD actors
        self._DesiredUpdateRate = 15
        #self._DesiredUpdateRate = 0.0001
        self._StillUpdateRate = 0.0001

        self.ConnectSignals()
        
        # need this to be able to handle key_press events.
        self.set_flags(gtk.CAN_FOCUS)
        # default size
        self.set_size_request(300, 300)

    def ConnectSignals(self):
        self.connect("realize", self.OnRealize)
        self.connect("expose_event", self.OnExpose)
        self.connect("configure_event", self.OnConfigure)
        self.connect("button_press_event", self.OnButtonDown)
        self.connect("button_release_event", self.OnButtonUp)
        self.connect("motion_notify_event", self.OnMouseMove)
        self.connect("enter_notify_event", self.OnEnter)
        self.connect("leave_notify_event", self.OnLeave)
        self.connect("key_press_event", self.OnKeyPress)
        self.connect("delete_event", self.OnDestroy)
        self.add_events(gdk.EXPOSURE_MASK|
                        gdk.BUTTON_PRESS_MASK |
                        gdk.BUTTON_RELEASE_MASK |
                        gdk.KEY_PRESS_MASK |
                        gdk.POINTER_MOTION_MASK |
                        gdk.POINTER_MOTION_HINT_MASK |
                        gdk.ENTER_NOTIFY_MASK |
                        gdk.LEAVE_NOTIFY_MASK)
        
    def GetRenderWindow(self):
        return self._RenderWindow

    def GetRenderer(self):
        self._RenderWindow.GetRenderers().InitTraversal()
        return self._RenderWindow.GetRenderers().GetNextItem()

    def SetDesiredUpdateRate(self, rate):
        """Mirrors the method with the same name in
        vtkRenderWindowInteractor."""
        self._DesiredUpdateRate = rate

    def GetDesiredUpdateRate(self):
        """Mirrors the method with the same name in
        vtkRenderWindowInteractor."""
        return self._DesiredUpdateRate 
        
    def SetStillUpdateRate(self, rate):
        """Mirrors the method with the same name in
        vtkRenderWindowInteractor."""
        self._StillUpdateRate = rate

    def GetStillUpdateRate(self):
        """Mirrors the method with the same name in
        vtkRenderWindowInteractor."""
        return self._StillUpdateRate

    def Render(self):
        #print 'base render'
        if self.__Created:
            #print 'base created'
            self._RenderWindow.Render()

    def OnRealize(self, *args):
        #print 'OnRealize'
        if self.__Created == 0:
            # you can't get the xid without the window being realized.
            self.realize()
            if sys.platform=='win32':
                win_id = str(self.widget.window.handle)
            else:
                win_id = str(self.widget.window.xid)
            self._RenderWindow.SetWindowInfo(win_id)
            self.__Created = 1
            #self._InitGoodies()
        return True

    def Created(self):
        return self.__Created
    
    def OnConfigure(self, widget, event):
        #print 'OnConfigure'
        self.widget=widget
        self._RenderWindow.SetSize(event.width, event.height)
        self.Render()
        return True

    def OnExpose(self, *args):
        #if self._CurrentRenderer:
        #    #print 'on expose rendering'
        self.Render()
        return True

    def OnDestroy(self, *args):
        self.hide()
        del self._RenderWindow
        self.destroy()
        return True

    def OnButtonDown(self, wid, event):
        """Mouse button pressed."""
        #print 'OnButtonDown base'
        self._RenderWindow.SetDesiredUpdateRate(self._DesiredUpdateRate)
        return True
    
    def OnButtonUp(self, wid, event):
        """Mouse button released."""
        #print 'OnButtonUp base'
        self._RenderWindow.SetDesiredUpdateRate(self._StillUpdateRate)
        return True

    def OnMouseMove(self, wid, event):
        """Mouse has moved."""
        return True

    def OnEnter(self, wid, event):
        """Entering the vtkRenderWindow."""
        return True

    def OnLeave(self, wid, event):
        """Leaving the vtkRenderWindow."""
        return True
    
    def OnKeyPress(self, wid, event):
        """Key pressed."""
        return True

    def OnKeyRelease(self, wid, event):
        "Key released."
        return True


class GtkGLExtVTKRenderWindow(GtkGLExtVTKRenderWindowBase):
    """ An example
    of a fully functional GtkGLExtVTKRenderWindow that is based on the
    vtkRenderWidget.py provided with the VTK sources."""
    def __init__(self, *args):

        GtkGLExtVTKRenderWindowBase.__init__(self)


        self._CurrentRenderer = None
        self._CurrentCamera = None
        self._CurrentZoom = 1.0
        self._CurrentLight = None

        self._ViewportCenterX = 0
        self._ViewportCenterY = 0
        
        self._Picker = vtk.vtkCellPicker()
        self._PickedAssembly = None
        self._PickedProperty = vtk.vtkProperty()
        self._PickedProperty.SetColor(1, 0, 0)
        self._PrePickedProperty = None
        
        self._OldFocus = None

        # these record the previous mouse position
        self._LastX = 0
        self._LastY = 0

    def OnButtonDown(self, wid, event):
        #print 'derived button down'
        self._RenderWindow.SetDesiredUpdateRate(self._DesiredUpdateRate)
        return self.StartMotion(wid, event)
        return True

    def OnButtonUp(self, wid, event):
        #print 'derived  button up'
        self._RenderWindow.SetDesiredUpdateRate(self._StillUpdateRate)
        return self.EndMotion(wid, event)
        return True

    def OnMouseMove(self, wid, event=None):
        if ((event.state & gdk.BUTTON1_MASK) == gdk.BUTTON1_MASK):
            if ((event.state & gdk.SHIFT_MASK) == gdk.SHIFT_MASK):
                m = self.get_pointer()
                self.Pan(m[0], m[1])
            else:
                m = self.get_pointer()
                self.Rotate(m[0], m[1])
        elif ((event.state & gdk.BUTTON2_MASK) == gdk.BUTTON2_MASK):
            m = self.get_pointer()
            self.Pan(m[0], m[1])
        elif ((event.state & gdk.BUTTON3_MASK) == gdk.BUTTON3_MASK):
            m = self.get_pointer()
            self.Zoom(m[0], m[1])
        else:
            #print 'returning false'
            return False

        return True

    def OnEnter(self, wid, event=None):
        # a render hack because grab_focus blanks the renderwin
        self.grab_focus()
        w = self.get_pointer()
        self.UpdateRenderer(w[0], w[1])
        return True
    
    def OnKeyPress(self, wid, event=None):

        if (event.keyval == gdk.keyval_from_name("q") or
            event.keyval == gdk.keyval_from_name("Q")):
            gtk.main_quit()
            
        
        if (event.keyval == gdk.keyval_from_name('r') or
            event.keyval == gdk.keyval_from_name('R')):
            self.Reset()
            return True
        elif (event.keyval == gdk.keyval_from_name('w') or
              event.keyval == gdk.keyval_from_name('W')):
            self.Wireframe()
            return True
        elif (event.keyval == gdk.keyval_from_name('s') or
              event.keyval == gdk.keyval_from_name('S')):
            self.Surface()
            return True
        elif (event.keyval == gdk.keyval_from_name('p') or
              event.keyval == gdk.keyval_from_name('P')):
            m = self.get_pointer()
            self.PickActor(m[0], m[1])
            return True
        else:
            return False

    def GetZoomFactor(self):
        return self._CurrentZoom

    def SetZoomFactor(self, zf):
        self._CurrentZoom = zf

    def GetPicker(self):
        return self._Picker

    def Render(self):
        #print 'derived render'
        if (self._CurrentLight):
            #print 'Render current light'
            light = self._CurrentLight
            light.SetPosition(self._CurrentCamera.GetPosition())
            light.SetFocalPoint(self._CurrentCamera.GetFocalPoint())

        GtkGLExtVTKRenderWindowBase.Render(self)



    def UpdateRenderer(self,x,y):
        """
        UpdateRenderer will identify the renderer under the mouse and set
        up _CurrentRenderer, _CurrentCamera, and _CurrentLight.
        """

        windowX,windowY  = self.widget.window.get_size()

        renderers = self._RenderWindow.GetRenderers()
        numRenderers = renderers.GetNumberOfItems()

        self._CurrentRenderer = None
        renderers.InitTraversal()
        for i in range(0,numRenderers):
            renderer = renderers.GetNextItem()
            vx,vy = (0,0)
            if (windowX > 1):
                vx = float(x)/(windowX-1)
            if (windowY > 1):
                vy = (windowY-float(y)-1)/(windowY-1)
            (vpxmin,vpymin,vpxmax,vpymax) = renderer.GetViewport()
            
            if (vx >= vpxmin and vx <= vpxmax and
                vy >= vpymin and vy <= vpymax):
                self._CurrentRenderer = renderer
                self._ViewportCenterX = float(windowX)*(vpxmax-vpxmin)/2.0\
                                        +vpxmin
                self._ViewportCenterY = float(windowY)*(vpymax-vpymin)/2.0\
                                        +vpymin
                self._CurrentCamera = self._CurrentRenderer.GetActiveCamera()
                lights = self._CurrentRenderer.GetLights()
                lights.InitTraversal()
                self._CurrentLight = lights.GetNextItem()
                break

        self._LastX = x
        self._LastY = y

    def GetCurrentRenderer(self):
        if self._CurrentRenderer is None:
            renderers = self._RenderWindow.GetRenderers()
            numRenderers = renderers.GetNumberOfItems()

            renderers.InitTraversal()
            for i in range(0,numRenderers):
                renderer = renderers.GetNextItem()
                break
            self._CurrentRenderer = renderer
        return self._CurrentRenderer

    def GetCurrentCamera(self):
        if self._CurrentCamera is None:
            renderer = self.GetCurrentRenderer()
            self._CurrentCamera = renderer.GetActiveCamera()
        return self._CurrentCamera

    def StartMotion(self, wid, event=None):
        x = event.x
        y = event.y
        self.UpdateRenderer(x,y)
        return True

    def EndMotion(self, wid, event=None):
        if self._CurrentRenderer:
            #print 'endmotion rendering'
            self.Render()
        return True

    def Rotate(self,x,y):
        if self._CurrentRenderer:
            
            self._CurrentCamera.Azimuth(self._LastX - x)
            self._CurrentCamera.Elevation(y - self._LastY)
            self._CurrentCamera.OrthogonalizeViewUp()
            
            self._LastX = x
            self._LastY = y
            
            self._CurrentRenderer.ResetCameraClippingRange()
            self.Render()

    def Pan(self,x,y):
        if self._CurrentRenderer:
            
            renderer = self._CurrentRenderer
            camera = self._CurrentCamera
            (pPoint0,pPoint1,pPoint2) = camera.GetPosition()
            (fPoint0,fPoint1,fPoint2) = camera.GetFocalPoint()

            if (camera.GetParallelProjection()):
                renderer.SetWorldPoint(fPoint0,fPoint1,fPoint2,1.0)
                renderer.WorldToDisplay()
                fx,fy,fz = renderer.GetDisplayPoint()
                renderer.SetDisplayPoint(fx-x+self._LastX,
                                         fy+y-self._LastY,
                                         fz)
                renderer.DisplayToWorld()
                fx,fy,fz,fw = renderer.GetWorldPoint()
                camera.SetFocalPoint(fx,fy,fz)

                renderer.SetWorldPoint(pPoint0,pPoint1,pPoint2,1.0)
                renderer.WorldToDisplay()
                fx,fy,fz = renderer.GetDisplayPoint()
                renderer.SetDisplayPoint(fx-x+self._LastX,
                                         fy+y-self._LastY,
                                         fz)
                renderer.DisplayToWorld()
                fx,fy,fz,fw = renderer.GetWorldPoint()
                camera.SetPosition(fx,fy,fz)
                
            else:
                (fPoint0,fPoint1,fPoint2) = camera.GetFocalPoint()
                # Specify a point location in world coordinates
                renderer.SetWorldPoint(fPoint0,fPoint1,fPoint2,1.0)
                renderer.WorldToDisplay()
                # Convert world point coordinates to display coordinates
                dPoint = renderer.GetDisplayPoint()
                focalDepth = dPoint[2]
                
                aPoint0 = self._ViewportCenterX + (x - self._LastX)
                aPoint1 = self._ViewportCenterY - (y - self._LastY)
                
                renderer.SetDisplayPoint(aPoint0,aPoint1,focalDepth)
                renderer.DisplayToWorld()
                
                (rPoint0,rPoint1,rPoint2,rPoint3) = renderer.GetWorldPoint()
                if (rPoint3 != 0.0):
                    rPoint0 = rPoint0/rPoint3
                    rPoint1 = rPoint1/rPoint3
                    rPoint2 = rPoint2/rPoint3

                camera.SetFocalPoint((fPoint0 - rPoint0) + fPoint0, 
                                     (fPoint1 - rPoint1) + fPoint1,
                                     (fPoint2 - rPoint2) + fPoint2) 
                
                camera.SetPosition((fPoint0 - rPoint0) + pPoint0, 
                                   (fPoint1 - rPoint1) + pPoint1,
                                   (fPoint2 - rPoint2) + pPoint2)

            self._LastX = x
            self._LastY = y

            self.Render()

    def Zoom(self,x,y):
        if self._CurrentRenderer:

            renderer = self._CurrentRenderer
            camera = self._CurrentCamera

            zoomFactor = math.pow(1.02,(0.5*(self._LastY - y)))
            self._CurrentZoom = self._CurrentZoom * zoomFactor

            if camera.GetParallelProjection():
                parallelScale = camera.GetParallelScale()/zoomFactor
                camera.SetParallelScale(parallelScale)
            else:
                camera.Dolly(zoomFactor)
                renderer.ResetCameraClippingRange()

            self._LastX = x
            self._LastY = y

            self.Render()

    def Reset(self):
        if self._CurrentRenderer:
            self._CurrentRenderer.ResetCamera()
            
        self.Render()

    def Wireframe(self):
        actors = self._CurrentRenderer.GetActors()
        numActors = actors.GetNumberOfItems()
        actors.InitTraversal()
        for i in range(0,numActors):
            actor = actors.GetNextItem()
            actor.GetProperty().SetRepresentationToWireframe()

        self.Render()
        
    def Surface(self):
        actors = self._CurrentRenderer.GetActors()
        numActors = actors.GetNumberOfItems()
        actors.InitTraversal()
        for i in range(0,numActors):
            actor = actors.GetNextItem()
            actor.GetProperty().SetRepresentationToSurface()

        self.Render()

    def PickActor(self,x,y):
        if self._CurrentRenderer:

            renderer = self._CurrentRenderer
            picker = self._Picker

            windowX,windowY  = self.widget.window.get_size()
            picker.Pick(x,(windowY - y - 1),0.0,renderer)
            assembly = picker.GetAssembly()

            if (self._PickedAssembly != None and
                self._PrePickedProperty != None):
                self._PickedAssembly.SetProperty(self._PrePickedProperty)
                # release hold of the property
                self._PrePickedProperty.UnRegister(self._PrePickedProperty)
                self._PrePickedProperty = None

            if (assembly != None):
                self._PickedAssembly = assembly
                self._PrePickedProperty = self._PickedAssembly.GetProperty()
                # hold onto the property
                self._PrePickedProperty.Register(self._PrePickedProperty)
                self._PickedAssembly.SetProperty(self._PickedProperty)

            self.Render()


def main():
    # The main window
    window = gtk.Window()
    window.set_title("A GtkGLExtVTKRenderWindow Demo!")
    window.connect("destroy", gtk.main_quit)
    window.connect("delete_event", gtk.main_quit)
    window.set_border_width(10)

    vtkda = GtkGLExtVTKRenderWindow()
    vtkda.show()

    
    vbox = gtk.VBox(spacing=3)
    vbox.show()
    vbox.pack_start(vtkda)

    button = gtk.Button('My Button')
    button.show()
    vbox.pack_start(button)
    window.add(vbox)

    
    
    window.set_size_request(400, 400)

    # The VTK stuff.
    cone = vtk.vtkConeSource()
    cone.SetResolution(80)
    coneMapper = vtk.vtkPolyDataMapper()
    coneMapper.SetInput(cone.GetOutput())
    #coneActor = vtk.vtkLODActor()
    coneActor = vtk.vtkActor()
    coneActor.SetMapper(coneMapper)    
    coneActor.GetProperty().SetColor(0.5, 0.5, 1.0)
    ren = vtk.vtkRenderer()
    vtkda.GetRenderWindow().AddRenderer(ren)
    ren.AddActor(coneActor)


    # show the main window and start event processing.
    window.show()
    gtk.main()


if __name__ == "__main__":
    main()
