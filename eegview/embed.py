from __future__ import division
import os


import pygtk
#pygtk.require('2.0')
import gtk
import vtk

from loc3djr.GtkGLExtVTKRenderWindowInteractor import GtkGLExtVTKRenderWindowInteractor

from matplotlib.numerix import array, take, cross_correlate, fromstring, arange, Int16, Float, log10

from pbrainlib.gtkutils import error_msg, simple_msg, make_option_menu,\
     get_num_value, get_num_range, get_two_nums, str2num_or_err

from events import Observer
from dialogs import SpecProps



class EmbedWin(gtk.Window, Observer):

    def __init__(self, eegplot):
        gtk.Window.__init__(self)
        Observer.__init__(self)
        self.set_size_request(300, 300)
        self.eegplot = eegplot
        self.eeg = eegplot.get_eeg()
        self.eoi = eegplot.get_eoi()
        


        vbox = gtk.VBox()
        vbox.show()
        vbox.set_spacing(3)
        self.add(vbox)



        interactor = GtkGLExtVTKRenderWindowInteractor()
        vbox.pack_start(interactor, True, True)

        toolbar = self.make_toolbar()
        toolbar.show()
        vbox.pack_start(toolbar, False, False)

        interactor.show()
        interactor.Initialize()
        interactor.Start()
        interactor.AddObserver("ExitEvent", lambda o,e,x=None: x)

        self.renderer = vtk.vtkRenderer()
        interactor.GetRenderWindow().AddRenderer(self.renderer)
        self.interactor = interactor

        self.set_title("Embedding Window")
        self.set_border_width(10)

        self.scatterActor = None

        self.make_embed()  #last line!
        
    def make_toolbar(self):

        toolbar  = gtk.Toolbar()
        iconSize = gtk.ICON_SIZE_SMALL_TOOLBAR
        toolbar.set_border_width(5)
        toolbar.set_style(gtk.TOOLBAR_ICONS)
        toolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)

        l = gtk.Label('Lag')
        l.show()
        toolbar.append_widget(
            l, 'Embedding lag as number of stepsizes', '')


        e = gtk.Entry()
        e.set_text('50')
        e.set_width_chars(3)        
        e.show()
        toolbar.append_widget(
            e, 'Embedding lag as number of stepsizes', '')
        self.entryLag = e

        toolbar.append_space()
        
        l = gtk.Label('Dimension')
        l.show()
        toolbar.append_widget(
            l, 'Embedding dimension', '')
        e = gtk.Entry()
        e.set_text('3')
        e.set_width_chars(3)        
        e.show()
        toolbar.append_widget(
            e, 'Embedding lag as number of stepsizes', '')
        self.entryDim = e
        
        toolbar.append_space()
        self.buttonFollowEvents = gtk.CheckButton('Auto')
        self.buttonFollowEvents.show()
        self.buttonFollowEvents.set_active(True)
        toolbar.append_widget(
            self.buttonFollowEvents, 'Automatically update embedding in response to changes in EEG window', '')

        toolbar.append_space()
            
        iconw = gtk.Image() # icon widget
        iconw.set_from_stock(gtk.STOCK_EXECUTE, iconSize)
        button = toolbar.append_item(
            'Update',
            'Update plot',
            'Private', 
            iconw,
            self.make_embed)

        return toolbar

    def make_embed(self, *args):

        if self.scatterActor is not None:
            self.renderer.RemoveActor(self.scatterActor)            

        selected = self.eegplot.get_selected()
        if selected is None:
            error_msg('You must first select an EEG channel by clicking on it',
                      parent=self)
            return
        torig, data, trode = selected
        gname, gnum = trode
        label = '%s %d' % (gname, gnum)

        Fs = self.eegplot.eeg.freq
        dt = 1.0/Fs

        try: lag = int(self.entryLag.get_text())
        except ValueError:
            error_message('Lag must be an integer; found "%s"'%self.entryLag.get_text())
            return

        
        try: dim = int(self.entryDim.get_text())
        except ValueError:
            error_message('Dimension must be an integer; found "%s"'%self.entrySim.get_text())
            return

        pnts = []
        ind = arange(dim)*lag

        while 1:
            if ind[-1]>=len(data): break
            pnts.append( take(data, ind)[:3] )  # plot 3 dims
            ind += 1


        polyData = vtk.vtkPolyData()

        points = vtk.vtkPoints()

        for i, pnt in enumerate(pnts):
            x, y, z = pnt
            points.InsertPoint(i, x, y, z)

        polyData = vtk.vtkPolyData()
        polyData.SetPoints(points)

        sphere = vtk.vtkSphereSource()
        res = 5
        sphere.SetThetaResolution(res)
        sphere.SetPhiResolution(res)
        sphere.SetRadius(10)

        filter = vtk.vtkGlyph3D()
        filter.SetInput(polyData)
        filter.SetSource(0, sphere.GetOutput())

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInput(filter.GetOutput())

        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor( 1,1,0 )
        self.scatterActor = actor
        self.renderer.AddActor(actor)
        self.interactor.Render()
        
    def recieve(self, event, *args):
        if not self.buttonFollowEvents.get_active(): return
        if event in (Observer.SELECT_CHANNEL, Observer.SET_TIME_LIM):
            self.make_embed()
            
            
    
