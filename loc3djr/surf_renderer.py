from __future__ import division
import sys, os
import vtk

import pygtk
pygtk.require('2.0')
import gtk
from gtk import gdk
from GtkGLExtVTKRenderWindowInteractor import GtkGLExtVTKRenderWindowInteractor
from GtkGLExtVTKRenderWindow import GtkGLExtVTKRenderWindow

from pbrainlib.gtkutils import error_msg, simple_msg, ButtonAltLabel, \
     str2posint_or_err, str2posnum_or_err, ProgressBarDialog, make_option_menu
from matplotlib.cbook import Bunch

from events import EventHandler, UndoRegistry, Viewer
from markers import Marker
from shared import shared

colorSeq = (
    ( 'electrodes' , (0.482, 0.737, 0.820)    ),
    ( 'dark skin'  , (0.624, 0.427, 0.169)    ),
    ( 'light skin' , (0.953, 0.875, 0.765)    ),
    ( 'bone'       , (0.9804, 0.9216, 0.8431) ),
    )


colord = dict(colorSeq)

class DecimateFilter(vtk.vtkDecimate):
    """
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
            while gtk.events_pending(): gtk.mainiteration()


        def progress(o, event):
            val = o.GetProgress()
            prog.bar.set_fraction(val)            
            while gtk.events_pending(): gtk.mainiteration()
            
        def end(o, event):
            prog.hide()
            while gtk.events_pending(): gtk.mainiteration()

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
                

class ConnectFilter(vtk.vtkPolyDataConnectivityFilter):
    """
    Public attrs

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
            while gtk.events_pending(): gtk.mainiteration()

        def progress(o, event):
            val = o.GetProgress()
            prog.bar.set_fraction(val)            
            while gtk.events_pending(): gtk.mainiteration()
            
        def end(o, event):
            prog.hide()
            while gtk.events_pending(): gtk.mainiteration()

        self.AddObserver('StartEvent', start)
        self.AddObserver('ProgressEvent', progress)
        self.AddObserver('EndEvent', end)

    def update(self):
        self.SetExtractionMode(self.mode)
    

