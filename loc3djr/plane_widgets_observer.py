from gtk import gdk
import gtk
import vtk
import time
from scipy import array
from markers import Marker, RingActor
from events import EventHandler, UndoRegistry, Viewer


from marker_window_interactor import MarkerWindowInteractor

INTERACT_CURSOR, MOVE_CURSOR, COLOR_CURSOR, SELECT_CURSOR, DELETE_CURSOR, LABEL_CURSOR = gtk.gdk.ARROW, gtk.gdk.HAND2, gtk.gdk.SPRAYCAN, gtk.gdk.TCROSS, gtk.gdk.X_CURSOR, gtk.gdk.PENCIL


class PlaneWidgetObserver(MarkerWindowInteractor):
    """
    CLASS: PlaneWidgetObserver
    DESCR: Handles interactions with PlaneWidgets
    """
    def __init__(self, planeWidget, owner, orientation, imageData=None):
        print "PlaneWidgetObserver.__init__(): orientation=",orientation
        MarkerWindowInteractor.__init__(self)
        self.interactButtons = (1,2,3)
        self.pw = planeWidget
        self.owner = owner
        self.orientation = orientation
        self.observer = vtk.vtkImagePlaneWidget()

        self.camera = self.renderer.GetActiveCamera()

        self.ringActors = vtk.vtkActorCollection()
        self.defaultRingLine = 1
        self.textActors = {}
        self.hasData = 0

        self.set_image_data(imageData)
        self.lastTime = 0
        self.set_mouse1_to_move()
        
    def set_image_data(self, imageData):
        if imageData is None: return 
        self.imageData = imageData
        if not self.hasData:
            print "PlaneWidgetObserver(", self.orientation,").. AddObserver(self.interaction_event)"
            foo = self.pw.AddObserver('InteractionEvent', self.interaction_event)
            print "PlaneWidgetObserver.set_image_data(): AddObserver call returns ", foo
            self.connect("scroll_event", self.scroll_widget_slice)
            self.hasData = 1

        # make cursor invisible
        self.observer.GetCursorProperty().SetOpacity(0.0)
        
        self.observer.TextureInterpolateOn()            
        self.observer.TextureInterpolateOn()
        self.observer.SetKeyPressActivationValue(
            self.pw.GetKeyPressActivationValue())
        self.observer.GetPlaneProperty().SetColor(0,0,0)
        self.observer.SetResliceInterpolate(
            self.pw.GetResliceInterpolate())
        self.observer.SetLookupTable(self.pw.GetLookupTable())        
        self.observer.DisplayTextOn()
        #self.observer.GetMarginProperty().EdgeVisibilityOff()  # turn off edges??
        self.observer.SetInput(imageData)
        self.observer.SetInteractor(self.interactor)
        self.observer.On()
        self.observer.InteractionOff()
        self.update_plane()
        if self.orientation==0: up = (0,0,1)
        elif self.orientation==1: up = (0,0,1)
        elif self.orientation==2: up = (0,-1,0)
        else:
            raise ValueError, 'orientation must be in 0,1,2'

        center = self.observer.GetCenter()
        normal = self.pw.GetNormal()
        spacing =imageData.GetSpacing()
        bounds = imageData.GetBounds()

        offset = max(bounds)
        pos = (center[0] + normal[0]*offset,
               center[1] - normal[1]*offset,
               center[2] - normal[2]*offset)
        
        self.set_camera((center, pos, up))
        self.resetCamera = (center, pos, up)

        #self.sliceIncrement = spacing[self.orientation]
        self.sliceIncrement = 0.1

    def mouse1_mode_change(self, event):
        try: self.moveEvent
        except AttributeError: pass
        else: self.observer.RemoveObserver(self.moveEvent)

        try: self.startEvent
        except AttributeError: pass
        else: self.observer.RemoveObserver(self.startEvent)

        try: self.endEvent
        except AttributeError: pass
        else: self.observer.RemoveObserver(self.endEvent)

        
    def set_mouse1_to_move(self):


        self.markerAtPoint = None
        self.pressed1 = 0

        def move(*args):
            if self.markerAtPoint is None: return 
            xyz = self.get_cursor_position_world()
            EventHandler().notify(
                'move marker', self.markerAtPoint, xyz)

        def button_down(*args):
            self.markerAtPoint = self.get_marker_at_point()
            if self.markerAtPoint is not None:
                self.lastPos = self.markerAtPoint.get_center()

        def button_up(*args):
            if self.markerAtPoint is None: return
            thisPos = self.markerAtPoint.get_center()

            def undo_move(marker):
                marker.set_center(self.lastPos)
                ra = self.get_actor_for_marker(marker)
                ra.update()
                self.Render()

            if thisPos != self.lastPos:
                UndoRegistry().push_command(undo_move, self.markerAtPoint)
            self.markerAtPoint = None
            

        self.pressHooks[1] = button_down
        self.releaseHooks[1] = button_up

        #self.startEvent = self.observer.AddObserver(
        #    'StartInteractionEvent', start_iact)
        #self.endEvent = self.observer.AddObserver(
        #    'EndInteractionEvent', end_iact)
        self.moveEvent = self.observer.AddObserver(
            'InteractionEvent', move)

        #self.set_select_mode()

        cursor = gtk.gdk.Cursor (MOVE_CURSOR)
        if self.window is not None:
            self.window.set_cursor (cursor)

    def set_select_mode(self):
        return

        self.defaultRingLine = 3
        actors = self.get_ring_actors_as_list()
        for actor in actors:
            actor.set_line_width(self.defaultRingLine)
            actor.update()
        self.Render()

    def set_interact_mode(self):
        

        self.interactButtons = (1,2,3)
        self.set_mouse1_to_move()
        return
    
        self.defaultRingLine = 1
        actors = self.get_ring_actors_as_list()
        for actor in actors:
            actor.set_line_width(self.defaultRingLine)
            actor.update()
        self.Render()
        self.set_mouse1_to_move()


    def get_marker_at_point(self):
        xyz = self.get_cursor_position_world()
        for actor in self.get_ring_actors_as_list():
            if not actor.GetVisibility(): continue
            marker = actor.get_marker()
            if marker is None: return None
            if marker.contains(xyz): return marker
        return None

    def get_plane_points(self):
        return self.pw.GetOrigin(), self.pw.GetPoint1(), self.pw.GetPoint2()

    def set_plane_points(self, pnts):
        o, p1, p2 = pnts
        self.pw.SetOrigin(o)
        self.pw.SetPoint1(p1)
        self.pw.SetPoint2(p2)
        self.pw.UpdatePlacement()
        self.update_plane()

    def OnButtonDown(self, wid, event):
        if not self.hasData: return 
        self.lastPnts = self.get_plane_points()


        if event.button==1:
            self.observer.InteractionOn()

        ret =  MarkerWindowInteractor.OnButtonDown(self, wid, event)
        return ret
    def OnButtonUp(self, wid, event):
        if not hasattr(self, 'lastPnts'): return
        #calling this before base class freezes the cursor at last pos
        if not self.hasData: return 
        if  event.button==1:
            self.observer.InteractionOff()
        MarkerWindowInteractor.OnButtonUp(self, wid, event)            

        pnts = self.get_plane_points()

        if pnts != self.lastPnts:
            UndoRegistry().push_command(self.set_plane_points, self.lastPnts)
        return True
    

    def scroll_depth(self, step):
        # step along the normal
        p1 = array(self.pw.GetPoint1())
        p2 = array(self.pw.GetPoint2())

        origin = self.pw.GetOrigin()
        normal = self.pw.GetNormal()
        newPlane = vtk.vtkPlane()
        newPlane.SetNormal(normal)
        newPlane.SetOrigin(origin)
        newPlane.Push(step)
        newOrigin = newPlane.GetOrigin()

        delta = array(newOrigin) - array(origin) 
        p1 += delta
        p2 += delta
            
        self.pw.SetPoint1(p1)
        self.pw.SetPoint2(p2)
        self.pw.SetOrigin(newOrigin)
        self.pw.UpdatePlacement()
        self.update_plane()
        
    def scroll_axis1(self, step):
        #rotate around axis 1
        axis1 = [0,0,0]
        self.pw.GetVector1(axis1)
        transform = vtk.vtkTransform()

        axis2 = [0,0,0]
        self.pw.GetVector2(axis2)

        transform = vtk.vtkTransform()
        transform.RotateWXYZ(step,
                             (axis1[0] + 0.5*axis2[0],
                              axis1[1] + 0.5*axis2[2],
                              axis1[2] + 0.5*axis2[2]))
        o, p1, p2 = self.get_plane_points()
        o = transform.TransformPoint(o)
        p1 = transform.TransformPoint(p1)
        p2 = transform.TransformPoint(p2)
        self.set_plane_points((o, p1, p2))
        self.update_plane()
        
    def scroll_axis2(self, step):
        axis1 = [0,0,0]
        self.pw.GetVector2(axis1)
        transform = vtk.vtkTransform()

        axis2 = [0,0,0]
        self.pw.GetVector1(axis2)

        transform = vtk.vtkTransform()
        transform.RotateWXYZ(step,
                             (axis1[0] + 0.5*axis2[0],
                              axis1[1] + 0.5*axis2[2],
                              axis1[2] + 0.5*axis2[2]))
        o, p1, p2 = self.get_plane_points()
        o = transform.TransformPoint(o)
        p1 = transform.TransformPoint(p1)
        p2 = transform.TransformPoint(p2)
        self.set_plane_points((o, p1, p2))
        self.update_plane()


    def scroll_widget_slice(self, widget, event):

        now = time.time()
        elapsed = now - self.lastTime

        if elapsed < 0.001: return # swallow repeatede events

        if event.direction == gdk.SCROLL_UP: step = 1
        elif event.direction == gdk.SCROLL_DOWN: step = -1

        if self.interactor.GetShiftKey():
            self.scroll_axis1(step)
        elif self.interactor.GetControlKey():
            self.scroll_axis2(step)
        else:
            self.scroll_depth(step*self.sliceIncrement)
        
        

        self.get_pwxyz().Render()
        self.update_rings()
        self.Render()
        self.lastTime = time.time()

    def update_rings(self):
            
        self.ringActors.InitTraversal()
        numActors = self.ringActors.GetNumberOfItems()
        for i in range(numActors):
            actor = self.ringActors.GetNextActor()
            #print i, actor
            vis = actor.update()
            textActor = self.textActors[actor.get_marker()]
            if vis and EventHandler().get_labels_on():
                textActor.VisibilityOn()
            else:
                textActor.VisibilityOff()


    def interaction_event(self, *args):
        self.update_plane()
        self.update_rings()
        self.Render()

    def update_plane(self):
        p1 = self.pw.GetPoint1()
        p2 = self.pw.GetPoint2()
        o = self.pw.GetOrigin()
        self.observer.SetPoint1(p1)
        self.observer.SetPoint2(p2)
        self.observer.SetOrigin(o)
        self.observer.UpdatePlacement()
        self.renderer.ResetCameraClippingRange()

    def OnKeyPress(self, wid, event=None):
        
        if (event.keyval == gdk.keyval_from_name("i") or
            event.keyval == gdk.keyval_from_name("I")):

            xyz = self.get_cursor_position_world()
            if xyz is None: return 

            marker = Marker(xyz=xyz,
                            rgb=EventHandler().get_default_color())

            EventHandler().add_marker(marker)
            return True

        elif (event.keyval == gdk.keyval_from_name("r") or
              event.keyval == gdk.keyval_from_name("R")):
            self.set_camera(self.resetCamera)
            return True
        
        return MarkerWindowInteractor.OnKeyPress(self, wid, event)


    def update_viewer(self, event, *args):
        MarkerWindowInteractor.update_viewer(self, event, *args)
        if event=='add marker':
            marker = args[0]
            self.add_ring_actor(marker)
        elif event=='remove marker':
            marker = args[0]
            self.remove_ring_actor(marker)
        elif event=='move marker':
            # ring actor will update automatically because it shares
            # the sphere source
            marker, pos = args
            textActor = self.textActors[marker]
            textActor.SetPosition(pos)

        elif event=='color marker':
            marker, color = args
            actor = self.get_actor_for_marker(marker)
            actor.update()
        elif event=='label marker':
            marker, label = args
            marker.set_label(label)
            text = vtk.vtkVectorText()
            text.SetText(marker.get_label())
            textMapper = vtk.vtkPolyDataMapper()
            textMapper.SetInput(text.GetOutput())
            textActor = self.textActors[marker]
            textActor.SetMapper(textMapper)
        elif event=='observers update plane':
            self.update_plane()
            
        self.update_rings()
        self.Render()

    def add_ring_actor(self, marker):
        ringActor = RingActor(marker, self.pw, lineWidth=self.defaultRingLine)
        vis = ringActor.update()
        self.renderer.AddActor(ringActor)
        self.ringActors.AddItem(ringActor)


        # a hack to keep vtk from casting my class when I put it in
        # the collection.  If I don't register some func, I lose all
        # the derived methods        
        self.observer.AddObserver('EndInteractionEvent', ringActor.silly_hack)

        text = vtk.vtkVectorText()
        text.SetText(marker.get_label())
        textMapper = vtk.vtkPolyDataMapper()
        textMapper.SetInput(text.GetOutput())

        textActor = vtk.vtkFollower()
        textActor.SetMapper(textMapper)
        size = 2*marker.get_size()
        textActor.SetScale(size, size, size)
        x,y,z = marker.get_center()
        textActor.SetPosition(x, y, z)
        textActor.SetCamera(self.camera)
        textActor.GetProperty().SetColor(marker.get_label_color())
        if EventHandler().get_labels_on() and vis:
            textActor.VisibilityOn()
        else:
            textActor.VisibilityOff()

        self.textActors[marker] = textActor
        self.renderer.AddActor(textActor)


    def remove_ring_actor(self, marker):
        actor = self.get_actor_for_marker(marker)
        if actor is not None:
            self.renderer.RemoveActor(actor)
            self.ringActors.RemoveItem(actor)

        textActor = self.textActors[marker]
        self.renderer.RemoveActor(textActor)
        del self.textActors[marker]
        
    def get_actor_for_marker(self, marker):
        self.ringActors.InitTraversal()
        numActors = self.ringActors.GetNumberOfItems()
        for i in range(numActors):
            actor = self.ringActors.GetNextActor()
            if marker is actor.get_marker():
                return actor
        return None

    def get_ring_actors_as_list(self):

        self.ringActors.InitTraversal()
        numActors = self.ringActors.GetNumberOfItems()
        l = [None]*numActors
        for i in range(numActors):
            l[i] = self.ringActors.GetNextActor()
        return l

    def get_cursor_position_world(self):
        x, y = self.GetEventPosition()
        xyz = [x, y, 0.0]
        picker = vtk.vtkWorldPointPicker()
        picker.Pick(xyz, self.renderer)
        ppos = picker.GetPickPosition()
        return ppos
        #pos = self.get_cursor_position()
        #if pos is None: return None
        #world =  self.obs_to_world(pos)
        #return world
    
    def get_cursor_position(self):
        xyzv = [0,0,0,0]
        val = self.observer.GetCursorData(xyzv)
        if val: return xyzv[:3]
        else: return None

    def get_pwxyz(self):
        return self.owner.get_plane_widget_xyz()

    def get_pw(self):
        return self.pw

    def get_orientation(self):
        return self.orientation

    def obs_to_world(self, pnt):
        if not self.hasData: return 
        spacing = self.imageData.GetSpacing()
        transform = vtk.vtkTransform()
        transform.Scale(spacing)
        return transform.TransformPoint(pnt)

