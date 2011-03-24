from __future__ import division
import sys, os, math
import vtk

import gtk, gobject

from loc3djr import image_reader
from loc3djr.markers import Marker
from pbrainlib.gtkutils import error_msg, simple_msg, make_option_menu,\
     get_num_value, get_num_range, get_two_nums, str2int_or_err,\
     OpenSaveSaveAsHBox, ButtonAltLabel, numbify

from matplotlib.cbook import exception_to_str

from shared import fmanager

try:
    set
except:
    from sets import Set as set

#from Numeric import array, zeros, ones, sort, absolute, sqrt, divide,\
#     argsort, take, arange
from scipy import array, zeros, ones, sort, absolute, sqrt, divide,\
     argsort, take, arange
import numpy as np 

from amp_dialog import AmpDialog
from array_mapper import ArrayMapper
from data import Amp


def identity(frac, *args):
    return frac

def dist(x,y):
    tmp = array(x)-array(y)
    return sqrt(sum(tmp**2))



class GridManager:
    """
    CLASS: GridManager
    DESCR: maintains list of VTK actors for view3d display
    """
    SCROLLBARSIZE = 150,20
    def __init__(self, interactor, renderer, meshManager, view3, infile, dimensiond=None):
        self.view3 = view3
        self.interactor = interactor
        self.renderer = renderer
        self.meshManager = meshManager
        self.gridActors = {}  # dict from name -> grid or ribbon actors
        self.ribbons = {}     # dict from name -> ribbon actor
        self.surfs = {}       # dict from name -> surf actor
        self.normalActors = []
        self.markers = []
        self.textActors = []
        self.tubeActors = []
        self.dimensiond = dimensiond
        self.scalarSet = []        
        self.scalarVals = []
        self.dlgDim = None
        self.dlgProp = None
        self.vtkIDs = {}  # a map from name, num -> vtkID
        ok = self.load_markers(infile)

        # a set of gridnames where we have wanred if can't build grid
        self.gridWarned = set()  
        self.markerFilename = None
        self.ok = ok

        self.ampAscii  = None  # an ampfile for ascii data

        # mcc: create a ScalarBarActor to be used in interactor. we need
        # to call SetLookupTable() and give it a pointer to a lookup
        # table used by one of the "actors" in the "scene".
        self.scalarBar = vtk.vtkScalarBarActor()
        self.scalarBar.SetWidth(0.15)
        self.scalarBar.SetHeight(0.5)
        self.scalarBar.SetTitle("ECoG Power")
        self.scalarBar.SetLabelFormat ("%-#6.f")
        self.scalarBar.GetTitleTextProperty().SetColor(1.0,1.0,1.0)
        #self.scalarBar.SetPosition(0.8,0.2)
        self.scalarBar.VisibilityOff()
        # XXX mcc: turn off for Leo (try to make this smaller!!) XXX
        #self.renderer.AddActor(self.scalarBar)
 
        self.do_scale_pipes = False 
        self.do_scale_pipes_with_coherence = True 
        self.pipes_scaling_factor = 0.2
    
    #self.entryAsciiFile = None    
    
          
    def markers_as_collection(self):
        markers = vtk.vtkActorCollection()
        for marker in self.markers:
            markers.AddItem(marker)
        return markers
    
    def set_scalar_data(self, datad):
        """
        **********************************************************************
        FUNC: set_scalar_data
        DESC: data d is a dict from (gname, gnum) -> scalar

        Plot the data on the grids using surface interpolation
        **********************************************************************
        """
        #return # XXX: mcc
        #print "GridManager.set_scalar_data(", datad, ")" #debug

        self.scalarVals.extend([val for key, val in datad.items()])
        if self.dimensiond is None:
            self.scalarSet.append(datad)
            return

        named = {}

        for tup, val in datad.items():
            gname, gnum = tup
            
            named.setdefault(gname, []).append((gnum, val))


        rangeSet = self.get_scalar_range()
        if rangeSet is not None:
            minVal, maxVal = rangeSet

        #print "calling scalarLookup setRange(%f, %f)"  % (minVal, maxVal)
        #self.scalarLookup = vtk.vtkLookupTable()
        #self.scalarLookup.SetRange(minVal, maxVal)
        #self.scalarBar.SetLookupTable(self.scalarLookup)
        
        for name in self.get_grid1_names():
            print "set_scalar_data: grid1_names: doing %s" % name
            items = named.get(name, None)
            if items is None: continue
            items.sort()

            polydata, actor, filter, markers = self.ribbons[name]
            if len(markers)!=len(items):
                if name not in self.gridWarned:
                    if (len(markers)<len(items)):
                        simple_msg('Missing some scalar data for grid %s.  %d markers and %d scalars' % (name, len(markers), len(items)))
                    else:
                        simple_msg('Too much scalar data for grid %s.  %d markers and %d scalars' % (name, len(markers), len(items)))
                self.gridWarned.add(name)

            scalars = vtk.vtkFloatArray()
            for num, val in items:
                #print "looking up self.vtkIDs[(%s, %d)]" % (name, num)
                try:
                    vtkID = self.vtkIDs[(name, num)]
                except Exception as inst:
                    simple_msg(inst)
                #print "scalars.InsertValue(%d, %f)" % (vtkID, val)
                scalars.InsertValue(vtkID, val)
            polydata.GetPointData().SetScalars(scalars)

            if rangeSet is not None:
                #pass
                #print "actor.GetMapper().SetScalarRange(%f, %f)" % (minVal, maxVal)
                actor.GetMapper().SetScalarRange(minVal, maxVal)

                self.scalarBar.VisibilityOn()
                self.scalarBar.SetLookupTable(actor.GetMapper().GetLookupTable())
                    

                
        for name in self.get_grid2_names():
            #print "set_scalar_data: grid2_names: doing %s" % name
            items = named.get(name, None)
            if items is None: continue
            #print "items is ", items
            items.sort()

            grid, actor, filter, markers = self.surfs[name]
            #print "got grid=", grid, "actor=", actor, "filter=", filter, "markers=", markers
            
            if len(markers)!=len(items):
                if name not in self.gridWarned:
                    if (len(markers)<len(items)):
                        simple_msg('Missing some scalar data for grid %s.  %d markers and %d scalars' % (name, len(markers), len(items)))
                    else:
                        simple_msg('Too much scalar data for grid %s.  %d markers and %d scalars' % (name, len(markers), len(items)))
                        
                self.gridWarned.add(name)


            scalars = vtk.vtkFloatArray()
            for num, val in items:
                #print "looking up self.vtkIDs[(%s, %d)]" % (name, num)
                vtkID = self.vtkIDs.get((name, num))
                if vtkID is None: continue
                #print "scalars.InsertValue(%d, %f)" % (vtkID, val)
                scalars.InsertValue(vtkID, val)
            #print "calling grid.GetPointData().SetScalars(", scalars, ")"
            
            grid.GetPointData().SetScalars(scalars)
            
            if rangeSet is not None:
                #print "doing rangeSet (??)"
                mapper = actor.GetMapper()
                #print "dude mapper is ", mapper
                if 1:
                    mapper.SetColorModeToMapScalars()
                    mapper.SetScalarRange(minVal, maxVal)
                else:
                    mapper.SetColorModeToMapScalars()
                    lut = mapper.GetLookupTable()
                    lut.SetRange(minVal, maxVal)
        self.interactor.Render()
            
    def flush(self):
        for actor in self.normalActors:
            self.renderer.RemoveActor(actor)
        for actor in self.gridActors.values():
            self.renderer.RemoveActor(actor)            
        for actor in self.markers:
            self.renderer.RemoveActor(actor)
        for actor in self.textActors:
            self.renderer.RemoveActor(actor)

        self.flush_connections()
            
        self.gridActors = {}  # dict from name -> grid or ribbon actors
        self.ribbons = {}  # dict from name -> ribbon actor
        self.surfs = {}    # dict from name -> surf actor
        self.normalActors = []
        self.markers = []
        self.textActors = []
        self.dimensiond = None
        self.scalarSet = []
        self.scalarVals = []
        self.interactor.Render()
        self.vtkIDs = {}
        
    def flush_connections(self):
        for actor in self.tubeActors:
            self.renderer.RemoveActor(actor)
        self.tubeActors = []
        
    def connect_markers(self, e1, e2, relHeight=0.25, lineWid=0.03,
                        scalarfunc=identity, radiusFactor=10):
        """
        Draw a line connecting electode1 with electrode2 (gname, gnum)
        tuples. scalarfunc sets the scalar values of the connecting
        arc as a function of the frac of distance between them (use
        none for homogenous line)
        """
        m1 = self.markerd.get(e1)
        m2 = self.markerd.get(e2)

        if m1 is None:  err = '%s %d' % e1
        elif m2 is None: err = '%s %d' % e2
        else: err = None
        if err is not None:
            error_msg('No marker with label %s' % err)
            return False
        
        p1 = array(m1.get_center())
        p2 = array(m2.get_center())
        d = dist(p1,p2)
        midp = 0.5*(p1+p2)

        try:
            n1 = m1.normal
            n2 = m2.normal
        except AttributeError: return False

        normal = 0.5*(n1+n2)
        vtk.vtkMath.Normalize(normal)

        p3 = midp + relHeight*d*normal
        #p3 = midp

        aSplineX = vtk.vtkCardinalSpline()
        aSplineY = vtk.vtkCardinalSpline()
        aSplineZ = vtk.vtkCardinalSpline()


        aSplineX.AddPoint(0, p1[0])
        aSplineX.AddPoint(1, p3[0])
        aSplineX.AddPoint(2, p2[0])

        aSplineY.AddPoint(0, p1[1])
        aSplineY.AddPoint(1, p3[1])
        aSplineY.AddPoint(2, p2[1])

        aSplineZ.AddPoint(0, p1[2])
        aSplineZ.AddPoint(1, p3[2])
        aSplineZ.AddPoint(2, p2[2])

        numInPnts = 3
        numOutPnts = 20

        # Interpolate x, y and z by using the three spline filters and
        # create new points
        points = vtk.vtkPoints()
        scalars = vtk.vtkFloatArray()

        for i in range(numOutPnts):
            t = (numInPnts-1.0)/(numOutPnts-1.0)*i
            points.InsertPoint(
                i, aSplineX.Evaluate(t), aSplineY.Evaluate(t), aSplineZ.Evaluate(t))
            if scalarfunc is not None:
                scalars.InsertTuple1(i,scalarfunc(t/(numInPnts-1.0)))

        # Create the polyline.
        lines = vtk.vtkCellArray()
        lines.InsertNextCell(numOutPnts)
        for i in range(numOutPnts):
            lines.InsertCellPoint(i)

        polyData = vtk.vtkPolyData()
        polyData.SetPoints(points)
        polyData.SetLines(lines)
        if scalarfunc is not None:
            polyData.GetPointData().SetScalars(scalars)

        # Add thickness to the resulting line.
        filter = vtk.vtkTubeFilter()
        filter.SetNumberOfSides(8)
        filter.SetInput(polyData)


        #if scalarfunc is not None:
        #    # Vary tube thickness with scalar
        #    filter.SetRadius(lineWid*m1.get_size())
        #    filter.SetRadiusFactor(radiusFactor)
        #    #filter.SetVaryRadiusToVaryRadiusByScalar()
        #else:
        #    filter.SetRadius(0.75*radiusFactor*lineWid*m1.get_size())

        radius_factor = 10
        if (self.do_scale_pipes_with_coherence == True):
            radius_factor = radiusFactor
        #print "grid_manager ", self.do_scale_pipes_with_coherence, self.do_scale_pipes, radius_factor
        if (self.do_scale_pipes == True):
            filter.SetRadius(0.75*radius_factor*lineWid*m1.get_size())
            print "m1.get_size() is ", m1.get_size()
            #print "do_scale_pipes == True, setting radius to %f" % (0.75*radiusFactor*lineWid*m1.get_size())
        else:
            #print "do_scale_pipes == False, setting radius to %f" % (0.75*radiusFactor*lineWid)
            #the math.pow in here is to scale the radii a little better so that we can make out the differences
            filter.SetRadius(((math.pow(radius_factor,2))/160)*lineWid*self.pipes_scaling_factor)

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInput(filter.GetOutput())
        #Set this to Off to turn off color variation with scalar
        if scalarfunc is not None:
            mapper.ScalarVisibilityOn()
            #mapper.SetScalarRange(0,t)   

        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetSpecular(.3)
        actor.GetProperty().SetSpecularPower(30)
        self.renderer.AddActor(actor)
        self.tubeActors.append(actor)
        
        return True
            
    def load_markers(self, infile):
        print "load_markers(", infile,")"
        self.flush()
        infile.seek(0)
        try: self.markers = [Marker.from_string(line) for line in infile]
        except ValueError:
            msg = exception_to_str('Could not parse marker file')
            error_msg(msg)
            return

        print "GridManager.load_markers(): loaded self.markers of length " , len(self.markers)
        
        
        self.markerd = dict([ (m.get_name_num(), m) for m in self.markers])

        print "GridManager.load_markers(): self.markerd=", self.markerd

        self._add_markers(self.markers)
            
        self.interactor.Render()

        if self.dlgDim is not None: self.dlgDim.destroy()
        if self.dlgProp is not None: self.dlgProp.destroy()

        self.dlgDim, self.dlgDimEntries = self.make_dim_dialog()
        self.dlgProp = self.make_prop_dialog()

        for datad in self.scalarSet:
            self.set_scalar_data(datad)
        self.renderer.ResetCamera()
        self.interactor.Render()

        return True

    def _add_markers(self, markers):
        textActors = []
        for marker in markers:
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
            camera = self.renderer.GetActiveCamera()
            textActor.SetCamera(camera)
            textActor.GetProperty().SetColor(marker.get_label_color())
            #textActor.VisibilityOff()
            textActors.append(textActor)

            self.renderer.AddActor(textActor)
            self.renderer.AddActor(marker)

        self.textActors = textActors

    def show(self, *args):
        self.dlgProp.show()

        # set defaults for scalar range

        tup = self.get_scalar_range()
        if tup is not None:
            minVal, maxVal = tup

            smin = self.entryScalarMin.get_text()
            if not smin:
                self.entryScalarMin.set_text('%1.2f'%minVal)
            smax = self.entryScalarMax.get_text()
            if not smin:
                self.entryScalarMax.set_text('%1.2f'%maxVal)


    def _update_frames(self):

        'Update the frames fo the main dialog'
        

        """
        #todo: change grid file is broken on the remove with
        (grid_manager_test.py:13237): Gtk-CRITICAL **: file
        gtkcontainer.c: line 981 (gtk_container_remove): assertion
        `widget->parent == GTK_WIDGET (container)' failed"""

        try: self.tableOpacity
        except AttributeError: pass
        else: self.frameOpacity.remove(self.tableOpacity)
        self.tableOpacity = self._make_opacity_table()
        self.frameOpacity.add(self.tableOpacity)

        try: self.vboxNormals
        except AttributeError: pass
        else: self.frameNormals.remove(self.vboxNormals)
        self.vboxNormals = self._make_normals_vbox()
        self.frameNormals.add(self.vboxNormals)

        # call this after normals vbox since we need to know about the
        # flip button
        try: self.tableAngle
        except AttributeError: pass
        else: self.frameAngle.remove(self.tableAngle)
        self.tableAngle = self._make_strip_angle_table()
        self.frameAngle.add(self.tableAngle)

    def get_scalar_range(self):

        minVal, maxVal = None, None
        
        if len(self.scalarVals): 
            minVal = min(self.scalarVals)
            maxVal = max(self.scalarVals)
            
        smin = self.entryScalarMin.get_text()
        smax = self.entryScalarMax.get_text()
        if len(smin):
            try: minVal = float(smin)
            except ValueError:
                error_msg('Illegal floating point value "%s" for minimum scalar range.  Please fix it in the preferences dialog'%smin)
                return
        if len(smax):
            try: maxVal = float(smax)
            except ValueError:
                error_msg('Illegal floating point value "%s"for maximum scalar range.  Please fix it in the preferences dialog'%smax)
                return

        if minVal is None or maxVal is None: return None
        return minVal, maxVal
        
    def make_prop_dialog(self):

        
        if self.dimensiond is None:
            results = self.get_dimensions()

        def hide(*args):
            dlg.hide()
            return True
        dlg = gtk.Dialog('Grid properties')
        # intercept delete events
        dlg.connect('delete_event', hide)
        
        notebook = gtk.Notebook()
        notebook.show()
        dlg.vbox.pack_start(notebook, True, True)

        frame = gtk.Frame('Strip angle')
        frame.show()
        frame.set_border_width(5)
        label = gtk.Label('Strips')
        label.show()
        notebook.append_page(frame, label)
        self.frameAngle = frame

        frame = gtk.Frame('Grid normals')
        frame.show()
        frame.set_border_width(5)
        label = gtk.Label('Normals')
        label.show()
        notebook.append_page(frame, label)
        self.frameNormals = frame
        
        
        frame = gtk.Frame('Opacity')
        frame.show()
        frame.set_border_width(5)
        label = gtk.Label('Opacity')
        label.show()
        notebook.append_page(frame, label)
        self.frameOpacity = frame


        
        vboxMappers = gtk.VBox()
        vboxMappers.show()
        label = gtk.Label('Scalar data')
        label.show()
        notebook.append_page(vboxMappers, label)
        
        frame = gtk.Frame('Scalar Range')
        frame.show()
        frame.set_border_width(5)
        vboxMappers.pack_start(frame, False, False)

        frameVBox = gtk.VBox()
        frameVBox.show()
        frameVBox.set_spacing(3)
        frame.add(frameVBox)


        hbox = gtk.HBox()
        hbox.set_spacing(3)
        hbox.show()
        frameVBox.pack_start(hbox, False, False)
        
        label = gtk.Label('Min/Max')
        label.show()
        
        hbox.pack_start(label, False, False)


        self.entryScalarMin = gtk.Entry()
        self.entryScalarMin.show()
        self.entryScalarMin.set_width_chars(10)
        hbox.pack_start(self.entryScalarMin, False, False)

        
        self.entryScalarMax = gtk.Entry()
        self.entryScalarMax.show()
        self.entryScalarMax.set_width_chars(10)
        hbox.pack_start(self.entryScalarMax, False, False)


        hbox = gtk.HBox()
        hbox.set_spacing(3)
        hbox.show()
        frameVBox.pack_start(hbox, False, False)

        def set_range(button):
            tup = self.get_scalar_range()
            if tup is None: return
            minVal, maxVal = tup

            for grid, actor, filter, markers in self.surfs.values():
                actor.GetMapper().SetScalarRange(minVal, maxVal)
            for polydata, actor, filter, markers in self.ribbons.values():
                actor.GetMapper().SetScalarRange(minVal, maxVal)
            self.interactor.Render()
            
                
        button = gtk.Button(stock=gtk.STOCK_APPLY)
        button.show()
        hbox.pack_start(button, True, True)
        button.connect('clicked', set_range)

        def autoset(button):
            if not len(self.scalarVals):
                error_msg('No scalar data set')
                return
            
            minVal = min(self.scalarVals)
            maxVal = max(self.scalarVals)
            self.entryScalarMin.set_text('%1.2f'%minVal)
            self.entryScalarMax.set_text('%1.2f'%maxVal)
            set_range(None)
            
        button = ButtonAltLabel('Auto', gtk.STOCK_EXECUTE)
        button.show()
        button.connect('clicked', autoset)
        hbox.pack_start(button, True, True)

        frame = gtk.Frame('Scalars from ASCII file')
        frame.show()
        frame.set_border_width(5)
        vboxMappers.pack_start(frame, False, False)

        frameVBox = gtk.VBox()
        frameVBox.show()
        frameVBox.set_spacing(3)
        frame.add(frameVBox)

        def load_ascii_data(filename):
            print "GridManager.load_ascii_data()"
            try: fh = file(filename)
            except IOError, msg:
                msg = exception_to_str('Could not open %s' % filename)
                error_msg(msg, parent=dlg)
                return

            try:
                numHeaderLines = str2int_or_err(
                    entryHeader.get_text(), labelHeader, parent=dlg)
                print "load_ascii_data(): numHeaderLines is " , numHeaderLines
                if numHeaderLines is None: return

                # skip the header lines
                for i in range(numHeaderLines):
                    fh.readline()
                    #print "load_ascii_data(): read line"

                X = []
                for line in fh:
                    #print "load_ascii_data(): considering line ", line
                    vals = [float(val) for val in line.split()]
                    #print "load_ascii_data(): vals are ", vals
                    X.append(vals)
            except ValueError:
                print "Found uncharacteristic line in .dat file, perhaps not all numbers?"
                msg = exception_to_str('Error parsing %s' % filename)
                error_msg(msg, parent=dlg)
                return
            if int(entryPercent.get_text()) == 0:
                prop_to_zero = 10000000
            else:
                prop_to_zero = 100/int(entryPercent.get_text()) #user input percent to zero
            if buttonSampChan.get_active():
                # transpose the data to channels x samples
                X = array(zip(*X), 'd')
                # zero out the first 50 ms of X
                print "X.shape is ", X.shape
                torep = int(X.shape[1]/prop_to_zero) #a proportion of the rows will be zerod
                print "torep is: ", torep
                xrep = np.zeros([X.shape[0], torep]) #rows by same num of columns
                print "xrep.shape is ", xrep.shape
                xold = X[:][:,torep+1:] #X without the affected rows
                print "xold.shape is ", xold.shape
                xnew = np.concatenate((xrep,xold), axis=1) #stack xrep on top of xold
                print "xnew.shape is ", xnew.shape
                X = xnew
            else:
                X = array(X, 'd')
                # zero out the first 50 ms of X
                print "X.shape is ", X.shape
                torep = int(X.shape[0]/prop_to_zero) #a proportion of the rows will be zerod
                print "torep is: ", torep
                xrep = np.zeros([torep, X.shape[1]]) #rows by same num of columns
                print "xrep.shape is ", xrep.shape
                xold = X[:,torep+1:][:] #X without the affected rows
                print "xold.shape is ", xold.shape
                xnew = np.concatenate((xrep,xold), axis=0) #stack xrep on top of xold
                print "xnew.shape is ", xnew.shape
                X = xnew
                
            numChannels, numSamples = X.shape
            self.X = X

            # instead of loading this amp dialog, load a .amp file
            # code copied from view3 -- XXX

            print "Loading amp file.."
            if fmanager.amp == "" or fmanager.amp == " ": #retooled for streamlining using .eegviewrc file
                amp_filename = fmanager.get_filename(title="Select .amp file")
                if amp_filename is None: return
            else:
                amp_filename = fmanager.amp
                while not os.path.exists(amp_filename):
                    error_msg('File %s in .eegviewrc does not exist' % amp_filename, parent=dlg)
                    fmanager.amp = ""
                    amp_filename = fmanager.get_filename(title="Select .amp file")

            try: fh = file(amp_filename)
            except IOError, msg:
                msg = exception_to_str('Could not open %s' % amp_filename)
                error_msg(msg)
                return

            def parse_amp_file(fh):
                amp_list = []
                while 1:
                    line = fh.readline().strip()
                    #print "parse_amp_file(): line='%s'" % line
                    if (line == None):
                        break
                    if (line == ''):
                        break
                    if (line[0] == '#'):
                        continue
                    # every line should be like
                    # [int] [letters] [int]
                    # e.g. 1 FG 4
                    vals = line.split()
                    #print vals
                    if (len(vals) == 1):
                        # empty channel.. ignore
                        print "parse_amp_file(): ignoring empty line ", vals
                        continue
                    if (len(vals) != 3):
                        raise RuntimeError, 'Bad .amp file on line %s' % line
                    # ok now make sure this channel is in self.eoi, otherwise
                    # we don't want to try to plot that Cxy value later

                    electrode = (vals[1], int(vals[2]))
                    # XXX no eoi checking
                    #if electrode not in self.eoi:
                    #    print "skipping electrode ", electrode, ": not in self.eoi"
                    #    continue
                    amp_list.append((int(vals[0]),vals[1], int(vals[2])))
                    #print "amp_list is ", amp_list
                fh.close()
                return amp_list
        
            amplist_from_file = parse_amp_file(fh)
            amp = Amp()
            amp.set_channels(amplist_from_file)
        
            #ampDlg = AmpDialog([(i+1) for i in range(numChannels)])
            #ampDlg.show()
            #amp = ampDlg.get_amp()
            
            if amp is None: return
            print "setting ampAscii to amp, amp= ", amp
            self.ampAscii = amp
           
        def set_filename(button):
            if fmanager.dat == "" or fmanager.dat == " ": #retooled for streamlining
                filename = fmanager.get_filename(title="Select .dat file")
                if filename is None: return
            else:
                filename = fmanager.dat
                if not os.path.exists(filename):
                    error_msg('File %s does not exist' % filename, parent=dlg)
                    fmanager.dat = ""
                    filename = fmanager.dat
                    return
            entryAsciiFile.set_text(filename)
            load_ascii_data(filename)
        
        self.addview3 = False #toggle for whether to add arraymapper output to view3 window
        
        def doit(button):
            s = entryChannels.get_text()
            if not len(s):
                simple_msg('Please select channels: format like 1 2 3',
                           parent=dlg)
                return
        
            try: channels = [int(val) for val in s.split()]
            except ValueError:
                error_msg('Could not convert %s to a list of integers.  Use format like: 1 12 54' % s, parent=dlg)
                return

            filename = entryAsciiFile.get_text()
            if not filename:
                error_msg('You must first set the filename', parent=dlg)
                return

            
            if self.ampAscii is None:
                error_msg('No valid channel->electrode map', parent=dlg)
                return
            if not len(self.X):
                error_msg('No ascii data loaded', parent=dlg)
                return

            start_time_str = entry_start_time.get_text()
            end_time_str = entry_end_time.get_text()
            start_time = None
            end_time=None
            print "specified start time is ", start_time_str
            print "specified end time is ", end_time_str
            if ((start_time_str != '') & (end_time_str != '')):
                start_time = float(start_time_str)
                end_time = float(end_time_str)

            # mcc: look at self.ampAscii and make sure that the named grids correspond
            # to actual grids in the gridmanager
            
            grid1_names = self.get_grid1_names()
            grid2_names = self.get_grid2_names()

            for index1, curr_grid_name, index2 in self.ampAscii:
                if ((curr_grid_name not in grid1_names) & (curr_grid_name not in grid2_names)):
                    grid_names = ', ' . join(['%s ' % key for key in grid1_names]) + ', '
                    grid_names += (', ' . join(['%s ' % key for key in grid2_names]))
                    error_msg('key %s not in list of grid names: %s' % (curr_grid_name, grid_names))
                    return
            
            am = ArrayMapper(self, self.X, channels, self.ampAscii, self.addview3, self.view3, start_time=start_time, end_time=end_time)
            #here, we'll try to preemptively load a colormap if the .eegviewrc file has been set.
            self.set_custom_colormap()
            
            am.show()

        def radio_changed(button):
            filename = entryAsciiFile.get_text()
            if not filename:
                set_filename(button=None)
            else:
                load_ascii_data(filename)
        
               
        def view3_add(button):
            if self.addview3 == False:
                self.addview3 = True
            else:
                self.addview3 = False
                
        radioGrp = None
        button = gtk.RadioButton(radioGrp)
        button.set_label('Samples x Channels')
        button.set_active(True)
        button.show()
        button.connect('clicked', radio_changed)
        frameVBox.pack_start(button, True, True)
        buttonSampChan = button
        
        button = gtk.RadioButton(button)
        button.set_label('Channels x Samples')
        button.show()
        frameVBox.pack_start(button, True, True)
        buttonChanSamp = button

        hbox = gtk.HBox()
        hbox.show()
        hbox.set_spacing(3)
        frameVBox.pack_start(hbox, True, True)

        label = gtk.Label('Header lines')
        label.show()
        labelHeader = label
        hbox.pack_start(label, False, False)
        entry = gtk.Entry()
        entry.show()
        entry.set_text('0')
        entry.set_width_chars(5)
        hbox.pack_start(entry, False, False)
        entryHeader = entry
        
        label = gtk.Label('% to zero on file open')
        label.show()
        hbox.pack_start(label,False,False)
        entry = gtk.Entry()
        entry.show()
        entry.set_text('5')
        entry.set_width_chars(2)
        hbox.pack_start(entry, False, False)
        entryPercent = entry
        entryPercent.connect('changed', numbify)

        hbox = gtk.HBox()
        hbox.show()
        hbox.set_spacing(3)
        frameVBox.pack_start(hbox, True, True)

        label = gtk.Label('Channels')
        label.show()
        hbox.pack_start(label, False, False)
        entry = gtk.Entry()
        entry.show()
        entry.set_text('1 2 3')
        hbox.pack_start(entry, False, False)
        entryChannels = entry
        
        button = gtk.CheckButton('Add to View3')
        button.show()
        button.set_active(False)
        hbox.pack_start(button, False, False)
        button.connect('clicked', view3_add)

        hbox = gtk.HBox()
        hbox.show()
        hbox.set_spacing(3)
        frameVBox.pack_start(hbox, True, True)

        self.ampAscii = None
        self.X = []

            
        button = gtk.Button(stock=gtk.STOCK_OPEN)
        button.show()
        button.connect('clicked', set_filename)
        hbox.pack_start(button, False, False)
        entry = gtk.Entry()
        entry.show()
        hbox.pack_start(entry, True, True)
        entryAsciiFile = entry
        


        hbox = gtk.HBox()
        hbox.show()
        hbox.set_spacing(3)
        frameVBox.pack_start(hbox, True, True)

        label = gtk.Label('data start time and total len in ms (opt.)')
        label.show()
        labelHeader = label
        hbox.pack_start(label, False, False)

        entry = gtk.Entry()
        entry.show()
        entry.set_text('0')
        entry.set_width_chars(5)
        hbox.pack_start(entry, False, False)
        entry_start_time = entry
        entry = gtk.Entry()
        entry.show()
        entry.set_text(str((self.view3.NFFT/self.view3.eeg.freq) * 1000))
        entry.set_width_chars(5)
        hbox.pack_start(entry, False, False)
        entry_end_time = entry

        
        button = gtk.Button(stock=gtk.STOCK_EXECUTE)
        button.show()
        frameVBox.pack_start(button, True, True)
        button.connect('clicked', doit)

            

        
        frame = gtk.Frame('Markers')
        frame.show()
        frame.set_border_width(5)
        label = gtk.Label('Markers')
        label.show()
        notebook.append_page(frame, label)


        frameVBox = gtk.VBox()
        frameVBox.show()
        frameVBox.set_spacing(3)
        frame.add(frameVBox)


        table = gtk.Table(1,3)
        table.set_homogeneous(False)
        table.show()
        frameVBox.pack_start(table, False, False)
        
        table.set_col_spacings(3)
        table.set_row_spacings(3)
        table.set_border_width(3)


        row = 0
        label = gtk.Label('Markers size')
        label.show()


        scrollbar = gtk.HScrollbar()
        scrollbar.show()
        scrollbar.set_range(0, 1)
        scrollbar.set_increments(0.01,0.1)
        scrollbar.set_value(0.2)

        def set_size(bar):
            val = bar.get_value()
            for marker in self.markers:
                marker.set_size(val)
            self.interactor.Render()
            # do something
        scrollbar.connect('value_changed', set_size)
        scrollbar.set_size_request(*self.SCROLLBARSIZE)
        table.attach(label, 0, 1, row, row+1,
                     xoptions=gtk.EXPAND, yoptions=gtk.EXPAND)
        table.attach(scrollbar, 1, 2, row, row+1,
                     xoptions=gtk.FILL, yoptions=gtk.EXPAND)

        row = row +1

        label2 = gtk.Label('Pipes width')
        label2.show()

        scrollbar2 = gtk.HScrollbar()
        scrollbar2.show()
        scrollbar2.set_range(0, 4)
        scrollbar2.set_increments(0.01,0.1)
        scrollbar2.set_value(0.2)

        def set_pipes_size(bar):
            #print "set_pipes_size(", bar.get_value, ")"
            val = bar.get_value()
            self.pipes_scaling_factor = val
            #self.interactor.Render()
            # do something
            
        scrollbar2.connect('value_changed', set_pipes_size)
        scrollbar2.set_size_request(*self.SCROLLBARSIZE)
        table.attach(label2, 0, 1, row, row+1,
                     xoptions=gtk.EXPAND, yoptions=gtk.EXPAND)
        table.attach(scrollbar2, 1, 2, row, row+1,
                     xoptions=gtk.FILL, yoptions=gtk.EXPAND)


        button = gtk.CheckButton('Pipes scale with marker size')
        button.show()
        button.set_active(False)
        frameVBox.pack_start(button, False, False)
        def scale_pipes(button):
            if not button.get_active():
                self.do_scale_pipes = False
            else:
                self.do_scale_pipes = True
        button.connect('clicked', scale_pipes)

        button = gtk.CheckButton('Pipes scale with coherence values')
        button.show()
        button.set_active(True)
        frameVBox.pack_start(button, False, False)
        def scale_pipes_with_coherence(button):
            if not button.get_active():
                self.do_scale_pipes_with_coherence = False
            else:
                self.do_scale_pipes_with_coherence = True
        button.connect('clicked', scale_pipes_with_coherence)



        def markers_openhook(infile):
            try: self.load_markers(infile)
            except:
                msg = exception_to_str('Error parsing marker file %s' % hboxFile.filename)
                error_msg(msg, parent=dlg)
                return False
            else:
                return True



        def markers_savehook(outfile):
            try:
                for marker in self.markers:
                    outfile.write(marker.to_string() + '\n')
            except:
                msg = exception_to_str('Could not write markers to %s' % hboxFile.filename)
                error_msg(msg, parent=dlg)
                return
            else:
                return True

        hboxFile = OpenSaveSaveAsHBox(
            fmanager, markers_openhook, markers_savehook, parent=dlg)
        hboxFile.show()
        frameVBox.pack_start(hboxFile, False, False)

        ## XXX mcc color map stuff
        frame = gtk.Frame('Colormaps')
        frame.show()
        frame.set_border_width(5)

        label = gtk.Label('Colormaps')
        label.show()
        notebook.append_page(frame, label)

        
        frameVBox = gtk.VBox()
        frameVBox.show()
        frameVBox.set_spacing(3)
        frame.add(frameVBox)

        label = gtk.Label('Surface colormap')
        frameVBox.pack_start(label)
        combo1 = gtk.combo_box_new_text()
        combo1.append_text('hot')
        combo1.append_text('original')
        combo1.append_text('custom')
        combo1.set_active(1)
        frameVBox.pack_start(combo1)
        """
        def parse_colormap_textfile(colormap_filename):
            if colormap_filename is None: return
            if not os.path.exists(colormap_filename):
                error_msg('File %s does not exist' % colormap_filename, parent=dlg)
                return
            fh = open(colormap_filename)
            custom_colormap = zeros((256, 4), 'd')
            i = 0
            while 1:
                line = fh.readline().strip()
                print "colormap line='%s'" % line
                
                if (line == ''):
                    break

                foo = line.split('\t')
                custom_colormap[i] = map(float,foo)
                i = i+ 1
            print "yo custom_colormap=", custom_colormap
            return custom_colormap
        """
        def change_colormap_surf(combo):
            print "!! change_colormap(): combo=", combo
            if (combo.get_active() == 0):
                print "change to hot"
                for name in self.get_grid2_names():
                    grid, actor, filter, markers = self.surfs[name]
                    mapper = actor.GetMapper()
                    lut = mapper.GetLookupTable()
                    print "lut is ", lut
                    for i in range(0,128):
                        #lut.SetTableValue(i, [float(i)/256.0, 1.0-(float(i)/256.0), 0.0, 1.0])
                        lut.SetTableValue(i, [1.0, 1.0-(float(i)/256.0), 0.0, 1.0])
                    for i in range(128,256):
                        #lut.SetTableValue(i, [float(i)/256.0, 1.0-(float(i)/256.0), 0.0, 1.0])
                        lut.SetTableValue(i, [1.0, 1.0-(float(i)/256.0), 0.0, 1.0])
                    lut.Build()
                    mapper.SetLookupTable(lut)
                self.interactor.Render() 
            elif (combo.get_active() == 1):
                print "change to original"
                for name in self.get_grid2_names():
                    grid, actor, filter, markers = self.surfs[name]
                    mapper = actor.GetMapper()
                    lut = vtk.vtkLookupTable()
                    lut.SetHueRange(0.667, 0.0)
                    mapper.SetLookupTable(lut)
                self.interactor.Render() 
            elif (combo.get_active() == 2):
                print "loading custom map"
                if fmanager.col == "" or fmanager.col == " ":
                    colormap_filename = fmanager.get_filename()
                else:
                    colormap_filename = fmanager.col
                    print "colormap_filename is " , colormap_filename
                    if not os.path.exists(colormap_filename):
                        colormap_filename = fmanager.get_filename()
                    if colormap_filename is None: 
                        return
                
                custom_colormap = self.parse_colormap_textfile(colormap_filename)

                for name in self.get_grid2_names():
                    grid, actor, filter, markers = self.surfs[name]
                    mapper = actor.GetMapper()

                    lut = vtk.vtkLookupTable()
                    for i in range(0, 256):
                        lut.SetTableValue(i, custom_colormap[i])
                    lut.Build()
                
                    mapper.SetLookupTable(lut)

                    
                self.interactor.Render()
                        
                
        def change_colormap_pipes(combo):
            print "!! change_colormap(): combo=", combo
            if (combo.get_active() == 0):
                print "change to hot"
                for actor in self.tubeActors:
                    mapper = actor.GetMapper()
                    lut = mapper.GetLookupTable()
                    print "lut is ", lut
                    for i in range(0,128):
                        #lut.SetTableValue(i, [float(i)/256.0, 1.0-(float(i)/256.0), 0.0, 1.0])
                        lut.SetTableValue(i, [1.0, 1.0-(float(i)/256.0), 0.0, 1.0])
                    for i in range(128,256):
                        #lut.SetTableValue(i, [float(i)/256.0, 1.0-(float(i)/256.0), 0.0, 1.0])
                        lut.SetTableValue(i, [1.0, 1.0-(float(i)/256.0), 0.0, 1.0])
                    lut.Build()
                    mapper.SetLookupTable(lut)
                
                self.interactor.Render() 
            elif (combo.get_active() == 1):
                print "change to original"

                for actor in self.tubeActors:
                    mapper = actor.GetMapper()
                    lut = vtk.vtkLookupTable()
                    lut.SetHueRange(0.667, 0.0)
                    mapper.SetLookupTable(lut)
                    self.interactor.Render() 

                
                self.interactor.Render()
                
            elif (combo.get_active() == 2):
                print "loading custom map a la Leo"
                colormap_filename = fmanager.get_filename()
                print "colormap_filename is " , colormap_filename
                if colormap_filename is None: return

                custom_colormap = parse_colormap_textfile(colormap_filename)

                for actor in self.tubeActors:
                    mapper = actor.GetMapper()
                    lut = vtk.vtkLookupTable()
                    for i in range(0, 256):
                        lut.SetTableValue(i, custom_colormap[i])
                    lut.Build()
                
                    mapper.SetLookupTable(lut)
                    
                    
                self.interactor.Render()
                        
                
        label = gtk.Label('Pipes colormap')
        frameVBox.pack_start(label)
        combo2 = gtk.combo_box_new_text()
        combo2.append_text('hot')
        combo2.append_text('original')
        combo2.append_text('custom')
        combo2.set_active(1)
        frameVBox.pack_start(combo2)

        #def show_white_pipes(button):
        #    if not button.get_active():
        #        # turn off white pipes
        #        return
        #    else:
        #        # turn em on
        #        return
        #button = gtk.CheckButton('Show white pipes')
        #button.show()
        #button.set_active(True)
        #frameVBox.pack_start(button, False, False)
        #button.connect('clicked', show_white_pipes)


        
        combo1.connect("changed", change_colormap_surf)
        combo2.connect("changed", change_colormap_pipes)

        frameVBox.show_all()
        
        
        

                    
        hbox = gtk.HBox()
        hbox.show()
        dlg.vbox.pack_start(hbox, False, False)

        def hide(button):
            dlg.hide()

        button = ButtonAltLabel('Hide', gtk.STOCK_CANCEL)
        button.show()
        button.connect('clicked', hide)
        hbox.pack_start(button, True, True)        

        self._update_frames()
        notebook.set_current_page(2)        
    #if not (fmanager.dat == "" or fmanager.dat == " "):
    #    entryAsciiFile.set_text(fmanager.dat)
    #    load_ascii_data(fmanager.dat)
    
        return dlg


        
    def show_normals(self, button):

        for actor in self.normalActors:
            self.renderer.RemoveActor(actor)
            
        self.normalActors = []


        if not button.get_active():
            self.interactor.Render()
            return
        
        for marker in self.markerd.values():
            if not hasattr(marker, 'normal'): continue
            lineSource = vtk.vtkLineSource()
            xyz = array(marker.get_center())
            lineSource.SetPoint1(xyz)
            pnt2 = array(xyz) + marker.normal
            lineSource.SetPoint2(pnt2)
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInput(lineSource.GetOutput())
            actor = vtk.vtkActor()
            actor.SetMapper(mapper)
            self.renderer.AddActor(actor)
            self.normalActors.append(actor)
        
        self.interactor.Render()
            
    def _make_normals_vbox(self):
        vbox = gtk.VBox()
        vbox.show()

        button = gtk.CheckButton('Show normals')
        button.show()
        button.set_active(False)
        vbox.pack_start(button, False, False)
        button.connect('clicked', self.show_normals)
        self.buttonShowNormals = button

        class FlipNormals:
            def __init__(self, parent, markers, filter, button):
                self.parent = parent
                self.button = button
                self.markers = markers
                self.filter = filter
                
            def __call__(self, *args):
                flip = self.button.get_active()
                self.parent.set_normals_grid2(self.markers, self.filter, flip)
                self.parent.show_normals(self.parent.buttonShowNormals)
                
        self.buttonsFlip = {}


        for name in self.get_grid2_names():
            grid, actor, filter, markers = self.surfs[name]
            button = gtk.CheckButton('Flip %s normals' % name)
            button.show()
            button.set_active(False)
            vbox.pack_start(button, False, False)
            func = FlipNormals(self, markers, filter, button)
            button.connect('clicked', func)
            self.buttonsFlip[name] = button

        return vbox
        
    def _make_opacity_table(self):
        names = self.get_grid_names()

        table = gtk.Table(len(names)+5,2) #I've added a bar at the bottom for the vtk brainmesh -e
        table.set_homogeneous(False)
        table.show()
        table.set_col_spacings(3)
        table.set_row_spacings(3)
        table.set_border_width(3)



        row = 0
        label = gtk.Label('Markers')
        label.show()


        scrollbar = gtk.HScrollbar()
        scrollbar.show()
        scrollbar.set_range(0, 1)
        scrollbar.set_increments(0.05,0.25)
        scrollbar.set_value(1)

        def set_marker_opacity(bar):
            val = bar.get_value()
            for marker in self.markers:
                marker.GetProperty().SetOpacity(val)
            self.interactor.Render()
            
        scrollbar.connect('value_changed', set_marker_opacity)
        scrollbar.set_size_request(*self.SCROLLBARSIZE)

        table.attach(label, 0, 1, row, row+1,
                     xoptions=gtk.EXPAND, yoptions=gtk.EXPAND)
        table.attach(scrollbar, 1, 2, row, row+1,
                     xoptions=gtk.FILL, yoptions=gtk.EXPAND)
        row+=1

        label = gtk.Label('Labels')
        label.show()
        scrollbar = gtk.HScrollbar()
        scrollbar.show()
        scrollbar.set_range(0, 1)
        scrollbar.set_increments(0.05,0.25)
        scrollbar.set_value(1)

        def set_label_opacity(bar):
            val = bar.get_value()
            for actor in self.textActors:
                actor.GetProperty().SetOpacity(val)
            self.interactor.Render()
            
        scrollbar.connect('value_changed', set_label_opacity)
        scrollbar.set_size_request(*self.SCROLLBARSIZE)

        table.attach(label, 0, 1, row, row+1,
                     xoptions=gtk.EXPAND, yoptions=gtk.EXPAND)
        table.attach(scrollbar, 1, 2, row, row+1,
                     xoptions=gtk.FILL, yoptions=gtk.EXPAND)
        
        row += 1


        label = gtk.Label('Pipes')
        label.show()
        scrollbar = gtk.HScrollbar()
        scrollbar.show()
        scrollbar.set_range(0, 1)
        scrollbar.set_increments(0.05,0.25)
        scrollbar.set_value(1)

        def set_pipe_opacity(bar):
            val = bar.get_value()
            for actor in self.tubeActors:
                actor.GetProperty().SetOpacity(val)
            self.interactor.Render()
            
        scrollbar.connect('value_changed', set_pipe_opacity)
        scrollbar.set_size_request(*self.SCROLLBARSIZE)

        table.attach(label, 0, 1, row, row+1,
                     xoptions=gtk.EXPAND, yoptions=gtk.EXPAND)
        table.attach(scrollbar, 1, 2, row, row+1,
                     xoptions=gtk.FILL, yoptions=gtk.EXPAND)
        row += 1

        self.opacityBarsDict = {}

        class SetOpacity:
            def __init__(self, prop, bar, interactor):
                self.prop = prop
                self.bar = bar
                self.renderOn = True
                self.interactor = interactor
                
            def __call__(self, *args):                
                val = self.bar.get_value()
                #print "_make_opacity_table.SetOpacity.__call__(): prop" , self.prop, ".SetOpacity(", val, ")"
                self.prop.SetOpacity(val)                
                if self.renderOn:
                    self.interactor.Render()    
        funcs = []

        
        for i, name in enumerate(names):
            label = gtk.Label(name)
            label.show()

            actor = self.gridActors[name]
            prop = actor.GetProperty()

            
            scrollbar = gtk.HScrollbar()
            scrollbar.show()
            scrollbar.set_range(0, .99)
            scrollbar.set_value(.99)
            func = SetOpacity(prop, scrollbar, self.interactor)
            scrollbar.connect('value_changed', func)
            scrollbar.set_size_request(*self.SCROLLBARSIZE)
            scrollbar.set_increments(0.05,0.25)
            self.opacityBarsDict[name] = scrollbar
            table.attach(label, 0, 1, row, row+1,
                         xoptions=gtk.EXPAND, yoptions=gtk.EXPAND)
            table.attach(scrollbar, 1, 2, row, row+1,
                         xoptions=gtk.FILL, yoptions=gtk.EXPAND)
            row += 1
            funcs.append(func)

        label = gtk.Label('All')
        label.show()


        def set_opacity(bar):
            val = bar.get_value()
            for func in funcs: func.renderOn = False

            for bar in self.opacityBarsDict.values():
                bar.set_value(val)
            for func in funcs: func.renderOn = True
            self.interactor.Render()

        scrollbar = gtk.HScrollbar()
        scrollbar.show()
        scrollbar.set_range(0, .99)
        scrollbar.set_increments(0.05,0.25)
        scrollbar.set_value(.99)
        scrollbar.connect('value_changed', set_opacity)
        scrollbar.set_size_request(*self.SCROLLBARSIZE)

        table.attach(label, 0, 1, row, row+1,
                     xoptions=gtk.EXPAND, yoptions=gtk.EXPAND)
        table.attach(scrollbar, 1, 2, row, row+1,
                     xoptions=gtk.FILL, yoptions=gtk.EXPAND)
        row += 1
        print "mminactive", self.meshManager
        #this last bit controls the vtk brainmesh opacity
        
        label = gtk.Label('Brain Mesh')
        label.show()
        
        def mesh_opacity(bar):
            val = bar.get_value()
            if self.meshManager:
                self.meshManager.contours.GetProperty().SetOpacity(val)
                self.interactor.Render()
            else:
                simple_msg("Mesh manager not yet loaded.")
                
        scrollbar = gtk.HScrollbar()
        scrollbar.show()
        scrollbar.set_range(0, .99)
        scrollbar.set_increments(0.05,0.25)
        scrollbar.set_value(.99)
        scrollbar.connect('value_changed', mesh_opacity)
        scrollbar.set_size_request(*self.SCROLLBARSIZE)

        table.attach(label, 0, 1, row, row+1,
                     xoptions=gtk.EXPAND, yoptions=gtk.EXPAND)
        table.attach(scrollbar, 1, 2, row, row+1,
                     xoptions=gtk.FILL, yoptions=gtk.EXPAND)
        row += 1
        

        return table

    def _make_strip_angle_table(self):
        # call this after normal table built since we need to know the
        # flip state
        names = self.get_grid1_names()

        table = gtk.Table(len(names),2)
        table.set_homogeneous(False)
        table.show()
        table.set_col_spacings(3)
        table.set_row_spacings(3)
        table.set_border_width(3)


        class SetAngle:
            def __init__(self, parent, name, scrollbar):
                self.name = name
                self.parent = parent
                polydata, actor, self.filter, self.markers = parent.ribbons[self.name]
                self.bar = scrollbar
                
            def __call__(self, *args):                
                val = self.bar.get_value()
                self.filter.SetAngle(val)
                self.parent.set_normals_grid1(self.markers, self.filter)
                self.parent.interactor.Render()    

        for i, name in enumerate(names):
            label = gtk.Label(name)
            label.show()


            scrollbar = gtk.HScrollbar()
            scrollbar.show()
            scrollbar.set_range(0, 360)
            scrollbar.set_value(0)

            plydata, actor, filter, markers = self.ribbons[name]
            func = SetAngle(self, name, scrollbar)

            scrollbar.connect('value_changed', func)
            scrollbar.set_size_request(*self.SCROLLBARSIZE)
            scrollbar.set_increments(5,10)
            table.attach(label, 0, 1, i, i+1,
                         xoptions=gtk.EXPAND, yoptions=gtk.EXPAND)
            table.attach(scrollbar, 1, 2, i, i+1,
                         xoptions=gtk.FILL, yoptions=gtk.EXPAND)

        return table
        
        
    def update_actors(self):

        for actor in self.gridActors.values():
            self.renderer.RemoveActor(actor)

        if self.dimensiond is None: return
        self.ribbons = {}  # dict from name -> ribbon actor
        self.surfs = {}    # dict from name -> surf actor
        
        for name in self.get_grid1_names():
            polydata, ribbon, filter, markers = self.make_strip_ribbon(name)
            self.ribbons[name]= polydata, ribbon, filter, markers
            self.gridActors[name]= ribbon

        for name in self.get_grid2_names():
            grid, surf, filter, markers = self.make_grid_surf(name)
            self.surfs[name] = grid, surf, filter, markers
            self.gridActors[name]= surf

        for actor in self.gridActors.values():
            self.renderer.AddActor(actor)

        self.interactor.Render()
        
    def get_grid_names(self):
        'Return a sorted list of grid names in markerd'
        d = dict([ (label[0],1) for label, trode in self.markerd.items()])
        names = d.keys()
        names.sort()
        return names

    def get_grid1_names(self):
        'Return the names of the Nx1 by grids'        
        names = []
        for name, tup in self.dimensiond.items():
            numrows, numcols = tup
            if numrows==1 or numcols==1:
                names.append(name)

        names.sort()            
        return names

    def get_grid2_names(self):
        'Return the names of the NxM'        
        names = []
        for name, tup in self.dimensiond.items():
            numrows, numcols = tup
            if numrows>1 and numcols>1:
                names.append(name)

        names.sort()            
        return names

    def make_dim_dialog(self):

        dlg = gtk.Dialog('Grid Dimensions')
        
        gridNames = self.get_grid_names()
        

        vbox = dlg.vbox
        entries = {}

        # make a dict from grid name to electrodes in grid
        named = {}
        for key, val in self.markerd.items():
            gname, gnum = key
            named.setdefault(gname, []).append( (gname, gnum) )

        table = gtk.Table( 4, len(gridNames))
        table.show()
        table.set_row_spacings(2)
        table.set_col_spacings(2)
        vbox.pack_start(table, True, True)
        

        for cnt, name in enumerate(gridNames):

            label = gtk.Label(name)
            label.show()
            table.attach(label, 0, 1, cnt, cnt+1)
            
            entryRows = gtk.Entry()
            entryRows.show()
            entryRows.set_text('1')
            entryRows.set_width_chars(5)
            table.attach(entryRows, 1, 2, cnt, cnt+1)
            

            entryCols = gtk.Entry()
            entryCols.show()
            entryCols.set_text('1')
            entryCols.set_width_chars(5)
            table.attach(entryCols, 2, 3, cnt, cnt+1)


            entries[name] = entryRows, entryCols

        for key in entries.keys():            
            e1, e2 = entries[key]

            N = len(named[key])
            if N==64:
                e1.set_text('8')
                e2.set_text('8')
            elif N==48:
                e1.set_text('8')
                e2.set_text('6')
            elif N==32:
                e1.set_text('8')
                e2.set_text('4')
            elif N==16:
                e1.set_text('8')
                e2.set_text('2')
            elif N==12:
                e1.set_text('6')
                e2.set_text('2')
            elif N==10:
                e1.set_text('5')
                e2.set_text('2')
            elif N==8:
                e1.set_text('8')
                e2.set_text('1')
            else:
                e1.set_text('%d'%N)
                e2.set_text('1')
                
        dlg.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        dlg.add_button(gtk.STOCK_OK, gtk.RESPONSE_OK)
        dlg.set_default_response(gtk.RESPONSE_OK)

        return dlg, entries
        
    def get_dimensions(self):
        'Return a dict mapping name to numrows, numcols'       
        self.dlgDim.show()
        response = self.dlgDim.run()

        if response == gtk.RESPONSE_OK:
            results = {}
            
            for name in self.get_grid_names():
                erows, ecols = self.dlgDimEntries[name]
                #todo: error checking
                numrows = int(erows.get_text())
                numcols = int(ecols.get_text())
                results[name] = numrows, numcols

            self.dlgDim.hide()
            self.dimensiond = results

            self.update_actors()
            
            return results
        else:
            self.dlgDim.hide()
            return None


    def make_strip_ribbon(self, name):
        """

        Return a ribbon actor for the grid with name and shape given by
        numRows, numCols where either numRows or numCols ==1

        The function attaches two properties to the markers in grid:
           normal : a Numeric array of normal values at the marker point
           ind    : an index into the point set of the grid

        """
        print "make_strip_ribbon(", name,")"
        
        markerd = self.markerd
        numrows, numcols = self.dimensiond[name]
        N = numrows*numcols
        
        trodes = []
        for trode, marker in markerd.items():
            gname, gnum = trode
            if gname==name:
                trodes.append( (gnum, gname, marker) )

        if len(trodes) != N:
            error_msg('%s strip requires %d electrodes; only found %d' %
                      ((numrows, numcols), N, len(trodes)))
            return None
        points = vtk.vtkPoints()

        trodes.sort()
        for gnum, gname, marker in trodes:
            vtkID = points.InsertNextPoint(*marker.get_center())
            self.vtkIDs[(name, gnum)] = vtkID


        # Create the polyline.
        lines = vtk.vtkCellArray()
        lines.InsertNextCell(N)
        for i in range(N):
            lines.InsertCellPoint(i)

        polyData = vtk.vtkPolyData()
        polyData.SetPoints(points)
        polyData.SetLines(lines)


        filter = vtk.vtkRibbonFilter()
        filter.SetInput(polyData)
        filter.SetWidth(0.2)

        markers = [marker for gnum, gname, marker in trodes]
        self.set_normals_grid1(markers, filter)  # todo: check flipped state
        
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInput(filter.GetOutput())

        # make red hot
        lut = vtk.vtkLookupTable()
        lut.SetHueRange(0.667, 0.0)
        mapper.SetLookupTable(lut)

        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        #profile.GetProperty().SetDiffuseColor(banana)
        actor.GetProperty().SetSpecular(.3)
        actor.GetProperty().SetSpecularPower(30)
        return polyData, actor, filter, markers


    def make_grid_surf(self, name):
        """

        Return a surface actor for the grid with name 

        The function attaches two properties to the markers in grid:
           normal : a Numeric array of normal values at the marker point
           ind    : an index into the point set of the grid

        """

        numrows, numcols = self.dimensiond[name]
        N = numrows*numcols

        trodes = []
        for trode, marker in self.markerd.items():
            gname, gnum = trode
            if gname==name:
                trodes.append( (gnum, gname, marker) )

        if len(trodes) != N:
            error_msg('%s grid requires %d electrodes; only found %d' %
                      (numrows, numcols), N, len(trodes))
            return None

        trodes.sort() # sort by number
        
        grid = vtk.vtkStructuredGrid()
        grid.SetDimensions(numrows, numcols, 1)
        points = vtk.vtkPoints()



        for gnum, gname, marker in trodes:
            vtkID = points.InsertNextPoint(*marker.get_center())
            self.vtkIDs[(gname, gnum)] = vtkID

        grid.SetPoints(points)


        filter = vtk.vtkDataSetSurfaceFilter()
        filter.SetInput(grid)

        markers = [marker for gnum, gname, marker in trodes]
        self.set_normals_grid2(markers, filter)  # todo: check flipped state

        print "GridManager.make_grid_surf(): creating mapper = vtk.vtkPolyDataMapper"
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInput(filter.GetOutput())


        surfActor = vtk.vtkActor()
        surfActor.SetMapper(mapper)

        # make red hot
        lut = vtk.vtkLookupTable()
        print "GridManager.make_grid_surf(): 'make red hot' lut.SetHueRange(0.667, 0.0)"        
        lut.SetHueRange(0.667, 0.0)
        # sweet, this works
        #lut.SetHueRange(0.0, 0.25)
        #lut.SetTableRange(0,1)
        #for i in range(0,128):
        #    #lut.SetTableValue(i, [float(i)/256.0, 1.0-(float(i)/256.0), 0.0, 1.0])
        #    lut.SetTableValue(i, [1.0, 1.0-(float(i)/256.0), 0.0, 1.0])
        #for i in range(128,256):
        #    #lut.SetTableValue(i, [float(i)/256.0, 1.0-(float(i)/256.0), 0.0, 1.0])
        #    lut.SetTableValue(i, [1.0, 1.0-(float(i)/256.0), 0.0, 1.0])
        #lut.Build()
        mapper.SetLookupTable(lut)


        property = surfActor.GetProperty()

        property.SetColor(1,1,1)
        #property.SetRepresentationToWireframe()
        property.SetRepresentationToSurface()
        property.SetInterpolationToGouraud()
        #property.SetInterpolationToPhong()
        #property.SetInterpolationToFlat()
        property.SetOpacity(0.99)
        property.EdgeVisibilityOn()
        #property.SetPointSize(10.0)

        return grid, surfActor, filter, markers

    def set_normals_grid1(self, markers, filter, flip=False):
        norms = vtk.vtkPolyDataNormals()
        norms.SetInput(filter.GetOutput())
        norms.ComputePointNormalsOn()
        #norms.AutoOrientNormalsOff()
        norms.ConsistencyOn()
        if flip:
            norms.FlipNormalsOn()
        norms.Update()
        normVecs =  norms.GetOutput().GetPointData().GetNormals()


        # todo: fix me so normals rotate too!  will need some
        # transform goop
        for i, marker in enumerate(markers):
            print "set_normals_grid1: calling GetComponent on normVecs=", normVecs
            thisNorm = array([normVecs.GetComponent(i,0), normVecs.GetComponent(i,1), normVecs.GetComponent(i,2)], 'd')

            marker.normal = thisNorm

    def set_normals_grid2(self, markers, filter, flip=False):
        norms = vtk.vtkPolyDataNormals()
        norms.SetInput(filter.GetOutput())
        norms.ComputePointNormalsOn()
        #norms.AutoOrientNormalsOff()
        norms.ConsistencyOn()
        if flip:
            norms.FlipNormalsOn()
        norms.Update()
        normVecs =  norms.GetOutput().GetPointData().GetNormals()

        for i, marker in enumerate(markers):
            thisNorm = array([normVecs.GetComponent(i,0), normVecs.GetComponent(i,1), normVecs.GetComponent(i,2)], 'd')

            marker.normal = thisNorm

    def parse_colormap_textfile(self, colormap_filename):
        if colormap_filename is None: return
        if not os.path.exists(colormap_filename):
            error_msg('File %s does not exist' % colormap_filename)
            colormap_filename = None
            return None
        fh = open(colormap_filename)
        custom_colormap = zeros((256, 4), 'd')
        i = 0
        while 1:
            line = fh.readline().strip()
            #print "colormap line='%s'" % line
            
            if (line == ''):
                break

            foo = line.split('\t')
            custom_colormap[i] = map(float,foo)
            i = i+ 1
        #print "yo custom_colormap=", custom_colormap
        return custom_colormap

    def set_custom_colormap(self):
        if fmanager.col == "" or fmanager.col == " ": 
            return
        else:
            colormap_filename = fmanager.col
            print "colormap_filename is " , colormap_filename
            if colormap_filename is None: return
            custom_colormap = self.parse_colormap_textfile(colormap_filename)
            if not (custom_colormap == None):
                for name in self.get_grid2_names():
                    grid, actor, filter, markers = self.surfs[name]
                    mapper = actor.GetMapper()
                    lut = vtk.vtkLookupTable()
                    for i in range(0, 256):
                        lut.SetTableValue(i, custom_colormap[i])
                    lut.Build()
                
                    mapper.SetLookupTable(lut)


def coherence_matrix(Cxy, Pxy, xyzd, eoi, bandind):
    N = len(eoi)
    M = zeros( (N,N), 'd')
    P = zeros( (N,N), 'd')
    D = zeros( (N,N), 'd')
    
    for i in range(N):
        for j in range(N):
            if i==j:
                M[i,j]=1.0
                D[i,j]=0.0
                continue
            key = (eoi[i], eoi[j])
            if not Cxy.has_key(key):
                key = (eoi[j], eoi[i])
            M[i,j] = Cxy[key][bandind]
            P[i,j] = Pxy[key][bandind]
            D[i,j] = dist(xyzd[eoi[i]], xyzd[eoi[j]])

    return M, P, D


def validate_marker_dict(md, eoi, parent):
    # make sure you have a key in md for every electrode in eoi

    for key in eoi:
        if not md.has_key(key):

            error_msg('Could not find a marker for electrode %s %d' % key,
                      parent=parent)            
            return False

    return True
    