class SurfParams(Viewer):
    """
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
            while gtk.events_pending(): gtk.mainiteration()


        def progress(o, event):
            val = o.GetProgress()
            self.prog.bar.set_fraction(val)            
            while gtk.events_pending(): gtk.mainiteration()
            
        def end(o, event):
            self.prog.hide()
            while gtk.events_pending(): gtk.mainiteration()

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

class SurfRendererProps(gtk.Window, Viewer):

    SCROLLBARSIZE = 150,20
    lastColor = SurfParams.color
    paramd = {}   # a dict from names to SurfParam instances

    def __init__(self, sr, pwxyz):
        """sr is a SurfRenderer"""
        gtk.Window.__init__(self)
        self.set_title('Surface renderer properties')

        self.sr = sr
        self.interactorStyle = self.sr.GetInteractorStyle()

        self.sr.AddObserver('KeyPressEvent', self.key_press)
        self.pwxyz = pwxyz
        
        self.notebook = gtk.Notebook()
        self.notebook.show()

        vbox = gtk.VBox()
        vbox.show()
        vbox.pack_start(self.notebook, gtk.TRUE, gtk.TRUE)
        self.add(vbox)

        self._make_intensity_frame()
        self._make_camera_control()
        self._make_seqment_props_frame()
        self._make_pipeline_frame()
        self._make_picker_frame()


        def hide(*args):
            self.hide()
            return gtk.TRUE
        self.connect('delete_event', hide)

        # action area
        hbox = gtk.HBox()
        hbox.show()
        vbox.pack_start(hbox, gtk.TRUE, gtk.TRUE)        


        button = gtk.Button(stock=gtk.STOCK_CANCEL)
        button.show()
        button.connect('clicked', hide)
        hbox.pack_start(button, gtk.TRUE, gtk.TRUE)        

            
        button = ButtonAltLabel('Render', gtk.STOCK_EXECUTE)
        button.show()
        button.connect('clicked', self.render)
        hbox.pack_start(button, gtk.TRUE, gtk.TRUE)        

        button = gtk.Button(stock=gtk.STOCK_OK)
        button.show()
        button.connect('clicked', hide)
        hbox.pack_start(button, gtk.TRUE, gtk.TRUE)        


    def key_press(self, interactor, event):
        key = interactor.GetKeySym()
        if self.pickerName is None:
            error_msg('You must select the pick segment in the Picker tab')
            return
        if key.lower()=='i':
            x,y = interactor.GetEventPosition()
            picker = vtk.vtkCellPicker()
            picker.PickFromListOn()
            o = self.paramd[self.pickerName]
            picker.AddPickList(o.isoActor)
            picker.SetTolerance(0.005)
            picker.Pick(x, y, 0, self.sr.renderer)
            points = picker.GetPickedPositions()
            numPoints = points.GetNumberOfPoints()
            if numPoints<1: return
            pnt = points.GetPoint(0)


            marker = Marker(xyz=pnt,
                            rgb=EventHandler().get_default_color())

            EventHandler().add_marker(marker)
        elif key.lower()=='x':
            x,y = interactor.GetEventPosition()
            picker = vtk.vtkCellPicker()
            picker.PickFromListOn()
            for o in self.paramd.values():
                picker.AddPickList(o.isoActor)
            picker.SetTolerance(0.01)
            picker.Pick(x, y, 0, self.sr.renderer)
            cellId = picker.GetCellId()
            if cellId==-1:
                pass
            else:
                o = self.paramd.values()[0]
                o.remove.RemoveCell(cellId)
                interactor.Render()

        elif key.lower()=='e':
            o = self.paramd.values()[0]
            pw = o.planeWidget
            if pw.GetEnabled():
                pw.EnabledOff()
            else:
                pw.EnabledOn()


        
    def render(self, *args):
        self.sr.Render()
            
    def _make_pipeline_frame(self):
        """
        Set up the surface rendering pipeline

        This class will provide an attibutes dictionary that the
        SufaceRenderer class can use
        """


        vbox = gtk.VBox()
        vbox.show()
        vbox.set_spacing(3)
        
        label = gtk.Label('Pipeline')
        label.show()
        self.notebook.append_page(vbox, label)
        self.vboxPipelineFrame = vbox

        self.update_pipeline_frame()
        
        
    def update_pipeline_frame(self):

        vbox = self.vboxPipelineFrame

        decattrs = DecimateFilter.labels.keys()
        decattrs.sort()

        
        widgets = vbox.get_children()
        for w in widgets:
            vbox.remove(w)

        names = self.paramd.keys()
        names.sort()



        if not len(names):
            label = gtk.Label('No segments defined')
            label.show()
            vbox.pack_start(label)
            return        

        
        frame = gtk.Frame('Segments')
        frame.show()
        frame.set_border_width(5)
        vbox.pack_start(frame, gtk.TRUE, gtk.TRUE)

        boxRadio = gtk.VBox()
        boxRadio.show()
        frame.add(boxRadio)



        def get_active_name():
            for name, button in buttonNames.items():
                if button.get_active():
                    return name



        def update_params(*args):

            name = get_active_name()

            # set the active props of the filter frames
            self.buttonUseConnect.set_active(self.paramd[name].useConnect)
            self.buttonUseDecimate.set_active(self.paramd[name].useDecimate)

            activeButton = connectExtractButtons[self.paramd[name].connect.mode]
            activeButton.set_active(gtk.TRUE)

            # fill in the decimate entry boxes
            for attr in decattrs:
                s = DecimateFilter.labels[attr]
                fmt = DecimateFilter.fmts[attr]
                entry = self.__dict__['entry_' + attr]
                val = getattr(self.paramd[name].deci, attr)
                entry.set_text(fmt%val)


        # set the active segment by name
        lastButton = None
        buttonNames = {}
        for name in names:
            button = gtk.RadioButton(lastButton)
            button.set_label(name)
            button.set_active(name==names[0])
            button.show()
            button.connect('clicked', update_params)
            boxRadio.pack_start(button, gtk.TRUE, gtk.TRUE)
            buttonNames[name] = button
            lastButton = button


        segmentName = get_active_name()
        framePipelineFilters = gtk.Frame('Pipeline filters')
        framePipelineFilters.show()
        framePipelineFilters.set_border_width(5)
        vbox.pack_start(framePipelineFilters, gtk.TRUE, gtk.TRUE)

        frameConnectFilter = gtk.Frame('Connect filter settings')
        frameConnectFilter.show()
        frameConnectFilter.set_border_width(5)
        frameConnectFilter.set_sensitive(self.paramd[segmentName].useConnect)
        vbox.pack_start(frameConnectFilter, gtk.TRUE, gtk.TRUE)

        frameDecimateFilter = gtk.Frame('Decimate filter settings')
        frameDecimateFilter.show()
        frameDecimateFilter.set_border_width(5)
        frameDecimateFilter.set_sensitive(self.paramd[segmentName].useDecimate)
        vbox.pack_start(frameDecimateFilter, gtk.TRUE, gtk.TRUE)

        
        def connect_toggled(button):
            frameConnectFilter.set_sensitive(button.get_active())
            name = get_active_name()
            self.paramd[name].useConnect  = button.get_active()
            self.paramd[name].update_pipeline()


        vboxFrame = gtk.VBox()
        vboxFrame.show()
        vboxFrame.set_spacing(3)
        framePipelineFilters.add(vboxFrame)

        self.buttonUseConnect = gtk.CheckButton('Use connect filter')
        self.buttonUseConnect.show()
        self.buttonUseConnect.set_active(self.paramd[segmentName].useConnect)
        self.buttonUseConnect.connect('toggled', connect_toggled)
        vboxFrame.pack_start(self.buttonUseConnect, gtk.TRUE, gtk.TRUE)

        def decimate_toggled(button):
            frameDecimateFilter.set_sensitive(button.get_active())
            name = get_active_name()
            self.paramd[name].useDecimate = button.get_active()
            self.paramd[name].update_pipeline()

        self.buttonUseDecimate = gtk.CheckButton('Use decimate filter')
        self.buttonUseDecimate.show()
        self.buttonUseDecimate.set_active(self.paramd[segmentName].useDecimate)
        self.buttonUseDecimate.connect('toggled', decimate_toggled)
        vboxFrame.pack_start(self.buttonUseDecimate, gtk.TRUE, gtk.TRUE)


        vboxFrame = gtk.VBox()
        vboxFrame.show()
        vboxFrame.set_spacing(3)
        frameConnectFilter.add(vboxFrame)


        extractModes = ConnectFilter.num2mode.items()
        extractModes.sort()



        def set_extract_mode(button, num):
            name = get_active_name()
            self.paramd[name].connect.mode = num

        lastButton = None
        connectExtractButtons = {}
        for num, name in extractModes:
            button = gtk.RadioButton(lastButton)
            button.set_label(name)
            button.show()
            button.connect('toggled', set_extract_mode, num)
            vboxFrame.pack_start(button, gtk.TRUE, gtk.TRUE)
            connectExtractButtons[num] = button
            lastButton = button
        activeButton = connectExtractButtons[self.paramd[segmentName].connect.mode]
        activeButton.set_active(gtk.TRUE)

        vboxFrame = gtk.VBox()
        vboxFrame.show()
        vboxFrame.set_spacing(3)
        frameDecimateFilter.add(vboxFrame)


        table = gtk.Table(len(decattrs),2)
        table.set_col_spacings(3)
        table.set_row_spacings(3)
        table.show()
        vboxFrame.pack_start(table, gtk.TRUE, gtk.TRUE)        

        def make_row(name, default, fmt='%1.1f'):
            label = gtk.Label(name)
            label.show()
            label.set_alignment(xalign=1, yalign=0.5)
            entry = gtk.Entry()
            entry.show()
            entry.set_text(fmt%default)
            entry.set_width_chars(10)
            table.attach(label, 0, 1, make_row.rownum, make_row.rownum+1,
                         xoptions=gtk.FILL, yoptions=0)
            table.attach(entry, 1, 2, make_row.rownum, make_row.rownum+1,
                         xoptions=gtk.EXPAND|gtk.FILL, yoptions=0)
            make_row.rownum += 1
            return label, entry
        make_row.rownum=0

        for attr in decattrs:
            label = DecimateFilter.labels[attr]
            fmt = DecimateFilter.fmts[attr]

            val = getattr(self.paramd[segmentName].deci, attr)
            label, entry = make_row(label, val, fmt)
            self.__dict__['label_' + attr] = label
            self.__dict__['entry_' + attr] = entry



        def apply(button):
            name = get_active_name()
            if self.paramd[name].useDecimate:
                for attr in decattrs:
                    label = self.__dict__['label_' + attr]
                    entry = self.__dict__['entry_' + attr]
                    converter = DecimateFilter.converters[attr]
                    val = converter(entry.get_text(), label, self)
                    if val is None: return
                    setattr(self.paramd[name].deci, attr, val)

            self.paramd[name].update_properties()
            
        button = gtk.Button(stock=gtk.STOCK_APPLY)
        button.show()
        vbox.pack_start(button, gtk.TRUE, gtk.TRUE)
        button.connect('clicked', apply)
        

    def _make_intensity_frame(self):
        """
        Provides the following attributes
        self.collecting         # intensity collection on
        self.intensitySum = 0   # intensity sum
        self.intensityCnt = 0   # intensity cnt
        self.labelIntensity     # label for intensity entry
        self.entryIntensity     # intensity entry box
        """

        self.collecting = False
        self.intensitySum = 0
        self.intensityCnt = 0


        vbox = gtk.VBox()
        vbox.show()
        vbox.set_spacing(3)
        
        label = gtk.Label('Segmentation')
        label.show()
        self.notebook.append_page(vbox, label)

        frame = gtk.Frame('Set the segment intensity')
        frame.show()
        frame.set_border_width(5)
        vbox.pack_start(frame, gtk.FALSE, gtk.FALSE)
        
        vboxFrame = gtk.VBox()
        vboxFrame.show()
        vboxFrame.set_spacing(3)
        frame.add(vboxFrame)

        table = gtk.Table(1,2)
        table.set_col_spacings(3)
        table.show()
        vboxFrame.pack_start(table, gtk.TRUE, gtk.TRUE)        

        self.labelIntensity = gtk.Label('Value: ')
        self.labelIntensity.show()
        self.entryIntensity = gtk.Entry()
        self.entryIntensity.show()
        self.entryIntensity.set_text('%1.1f' % SurfParams.intensity)


        table.attach(self.labelIntensity, 0, 1, 0, 1,
                     xoptions=gtk.FILL, yoptions=0)
        table.attach(self.entryIntensity, 1, 2, 0, 1,
                     xoptions=gtk.EXPAND|gtk.FILL, yoptions=0)



        hbox = gtk.HBox()
        hbox.show()
        hbox.set_homogeneous(gtk.TRUE)
        hbox.set_spacing(3)
        vboxFrame.pack_start(hbox, gtk.FALSE, gtk.FALSE)
            
        button = ButtonAltLabel('Capture', gtk.STOCK_ADD)
        button.show()
        button.connect('clicked', self.start_collect_intensity)
        hbox.pack_start(button, gtk.TRUE, gtk.TRUE)

        button = ButtonAltLabel('Stop', gtk.STOCK_STOP)
        button.show()
        button.connect('clicked', self.stop_collect_intensity)
        hbox.pack_start(button, gtk.TRUE, gtk.TRUE)

        button = ButtonAltLabel('Clear', gtk.STOCK_CLEAR)
        button.show()
        button.connect('clicked', self.clear_intensity)
        hbox.pack_start(button, gtk.TRUE, gtk.TRUE)



        frame = gtk.Frame('Segment properties')
        frame.show()
        frame.set_border_width(5)
        vbox.pack_start(frame, gtk.FALSE, gtk.FALSE)
        
        vboxFrame = gtk.VBox()
        vboxFrame.show()
        vboxFrame.set_spacing(3)
        frame.add(vboxFrame)
        
        

        table = gtk.Table(2,2)
        table.set_col_spacings(3)
        table.set_row_spacings(3)
        table.show()
        vboxFrame.pack_start(table, gtk.TRUE, gtk.TRUE)                

        self.labelName = gtk.Label('Label: ')
        self.labelName.show()
        self.labelName.set_alignment(xalign=1.0, yalign=0.5)
        self.entryName = gtk.Entry()
        self.entryName.show()
        self.entryName.set_text(SurfParams.label)

        table.attach(self.labelName, 0, 1, 0, 1,
                     xoptions=gtk.FILL, yoptions=0)
        table.attach(self.entryName, 1, 2, 0, 1,
                     xoptions=gtk.EXPAND|gtk.FILL, yoptions=0)


        def func(menuitem, s):
            if s=='choose':
                self.lastColor = self.choose_color()
            else:
                self.entryName.set_text(s)
                self.lastColor = colord[s]
                            

        colors = [ name for name, color in colorSeq]
        colors.append('choose')
        label = gtk.Label('Color: ')
        label.show()
        label.set_alignment(xalign=1.0, yalign=0.5)
        optmenu, menud = make_option_menu(
            colors, func)
        optmenu.show()
        table.attach(label, 0, 1, 1, 2,
                     xoptions=gtk.FILL, yoptions=0)
        table.attach(optmenu, 1, 2, 1, 2,
                     xoptions=gtk.EXPAND|gtk.FILL, yoptions=0)
        

        button = ButtonAltLabel('Add segment', gtk.STOCK_ADD)
        button.show()
        button.connect('clicked', self.add_segment)
        vbox.pack_start(button, gtk.FALSE, gtk.FALSE)        

        
    def _make_seqment_props_frame(self):
        """
        Control the sement attributes (delete, opacity, etc)
        """


        vbox = gtk.VBox()
        vbox.show()
        vbox.set_spacing(3)
        
        label = gtk.Label('Segments')
        label.show()
        self.notebook.append_page(vbox, label)

        frame = gtk.Frame('Segment properties')
        frame.show()
        frame.set_border_width(5)
        vbox.pack_start(frame, gtk.TRUE, gtk.TRUE)

        
        vboxFrame = gtk.VBox()
        vboxFrame.show()
        vboxFrame.set_spacing(3)
        frame.add(vboxFrame)

        self.vboxSegPropsFrame = vboxFrame
        self.update_segments_frame() 

        
    def update_segments_frame(self):
        'Update the segment props with the latest segments'

        vbox = self.vboxSegPropsFrame
        
        widgets = vbox.get_children()
        for w in widgets:
            vbox.remove(w)

        names = self.paramd.keys()

        if not len(names):
            label = gtk.Label('No segments')
            label.show()
            vbox.pack_start(label)
            return
        
        names.sort()
        numrows = len(names)+1
        numcols = 2

        table = gtk.Table(numrows,numcols)
        table.set_col_spacings(3)
        table.show()
        vbox.pack_start(table, gtk.TRUE, gtk.TRUE)        

        delete = gtk.Label('Hide')
        delete.show()
        opacity = gtk.Label('Opacity')
        opacity.show()
        

        table.attach(delete, 0, 1, 0, 1, xoptions=gtk.FILL, yoptions=0)
        table.attach(opacity, 1, 2, 0, 1, xoptions=gtk.EXPAND|gtk.FILL, yoptions=0)
        deleteButtons = {}
        opacityBars = {}


        class OpacityCallback:
            def __init__(self, sr, name, paramd):
                """
                sr is the surf renderer instance
                name is the name of the surface
                paramd is the dict mapping names to objects

                You don't want to pass the object itself because it is
                bound at init time but you to be able to dynamically
                update
                """
                self.name = name
                self.sr = sr
                self.paramd = paramd

            def __call__(self, bar):
                val = bar.get_value()
                self.paramd[self.name].isoActor.GetProperty().SetOpacity(val)

        class HideCallback:
            def __init__(self, sr, name, paramd):
                """
                sr is the surf renderer instance
                name is the name of the surface
                paramd is the dict mapping names to objects

                You don't want to pass the object itself because it is
                bound at init time but you to be able to dynamically
                update                
                """
                self.sr = sr
                self.name = name
                self.paramd = paramd
                self.removed = False

            def __call__(self, button):

                if button.get_active():
                    self.paramd[self.name].isoActor.VisibilityOff()
                else:
                    self.paramd[self.name].isoActor.VisibilityOn()
                self.sr.Render()                    

        rownum = 1                
        for name in names:
            hideCallback = HideCallback(self.sr, name, self.paramd)
            opacityCallback = OpacityCallback(self.sr, name, self.paramd)            
            b = gtk.CheckButton(name)
            b.show()
            b.set_active(gtk.FALSE)
            b.connect('toggled', hideCallback)
            table.attach(b, 0, 1, rownum, rownum+1,
                         xoptions=gtk.FALSE, yoptions=gtk.FALSE)
            deleteButtons[name] = b

            scrollbar = gtk.HScrollbar()
            scrollbar.show()
            scrollbar.set_size_request(*self.SCROLLBARSIZE)
            table.attach(scrollbar, 1, 2, rownum, rownum+1,
                         xoptions=gtk.TRUE, yoptions=gtk.FALSE)
            
            scrollbar.set_range(0, 1)
            scrollbar.set_increments(.05, .2)
            scrollbar.set_value(1.0)


            scrollbar.connect('value_changed', opacityCallback)
            rownum += 1


    def _make_picker_frame(self):
        """
        Controls to clean up the rendered segments
        """


        vbox = gtk.VBox()
        vbox.show()
        vbox.set_spacing(3)
        
        label = gtk.Label('Picker')
        label.show()
        self.notebook.append_page(vbox, label)

        frame = gtk.Frame('Select on which segment')
        frame.show()
        frame.set_border_width(5)
        vbox.pack_start(frame, gtk.TRUE, gtk.TRUE)

        
        vboxFrame = gtk.VBox()
        vboxFrame.show()
        vboxFrame.set_spacing(3)
        frame.add(vboxFrame)

        self.vboxPickerFrame = vboxFrame
        self.pickerName = None
        self.update_picker_frame() 

    def update_picker_frame(self):
        'Update the picker frame with the latest segments'

        # the name of the segment to be picked

        keys = self.paramd.keys()
        if len(keys) and self.pickerName is None:
            self.pickerName = keys[0]
        
        vbox = self.vboxPickerFrame
        
        widgets = vbox.get_children()
        for w in widgets:
            vbox.remove(w)

        names = self.paramd.keys()

        if not len(names):
            label = gtk.Label('No segments')
            label.show()
            vbox.pack_start(label)
            return
        
        names.sort()

        boxRadio = gtk.VBox()
        boxRadio.show()
        vbox.pack_start(boxRadio, gtk.TRUE, gtk.TRUE)

        def radio_changed(button):
            label = button.get_label()
            if label=='None': self.pickerName = None
            else: self.pickerName = label
            
        
        lastButton = None
        button = gtk.RadioButton(lastButton)
        button.set_label('None')
        button.set_active(True)
        button.connect('clicked', radio_changed)
        lastButton = button

        for name in names:
            button = gtk.RadioButton(lastButton)
            button.set_label(name)
            button.set_active(False)
            button.show()
            button.connect('clicked', radio_changed)
            boxRadio.pack_start(button, gtk.FALSE, gtk.FALSE)
            lastButton = button


    def clear_intensity(self, button):
        self.intensitySum = 0
        self.intensityCnt = 0
        self.entryIntensity.set_text('%1.1f' % SurfParams.intensity)        

    def start_collect_intensity(self, button):
        self.collecting = True

    def stop_collect_intensity(self, button):
        self.collecting = False

    def add_intensity(self, val):
        if self.collecting:
            self.intensitySum += val
            self.intensityCnt += 1

    def add_segment(self, button):
        'render, man'
        val = self.get_intensity()
        if val is None: return
        name = self.entryName.get_text()
        if not len(name):
            error_msg('You must enter a name in the Intensity tab')
            return

        if not self.paramd.has_key(name):
            self.paramd[name] = SurfParams(self.sr.renderer, self.sr.interactor)

        params = self.paramd[name]
        params.label = name
        params.intensity = val
        params.color = self.lastColor
        params.set_image_data(self.sr.imageData)
        params.update_properties()
        
        self.update_segments_frame() 
        self.update_pipeline_frame()
        self.update_picker_frame()
        
    def interaction_event(self, observer, event):
        if not self.collecting: return 
        xyzv = [0,0,0,0]
        observer.GetCursorData(xyzv)
        self.add_intensity(xyzv[3])
        self.entryIntensity.set_text('%1.1f' % (self.intensitySum/self.intensityCnt))

    def get_intensity(self):
        """
        Get the intensity of value if valid.

        If not warn and return None
        """
        
        val = str2posnum_or_err(self.entryIntensity.get_text(),
                                self.labelIntensity, parent=self)
        return val


    def _make_camera_control(self):
        """
        Control the view of the rendered surface
        """

        frame = gtk.Frame('Camera views')
        frame.show()
        frame.set_border_width(5)

        label = gtk.Label('Views')
        label.show()
        self.notebook.append_page(frame, label)

        vbox = gtk.VBox()
        vbox.show()
        vbox.set_spacing(3)
        frame.add(vbox)


        def planes_to_surf_view(button):
            fpu = self.sr.get_camera_fpu()
            self.pwxyz.set_camera(fpu)
            self.pwxyz.Render()
            
        button = ButtonAltLabel('Snap planes to surf view', gtk.STOCK_GO_BACK)
        button.show()
        button.connect('clicked', planes_to_surf_view)
        vbox.pack_start(button, gtk.FALSE, gtk.FALSE)

        def surf_to_planes_view(button):
            fpu = self.pwxyz.get_camera_fpu()
            self.sr.set_camera(fpu)
            self.sr.Render()


        button = ButtonAltLabel('Snap surf to planes view', gtk.STOCK_GO_FORWARD)
        button.show()
        button.connect('clicked', surf_to_planes_view)
        vbox.pack_start(button, gtk.FALSE, gtk.FALSE)
    

    def choose_color(self, *args):
        dialog = gtk.ColorSelectionDialog('Choose segment color')
            
        colorsel = dialog.colorsel

        da = gtk.DrawingArea()
        cmap = da.get_colormap()

        r,g,b = [int(65535*val) for val in self.lastColor]
        color = cmap.alloc_color(r,g,b)
        colorsel.set_previous_color(color)
        colorsel.set_current_color(color)
        colorsel.set_has_palette(gtk.TRUE)
    
        response = dialog.run()
        
        if response == gtk.RESPONSE_OK:
            color = colorsel.get_current_color()
            self.lastColor = [val/65535 for val in (color.red, color.green, color.blue)]

        dialog.destroy()
        return self.lastColor


class SurfRenderWindow(GtkGLExtVTKRenderWindowInteractor, Viewer):

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
            self.add_marker(marker) # fixme
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
