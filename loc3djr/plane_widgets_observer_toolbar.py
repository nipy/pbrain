import gtk
import vtk

def move_pw_to_point(pw, xyz):

    n = pw.GetNormal()
    o = pw.GetOrigin()
    pxyz = [0,0,0]
    vtk.vtkPlane.ProjectPoint(xyz, o, n, pxyz)
    transform = vtk.vtkTransform()
    transform.Translate(xyz[0]-pxyz[0], xyz[1]-pxyz[1], xyz[2]-pxyz[2])
    p1 = transform.TransformPoint(pw.GetPoint1())
    p2 = transform.TransformPoint(pw.GetPoint2())
    o = transform.TransformPoint(o)

    pw.SetOrigin(o)                
    pw.SetPoint1(p1)
    pw.SetPoint2(p2)
    pw.UpdatePlacement()
    
        

class ObserverToolbar(gtk.Toolbar):
    """
    CLASS: ObserverToolbar
    DESCR:
    """

    def __init__(self, pwo):
        'pwo is a PlaneWidgetObserver'
        gtk.Toolbar.__init__(self)

        self.pwo = pwo

        iconSize = gtk.ICON_SIZE_BUTTON
        
        self.set_border_width(5)
        self.set_style(gtk.TOOLBAR_ICONS)
        self.set_orientation(gtk.ORIENTATION_HORIZONTAL)


        def ortho(button):
            pw = pwo.get_pw()
            o = pw.GetCenter()
            xyz = pwo.obs_to_world(o)
            pwxyz = pwo.get_pwxyz()
            pw.SetPlaneOrientation(pwo.get_orientation())
            move_pw_to_point(pw, xyz)
            pwo.update_plane()
            pwo.Render()
            pwxyz.Render()

        iconw = gtk.Image() # icon widget
        iconw.set_from_stock(gtk.STOCK_ADD, iconSize)
        buttonOrtho = self.append_item(
            'Ortho',
            'Restore orthogonality of plane widget',
            'Private',
            iconw,
            ortho)


        def jumpto(button):
            pwxyz = pwo.get_pwxyz()
            pos = pwo.get_cursor_position()
            # get the cursor if it's on, else selection
            if pos is not None:
                xyz = pwo.obs_to_world(pos)
            else:
                selected = EventHandler().get_selected()
                if len(selected) !=1: return
                marker = selected[0]
                xyz = marker.get_center()

            pwxyz.snap_view_to_point(xyz)

        iconw = gtk.Image() # icon widget
        iconw.set_from_stock(gtk.STOCK_JUMP_TO, iconSize)
        buttonJump = self.append_item(
            'Jump to',
            'Move the planes to the point under the cursor or\n' +
            'to the selected marker if only one marker is selected',
            'Private',
            iconw,
            jumpto)

        def coplanar(self):
            numSelected = EventHandler().get_num_selected()
            if numSelected !=3:
                error_msg("You must first select exactly 3 markers",
                          )
                return

            # SetNormal is missing from the 4.2 python API so this is
            # a long winded way of setting the pw to intersect 3
            # selected markers
            m1, m2, m3 = EventHandler().get_selected()

            p1 = m1.get_center()
            p2 = m2.get_center()
            p3 = m3.get_center()
            
            pw = pwo.get_pw()
            planeO = vtk.vtkPlaneSource()
            planeO.SetOrigin(pw.GetOrigin())
            planeO.SetPoint1(pw.GetPoint1())
            planeO.SetPoint2(pw.GetPoint2())
            planeO.Update()

            planeN = vtk.vtkPlaneSource()
            planeN.SetOrigin(p1)
            planeN.SetPoint1(p2)
            planeN.SetPoint2(p3)
            planeN.Update()

            normal = planeN.GetNormal()
            planeO.SetNormal(normal)
            planeO.SetCenter(
                (p1[0] + p2[0] + p3[0])/3,
                (p1[1] + p2[1] + p3[1])/3,
                (p1[2] + p2[2] + p3[2])/3,
                )
            planeO.Update()

            pwxyz = pwo.get_pwxyz()
            pw.SetOrigin(planeO.GetOrigin())
            pw.SetPoint1(planeO.GetPoint1())
            pw.SetPoint2(planeO.GetPoint2())
            pw.UpdatePlacement()
            pwo.update_plane()
            pwo.Render()
            pwxyz.Render()
            
                       
        iconw = gtk.Image() # icon widget
        iconw.set_from_stock(gtk.STOCK_REDO, iconSize)
        buttonPlaneSelected = self.append_item(
            'Set plane',
            'Set the plane to be coplanar with 3 selected electrodes',
            'Private',
            iconw,
            coplanar)

    
