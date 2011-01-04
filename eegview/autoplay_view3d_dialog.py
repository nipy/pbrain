from __future__ import division
import sys, os, math
import vtk

import gtk, gobject

from pbrainlib.gtkutils import ButtonAltLabel, simple_msg

from dialogs import AutoPlayDialog
from events import Observer


class AutoPlayView3Dialog(AutoPlayDialog):
    """
    CLASS: AutoPlayView3Dialog 
    DESCR: note: setpars() is defined in dialogs.py, line 3852
    """
    def __init__(self, view3, tmin, tmax, twidth, scalarDisplay, quitHook=None):
        AutoPlayDialog.__init__(self, tmin, tmax, twidth, view3.newLength, scalarDisplay, quitHook)
        self.view3 = view3
        
        frame = gtk.Frame('Rotation')
        frame.show()
        self.vbox.pack_start(frame, False, False)
        frame.set_border_width(5)


        vboxFrame = gtk.VBox()
        vboxFrame.show()
        frame.add(vboxFrame)


                
        buttonUseRotation = gtk.CheckButton('Use rotation')
        buttonUseRotation.show()
        vboxFrame.pack_start(buttonUseRotation, False, False)
        buttonUseRotation.connect('toggled', self.use_rotation)
        buttonUseRotation.set_active(False)
        self.buttonUseRotation = buttonUseRotation

        self.rotationWidgets = []
        hbox = gtk.HBox()
        hbox.show()
        hbox.set_spacing(3)
        vboxFrame.pack_start(hbox, True, True)
        self.rotationWidgets.append(hbox)

        self.frames = []
            
        button = ButtonAltLabel('Clear', stock=gtk.STOCK_CUT)
        button.show()
        hbox.pack_start(button, True, True)
        button.connect('clicked', self.clear_frames)

        button = ButtonAltLabel('Add frame', stock=gtk.STOCK_ADD)
        button.show()
        hbox.pack_start(button, True, True)
        button.connect('clicked', self.add_frame)

        button = ButtonAltLabel('Interpolate', stock=gtk.STOCK_EXECUTE)
        button.show()
        hbox.pack_start(button, True, True)
        button.connect('clicked', self.interpolate_frames)

        self.labelFrames = gtk.Label()
        self.labelFrames.show()
        hbox.pack_start(self.labelFrames, True, True)


        hbox = gtk.HBox()
        hbox.show()
        hbox.set_spacing(3)
        vboxFrame.pack_start(hbox, True, True)
        self.rotationWidgets.append(hbox)
        
        labelPerTime = gtk.Label('Frames per time step')
        labelPerTime.show()
        hbox.pack_start(labelPerTime, False, False)



        entryPerTime = gtk.SpinButton()
        entryPerTime.show()
        hbox.pack_start(entryPerTime, False, False)
        #entryPerTime.set_width_chars(5)

        entryPerTime.set_range(0, 100)
        entryPerTime.set_increments(1, 5)
        entryPerTime.set_value(5)
        entryPerTime.set_numeric(True)
        entryPerTime.set_snap_to_ticks(True)
        entryPerTime.update()
        self.entryPerTime = entryPerTime

        self.update_frames_label()        
        self.use_rotation(self.buttonUseRotation)

        self.interpFrames = None

    def update_frames_label(self):
        self.labelFrames.set_text('Num frames: %d' % len(self.frames))

    def add_frame(self, button):

        camera = self.view3.renderer.GetActiveCamera()
        fpu = camera.GetFocalPoint(), camera.GetPosition(), camera.GetViewUp()

        im = self.view3.imageManager

        if im.using_planes():
            slicex = im.pwX.GetOrigin(), im.pwX.GetPoint1(), im.pwX.GetPoint2()
            slicey = im.pwY.GetOrigin(), im.pwY.GetPoint1(), im.pwY.GetPoint2()
            slicez = im.pwZ.GetOrigin(), im.pwZ.GetPoint1(), im.pwZ.GetPoint2()
        else:
            slicex = None, None, None
            slicey = None, None, None
            slicez = None, None, None

        slicePositions = slicex, slicey, slicez
        self.frames.append((fpu, slicePositions))
        self.update_frames_label()


    def clear_frames(self, button):
        self.frames = []
        self.update_frames_label()

    def use_rotation(self, button):
        sensitive = button.get_active()
        for w in self.rotationWidgets:
            w.set_sensitive(sensitive)

    def interpolate_frames(self, button=None):
        """
        Interpolate between the camera frames, with steps interpolated
        points between each frame.  frames is a sequence of fpu, IPW
        slice positions, where fpu is a (Focal Point, Position,
        ViewUp) tuple

        This routine matches frames to time steps and interpolates a
        frame for each time step.  It does not do the subinterpolation
        between time steps
        """

        self.interpFrames = None
        self.setpars()
        numInPnts = len(self.frames)
        numOutPnts = len(self.steps)*self.entryPerTime.get_value_as_int()

        if numInPnts<2:
            simple_msg('Found only %d input frames' % len(self.frames) ,
                      parent=self)
            return 
        if numOutPnts<2:
            simple_msg('Found only %d time steps' % len(self.steps) ,
                      parent=self)
            return 
        def interpolate_tup3(tups):
            aSplineX = vtk.vtkCardinalSpline()
            aSplineY = vtk.vtkCardinalSpline()
            aSplineZ = vtk.vtkCardinalSpline()

            for i,tup in enumerate(tups):
                x,y,z = tup
                aSplineX.AddPoint(i, x)
                aSplineY.AddPoint(i, y)
                aSplineZ.AddPoint(i, z)

            pnts = []
            for i in range(numOutPnts):
                t = (numInPnts-1.0)/(numOutPnts-1.0)*i
                pnts.append((aSplineX.Evaluate(t),
                             aSplineY.Evaluate(t),
                             aSplineZ.Evaluate(t)))
            return pnts

        fpus, slicePositions = zip(*self.frames)
        fs, ps, us = zip(*fpus)
        
        interpFs = interpolate_tup3(fs)
        interpPs = interpolate_tup3(ps)
        interpUs = interpolate_tup3(us)
        interpFPUs = zip(interpFs,interpPs,interpUs)


        im = self.view3.imageManager
        if im.using_planes():
        
            slicex, slicey, slicez = zip(*slicePositions)

            o, p1, p2 = zip(*slicex)
            interpo = interpolate_tup3(o)
            interpp1 = interpolate_tup3(p1)
            interpp2 = interpolate_tup3(p2)
            interpx = zip(interpo,interpp1,interpp2)

            o, p1, p2 = zip(*slicey)
            interpo = interpolate_tup3(o)
            interpp1 = interpolate_tup3(p1)
            interpp2 = interpolate_tup3(p2)
            interpy = zip(*(interpo,interpp1,interpp2))

            o, p1, p2 = zip(*slicez)
            interpo = interpolate_tup3(o)
            interpp1 = interpolate_tup3(p1)
            interpp2 = interpolate_tup3(p2)
            interpz = zip(interpo,interpp1,interpp2)

            interpSlices = zip(interpx, interpy, interpz)

        else:
            interpSlices = [None]*len(interpFPUs)
        self.interpFrames =  zip(interpFPUs, interpSlices)
        simple_msg('%d frames created; read to play!' % len(self.interpFrames))
        
        

    def set_frame(self, frame):
        fpu, slicePos = frame
        camera = self.view3.renderer.GetActiveCamera()
        focal, pos, up = fpu
        camera.SetFocalPoint(focal)
        camera.SetPosition(pos)
        camera.SetViewUp(up)

        im = self.view3.imageManager



        if slicePos is not None:
            slicex, slicey, slicez = slicePos
            o,p1,p2 = slicex
            im.pwX.SetOrigin(o)
            im.pwX.SetPoint1(p1)
            im.pwX.SetPoint2(p2)
            im.pwX.UpdatePlacement()

            o,p1,p2 = slicey
            im.pwY.SetOrigin(o)
            im.pwY.SetPoint1(p1)
            im.pwY.SetPoint2(p2)
            im.pwY.UpdatePlacement()

            o,p1,p2 = slicez
            im.pwZ.SetOrigin(o)
            im.pwZ.SetPoint1(p1)
            im.pwZ.SetPoint2(p2)
            im.pwZ.UpdatePlacement()

        self.view3.renderer.ResetCameraClippingRange()
        self.view3.interactor.Render()

    def forward(self, *args):
        if (self.buttonUseRotation.get_active() and
            self.interpFrames is  None):  
            self.interpolate_frames()
            
        self.stop()
        good = self.setpars()
        if not good: return False
        self.direction = 1
        self.idleID = gobject.idle_add(self.scroll)
        
    def scroll(self, *args):


        basename = '%s%05d' % (self.entryMovie.get_text(), self.ind)
        self.update_status_bar()
        
        if self.ind<0 or self.ind>=len(self.steps):
            self.stop()
            self.ind=0
            return False
        
        # we're still playing
        thisMin = self.steps[self.ind]
        thisMax = thisMin + self.twidth
        self.view3.offset = self.steps[self.ind]
        #decide who to send the signal to
        if self.scalarDisplay["scalardisplay"]:
            #if the scalar option is available, choose between them: 
            if self.buttonPageScalar.get_active():
                self.broadcast(Observer.SET_SCALAR, thisMin, thisMax)
                print "DIALOGS: SENT SCALAR MESSAGE: ", thisMin, thisMax
            else:
                #self.broadcast(Observer.SET_TIME_LIM, thisMin, thisMax)
                
                self.view3.compute_coherence()
                self.view3.plot_band()
                if self.buttonPageBoth.get_active():
                    self.broadcast(Observer.SET_SCALAR, thisMin, thisMax)
                
        else:  #otherwise just broadcast the eeg driver sig
            #self.broadcast(Observer.SET_TIME_LIM, thisMin, thisMax) #note we are not moving the herald window time anymore
            self.view3.compute_coherence()
            self.view3.plot_band()
        #update the data (actual scrolling step): now done below
        #self.ind += self.direction

        # do the rotate interpolation for view3
        if self.buttonUseRotation.get_active():
            numSteps = self.entryPerTime.get_value_as_int()
            ind0 = self.ind*numSteps
            for i in range(numSteps):
                print 'Setting frame %d of %d' % (ind0+i, len(self.interpFrames))
                self.set_frame(self.interpFrames[ind0+i])
                fname = '%s_interp%04d' % (basename, i)
                if i< numSteps-1:
                    self.view3.recieve(Observer.SAVE_FRAME, fname)
        else:
            fname = basename

        # notify the observers
        if self.checkButtonMovie.get_active():
            self.broadcast(Observer.SAVE_FRAME, fname)
        self.ind += self.direction
        return True
