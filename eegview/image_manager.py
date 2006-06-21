from __future__ import division
import sys, os, math
import vtk

import gtk, gobject

from loc3djr import image_reader
from pbrainlib.gtkutils import ButtonAltLabel
from plane_widgets import PlaneWidgetsXYZ

class ImageManager:
    """
    **********************************************************************
    CLASS: ImageManager
    DESCR: used by View3 to maintain vtkImagePlaneWidgets
    **********************************************************************
    """
    SCROLLBARSIZE = 150,20
    def __init__(self, interactor, renderer):
        self.interactor = interactor
        self.renderer = renderer
        self.pwX = vtk.vtkImagePlaneWidget()        
        self.pwY = vtk.vtkImagePlaneWidget()        
        self.pwZ = vtk.vtkImagePlaneWidget()
        self._usingPlanes = False
        self.readerDlg = image_reader.widgets['dlgReader']
        self.propsDlg = self.make_prop_dialog()
        
    def show_prefs(self, *args):
        self.propsDlg.show()


    def load_image_dialog(self, *args):                
        response = self.readerDlg.run()

        if response == gtk.RESPONSE_OK:
            try: reader = image_reader.widgets.reader
            except AttributeError: 
                pars = image_reader.widgets.get_params()
                pars = image_reader.widgets.validate(pars)
                if pars is None:
                    error_msg('Could not validate the parameters',
                              self.readerDlg)
                    return
                reader = image_reader.widgets.get_reader(pars)

            imageData = reader.GetOutput()
            imageData.SetSpacing(reader.GetDataSpacing())
            self.imageData = imageData
            self.load_image_data()
        else:
            imageData = None
        self.readerDlg.hide()


    def load_image_data(self, *args):

        if self.imageData is None: return 
        self.pwxyz = PlaneWidgetsXYZ(self.imageData)
        self.pwxyz.show()

        extent = self.imageData.GetExtent()
        frac = 0.3

        self._plane_widget_boilerplate(
            self.pwX, key='x', color=(1,0,0),
            index=frac*(extent[1]-extent[0]),
            orientation=0)

        self._plane_widget_boilerplate(
            self.pwY, key='y', color=(1,1,0),
            index=frac*(extent[3]-extent[2]),
            orientation=1)
        self.pwY.SetLookupTable(self.pwX.GetLookupTable())

        self._plane_widget_boilerplate(
            self.pwZ, key='z', color=(0,0,1),
            index=frac*(extent[5]-extent[4]),
            orientation=2)
        self.pwZ.SetLookupTable(self.pwX.GetLookupTable())        
        self.pwX.SetResliceInterpolateToCubic()
        self.pwY.SetResliceInterpolateToCubic()
        self.pwZ.SetResliceInterpolateToCubic()
        self.camera = self.renderer.GetActiveCamera()

        center = self.imageData.GetCenter()
        spacing = self.imageData.GetSpacing()
        bounds = self.imageData.GetBounds()
        pos = center[0], center[1], center[2] - max(bounds)*2
        fpu = center, pos, (0,-1,0)
        self.set_camera(fpu)
        self.set_interact()
        self._usingPlanes = True

    def using_planes(self):
        return self._usingPlanes

    def _plane_widget_boilerplate(self, pw, key, color, index, orientation):

        pw.TextureInterpolateOn()
        #pw.SetResliceInterpolateToCubic()
        pw.SetKeyPressActivationValue(key)
        pw.GetPlaneProperty().SetColor(color)
        pw.DisplayTextOn()
        pw.SetInput(self.imageData)
        pw.SetPlaneOrientation(orientation)
        pw.SetSliceIndex(int(index))
        pw.SetInteractor(self.interactor)
        pw.On()
        pw.UpdatePlacement()

    def set_camera(self, fpu):
        camera = self.renderer.GetActiveCamera()
        focal, position, up = fpu
        camera.SetFocalPoint(focal)
        camera.SetPosition(position)
        camera.SetViewUp(up)
        self.renderer.ResetCameraClippingRange()
        self.interactor.Render()

    def set_interact(self, *args):
        'b is a boolean'
        if self.imageData is None: return

        if self.buttonInteract.get_active():
            self.pwX.InteractionOn()
            self.pwY.InteractionOn()
            self.pwZ.InteractionOn()
        else:
            self.pwX.InteractionOff()
            self.pwY.InteractionOff()
            self.pwZ.InteractionOff()


    def make_prop_dialog(self):

        dlg = gtk.Dialog('Image data properties')

        vbox = dlg.vbox

        button = ButtonAltLabel('Info file', gtk.STOCK_OPEN)
        button.show()
        vbox.pack_start(button, False, False)
        button.connect('clicked', self.load_image_dialog)


        button = gtk.CheckButton('Interact with planes')
        button.show()
        vbox.pack_start(button, False, False)
        button.set_active(False)
        button.connect('toggled', self.set_interact)
        self.buttonInteract = button

        frame = gtk.Frame('Opacity')
        frame.show()
        frame.set_border_width(5)
        vbox.pack_start(frame, True, True)



        table = gtk.Table(4,2)
        table.set_homogeneous(False)
        table.show()
        frame.add(table)
        
        table.set_col_spacings(3)
        table.set_row_spacings(3)
        table.set_border_width(3)
        
        class OpacityScrollbar(gtk.HScrollbar):
            render = True
            interactor = self.interactor
            SCROLLBARSIZE = self.SCROLLBARSIZE
            def __init__(self, labelStr, pw, row):
                self.pw = pw
                label = gtk.Label(labelStr)
                label.show()

                scrollbar = gtk.HScrollbar()
                scrollbar.show()
                scrollbar.set_range(0, 1)
                scrollbar.set_increments(0.05,0.25)
                scrollbar.set_value(1)
                scrollbar.set_size_request(*self.SCROLLBARSIZE)
                self.scrollbar = scrollbar
                scrollbar.connect('value_changed', self.set_opacity)

                table.attach(label, 0, 1, row, row+1,
                             xoptions=gtk.EXPAND, yoptions=gtk.EXPAND)
                table.attach(scrollbar, 1, 2, row, row+1,
                             xoptions=gtk.FILL, yoptions=gtk.EXPAND)

            def set_opacity(self, *args):
                val = self.scrollbar.get_value()
                self.pw.GetTexturePlaneProperty().SetOpacity(val)
                self.pw.GetPlaneProperty().SetOpacity(val)
                if self.render: self.interactor.Render()

        xScroll = OpacityScrollbar('X', self.pwX, 0)
        yScroll = OpacityScrollbar('Y', self.pwY, 1)
        zScroll = OpacityScrollbar('Z', self.pwZ, 2)
        row = 3


        label = gtk.Label('All')
        label.show()

        scrollbar = gtk.HScrollbar()
        scrollbar.show()
        scrollbar.set_range(0, 1)
        scrollbar.set_increments(0.05,0.25)
        scrollbar.set_value(1)

        def set_all_opacity(bar):
            xScroll.render=False
            yScroll.render=False
            zScroll.render=False
            val = bar.get_value()
            xScroll.scrollbar.set_value(val)
            yScroll.scrollbar.set_value(val)
            zScroll.scrollbar.set_value(val)
            xScroll.render=True
            yScroll.render=True
            zScroll.render=True
            self.interactor.Render()
            
        scrollbar.connect('value_changed', set_all_opacity)
        scrollbar.set_size_request(150,20)

        table.attach(label, 0, 1, row, row+1,
                     xoptions=gtk.EXPAND, yoptions=gtk.EXPAND)
        table.attach(scrollbar, 1, 2, row, row+1,
                     xoptions=gtk.FILL, yoptions=gtk.EXPAND)



        def hide(button):
            dlg.hide()
            return True
        
        button = ButtonAltLabel('Hide', gtk.STOCK_CANCEL)
        button.show()
        button.connect('clicked', hide)
        vbox.pack_end(button, False, False)        

        return dlg

