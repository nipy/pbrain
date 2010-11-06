from __future__ import division
import sys, os, math, copy
import vtk

#from Numeric import array, zeros, ones, sort, absolute, sqrt, divide,\
#     argsort, take, arange
from scipy import array, zeros, ones, sort, absolute, sqrt, divide,\
     argsort, take, arange

import gtk, gobject
from matplotlib.backends.backend_gtkagg import FigureCanvasGTKAgg as FigureCanvas
from matplotlib.backends.backend_gtkagg import NavigationToolbar
from matplotlib.figure import Figure


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


class ArrayMapper(gtk.Window, ScalarMapper):
    """
    CLASS: ArrayMapper
    DESCR: 
    """
    def __init__(self, gridManager, X, channels, amp, start_time=None, end_time=None):
        ScalarMapper.__init__(self, gridManager)
        gtk.Window.__init__(self)
        self.resize(800,600)
        self.set_title('Array data')

        self.channels = channels        
        self.amp = amp
        self.trodes = [(gname, gnum) for cnum, gname, gnum in amp]
        self.X = X

        self.ax = None

        self.numChannels, self.numSamples = X.shape

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

        toolbar = NavigationToolbar(self.canvas, self)
        toolbar.show()
        vbox.pack_start(toolbar, False, False)

        self.set_sample_num(scrollbar)

    def set_sample_num(self, bar):
        if (self.time_in_secs == True):
            val = float(bar.get_value())
            ind = ((val -self.start_time)  / (self.end_time - self.start_time) * self.numSamples)
            print "ArrayMapper.set_sample_num() : ind=", ind
            datad = self.get_datad(ind)
            self.gridManager.set_scalar_data(datad)
            xdata = array([val, val], 'd')
            print "shape of xdata is " , xdata.shape
            for line in self.lines:
                print "ArrayMapper.set_sample_num(): doing line " , line
                line.set_xdata(xdata) 
        else:
            ind = int(bar.get_value())
            print "ArrayMapper.set_sample_num(", ind, ")"
            datad = self.get_datad(ind)
            self.gridManager.set_scalar_data(datad)
            xdata = array([ind, ind], 'd')
            for line in self.lines:
                line.set_xdata(xdata)
    
        if (self.time_in_secs == True):
            self.numlabel.set_text(str(float(bar.get_value())))
        else:
            self.numlabel.set_text(str(int(bar.get_value())))
        print "self.fig.get_axes() = ", self.fig.get_axes()
        self.canvas.draw()


    def get_datad(self, ind):
        
        slice = self.X[:,ind]
        datad = dict(zip(self.trodes, slice))
        return datad

    def make_fig(self, start_time, end_time):
        

        fig = Figure(figsize=(7,5), dpi=72)
        self.lines = []
        N = len(self.channels)
        self.ax = fig.add_subplot(1,1,1) #new singleplot configuration
        colordict = ['blue','green','red','cyan','magenta','yellow','black']
        minx = 0
        maxx = 0
        for i, channel in enumerate(self.channels):
            #self.ax = fig.add_subplot(N, 1, i+1) #switching to 1 plot -eli
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
            self.ax.plot(time_range, x, color, label=("channel " + str(i+1)))
            #self.ax.grid(True)
            
            #line = self.ax.plot([mid, mid], [min(x), max(x)])[0] #switching to single plot
            #self.ax.add_line(line) #switching to single plot - moved out of loop
        self.ax.set_xlabel('index')
        self.ax.set_title('Evoked response')
        self.ax.legend()
        if ((start_time != None) & (end_time != None)):
            mid = start_time + (end_time - start_time)/2.0
        else:
            mid = self.numSamples/2.0
        #print "setting up line at (([%d, %d], [%d, %d])[0]" % (mid, mid, min(x), max(x))
        line = self.ax.plot([mid, mid], [minx, maxx])[0]
        self.ax.add_line(line)
        self.lines.append(line)
        
        return fig

