from __future__ import division
import sys, os, math, copy, gc
import pylab as p
import vtk

#from Numeric import array, zeros, ones, sort, absolute, sqrt, divide,\
#     argsort, take, arange
from scipy import array, zeros, ones, sort, absolute, sqrt, divide,\
     argsort, take, arange

import gtk, gobject
from matplotlib.backends.backend_gtkagg import FigureCanvasGTKAgg as FigureCanvas
from matplotlib.backends.backend_gtkagg import NavigationToolbar
from matplotlib.figure import Figure
from events import Observer

class ScalarMapper:
    """
    CLASS: ScalarMapper
    DESCR: Classes that provide data to the grid manager

    The derived classes are responsible for loading data and building
    the electrode->scalar maps required by GridManager.set_scalar_data
    """
    SCROLLBARSIZE = 150,20
    def __init__(self, gridManager):
        self.gridManager = gridManager


class ArrayMapper(gtk.Window, ScalarMapper, Observer):
    """
    CLASS: ArrayMapper
    DESCR: 
    """
    def __init__(self, gridManager, X, channels, amp, addview3, view3, start_time=None, end_time=None):
        ScalarMapper.__init__(self, gridManager)
        gtk.Window.__init__(self)
        Observer.__init__(self)
        self.resize(512,570)
        self.set_title('Array data')
        self.view3 = view3
        self.addview3 = addview3
        self.channels = channels        
        self.amp = amp
        self.trodes = [(gname, gnum) for cnum, gname, gnum in amp]
        self.X = X

        self.ax = None

        self.numChannels, self.numSamples = X.shape
        self.addview3destroy = False

        self.time_in_secs = False
        self.start_time = None
        self.end_time = None
        if ((start_time != None) & (end_time != None)) :
            self.time_in_secs = True
            self.start_time = start_time
            self.end_time = end_time

        
        vbox = gtk.VBox()
        vbox.show()
        self.add(vbox)
        self.fig = self.make_fig(start_time, end_time)
        if self.addview3:
            button = gtk.Button('Remove from View3')
            button.show()
            #button.set_active(False)
            vbox.pack_start(button, False, False)
            button.connect('clicked', self.view3_remove)
            if self.addview3destroy == False:
                self.broadcast(Observer.ARRAY_CREATED, self.fig, True, False)
            self.addview3Button = button
        self.canvas = FigureCanvas(self.fig)  # a gtk.DrawingArea
        self.canvas.show()
        vbox.pack_start(self.canvas, True, True)        

        hbox = gtk.HBox()
        hbox.show()
        vbox.pack_start(hbox, False, False)        

        label = gtk.Label('Sample num')
        label.show()
        hbox.pack_start(label, False, False)

        scrollbar = gtk.HScrollbar()
        scrollbar.show()
        hbox.pack_start(scrollbar, True, True)
        
        
        if (self.time_in_secs == True):
            scrollbar.set_range(start_time, end_time)
            #scrollbar.set_increments(1,1)
            print "set_increments(%f, %f)" % ((end_time-start_time)/float(self.numSamples), (end_time-start_time)/float(self.numSamples))
            scrollbar.set_increments((end_time-start_time)/float(self.numSamples), (end_time-start_time)/float(self.numSamples))
            scrollbar.set_value(start_time + (end_time-start_time)/2.0)
                                
        else: 
            scrollbar.set_range(0, self.numSamples-1)
            scrollbar.set_increments(1,1)
            scrollbar.set_value(self.numSamples/2.0)
           


        
        scrollbar.connect('value_changed', self.set_sample_num)
        self.scrollbarIndex = scrollbar


        self.numlabel = gtk.Label(str(scrollbar.get_value()))
        self.numlabel.show()
        hbox.pack_start(self.numlabel,False, False)
        hbox2 = gtk.HBox()
        hbox2.show()
        toolbar = NavigationToolbar(self.canvas, self)
        toolbar.show()
        hbox2.pack_start(toolbar, True, True)
        button = gtk.Button('Coh. Here')
        button.show()
        hbox2.pack_start(button, False, False)
        button.connect('clicked', self.coh_here)
        vbox.pack_start(hbox2, False, False)

        self.set_sample_num(scrollbar)

        self.connect("destroy", self.on_destroy)
               
    def coh_here(self, button):
        val = self.scrollbarIndex.get_value()
        if (self.time_in_secs == True):
            val = (val*self.view3.eeg.freq)/1000 #convert val to points
        self.view3.offset = val - self.view3.newLength/2 #set the new view3 offset to the beginning of the window
        self.view3.compute_coherence()
        self.view3.plot_band()
        #I know I should be using the receiver. I really dislike that interface tho, so for now I'll be raw about it, until we get a better one.
        
    def view3_remove(self, button):
        #a switch in the array mapper to toggle view3 display
        if self.addview3destroy == False:
            self.addview3destroy = True
            self.broadcast(Observer.ARRAY_CREATED, self.fig, False, self.addview3destroy)
            self.addview3Button.set_label("Add to view3")
        else:
            self.addview3destroy = False
            self.broadcast(Observer.ARRAY_CREATED, self.fig, True, self.addview3destroy)
            self.addview3Button.set_label("Remove from view3")
            
    def on_destroy(self, widget):
        #take the view3 display out if we close the window
        self.view3_remove(self.addview3destroy)
        print "garbage collecting - unfortunately this doesn't prevent a segfault that will happen if you make a new arraymapper window and then try to drive the autoplay function with it. to be fixed in an upcoming patch, hopefully."
        gc.collect()
        
    def set_sample_num(self, bar):
        LO = self.view3.newLength/2
        if (self.time_in_secs == True):
            LO = (LO*1000)/self.view3.eeg.freq #convert LO to ms
            val = float(bar.get_value())
            ind = ((val -self.start_time)  / (self.end_time - self.start_time) * self.numSamples)
            #print "ArrayMapper.set_sample_num() : ind=", ind
            datad = self.get_datad(ind)
            self.gridManager.set_scalar_data(datad)
            xdata = array([val, val], 'd')
            #print "shape of xdata is " , xdata.shape
            #for line in self.lines:
            #    print "ArrayMapper.set_sample_num(): doing line " , line
            #    line.set_xdata(xdata) 
            self.lines[0].set_xdata(array([val-LO, val-LO], 'd'))
            self.lines[1].set_xdata(array([val, val], 'd')) #middle line
            self.lines[2].set_xdata(array([val+LO, val+LO], 'd'))
        else:
            ind = int(bar.get_value())
            #print "ArrayMapper.set_sample_num(", ind, ")"
            datad = self.get_datad(ind)
            self.gridManager.set_scalar_data(datad)
            #xdata = array([ind, ind], 'd')
            #for line in self.lines:
            #    line.set_xdata(xdata)
            self.lines[0].set_xdata(array([ind-LO, ind-LO], 'd'))
            self.lines[1].set_xdata(array([ind, ind], 'd')) #middle line
            self.lines[2].set_xdata(array([ind+LO, ind+LO], 'd'))
    
        if (self.time_in_secs == True):
            self.numlabel.set_text(str(float(bar.get_value())))
        else:
            self.numlabel.set_text(str(int(bar.get_value())))
        #print "self.fig.get_axes() = ", self.fig.get_axes()
        self.canvas.draw()
        if self.addview3:
            if self.addview3destroy == False: #don't signal unless we have to
                self.broadcast(Observer.ARRAY_CREATED, self.fig, False, False) #redraw the view3 version of the array
                #the second false is to say that we shouldn't destroy the display in view3


    def get_datad(self, ind):
        
        slice = self.X[:,ind]
        datad = dict(zip(self.trodes, slice))
        return datad

    def make_fig(self, start_time, end_time):
        fig = Figure(figsize=(8,8), dpi=72)
        self.lines = []
        N = len(self.channels)
        self.ax = fig.add_subplot(1,1,1) #new singleplot configuration
        colordict = ['#A6D1FF','green','red','cyan','magenta','yellow','white']
        minx = 0
        maxx = 0
        graph = []
        for i, channel in enumerate(self.channels):
            #subplot syntax is numrows, numcolumns, subplot ID
            print "ArrayMapper.make_fig(): self.X is is " , self.X, type(self.X), len(self.X)
            print "ArrayMapper.make_fig(): channel is ", channel
            print "ArrayMapper.make_fig(): self.numSamples=", self.numSamples

            time_range = arange(self.numSamples)
            #print "start_time= ", start_time, "end_time =", end_time
            if ((start_time != None) & (end_time != None)):
                time_range = arange(start_time, end_time, (end_time - start_time)/self.numSamples)
            
            #print "time_range is ", time_range
            x = self.X[channel-1,:]
            if minx > min(x):
                minx = copy.deepcopy(min(x))
            if maxx < max(x):
                maxx = copy.deepcopy(max(x))
            color = colordict[((i-1)%7)]
            newp = self.ax.plot(time_range, x, color, label=("channel " + str(i+1)))
            newp[0].set_linewidth(4)
            graph.append(newp)
            
        self.ax.set_xlabel('index')
        self.ax.set_title('Evoked response')
        #self.ax.legend()
        fig.legend(graph,self.channels,'upper right')
        if ((start_time != None) & (end_time != None)):
            mid = start_time + (end_time - start_time)/2.0
        else:
            mid = self.numSamples/2.0
        #print "setting up line at (([%d, %d], [%d, %d])[0]" % (mid, mid, min(x), max(x))
        LO = self.view3.newLength/2
        #line = self.ax.plot([mid, mid], [minx, maxx],'w')[0]
        #left edge of window:
        line = self.ax.plot([mid-LO, mid-LO], [minx, maxx],'y')[0]
        self.ax.add_line(line)
        self.lines.append(line)
        #middle of window, where the scalar data comes from:
        line = self.ax.plot([mid, mid], [minx, maxx],'r')[0]
        self.ax.add_line(line)
        self.lines.append(line)
        #right edge of window
        line = self.ax.plot([mid+LO, mid+LO], [minx, maxx],'y')[0]
        self.ax.add_line(line)
        self.lines.append(line)
        self.ax.patch.set_facecolor('black') #transparency
        self.finishedFigure = fig
        
        return fig
        
    def recieve(self, event, *args):
        if event in (Observer.SET_SCALAR,):
            #move the scrollbar forward by the twidth
            self.scrollbarIndex.set_value(args[1])
            print "ARRAY MAPPER: RECIEVED SCALAR MESSAGE: ", args[1]
        return

