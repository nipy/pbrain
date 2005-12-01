from __future__ import division
import sys, os, math
import vtk

import gtk, gobject




class ScalarMapper:
    """
    Classes that provide data to the grid manager

    The derived classes are responsible for loading data and building
    the electrode->scalar maps required by GridManager.set_scalar_data
    """
    SCROLLBARSIZE = 150,20
    def __init__(self, gridManager):
        self.gridManager = gridManager


class ArrayMapper(gtk.Window, ScalarMapper):

    def __init__(self, gridManager, X, channels, amp):
        ScalarMapper.__init__(self, gridManager)
        gtk.Window.__init__(self)
        self.set_title('Array data')

        self.channels = channels        
        self.amp = amp
        self.trodes = [(gname, gnum) for cnum, gname, gnum in amp]
        self.X = X

        self.numChannels, self.numSamples = X.shape
        
        vbox = gtk.VBox()
        vbox.show()
        self.add(vbox)

        self.fig = self.make_fig()

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
        scrollbar.set_range(0, self.numSamples-1)
        scrollbar.set_increments(1,1)
        scrollbar.set_value(self.numSamples//2)
        scrollbar.connect('value_changed', self.set_sample_num)
        self.scrollbarIndex = scrollbar

        toolbar = NavigationToolbar(self.canvas, self)
        toolbar.show()
        vbox.pack_start(toolbar, False, False)

        self.set_sample_num(scrollbar)

    def set_sample_num(self, bar):
        ind = int(bar.get_value())
        datad = self.get_datad(ind)
        self.gridManager.set_scalar_data(datad)
        xdata = array([ind, ind], typecode=Float)
        for line in self.lines:
            line.set_xdata(xdata)
        self.canvas.draw()


    def get_datad(self, ind):
        
        slice = self.X[:,ind]
        datad = dict(zip(self.trodes, slice))
        return datad

    def make_fig(self):
        

        fig = Figure(figsize=(7,5), dpi=72)
        self.lines = []
        N = len(self.channels)
        for i, channel in enumerate(self.channels):
            ax = fig.add_subplot(N, 1, i+1)
            x = self.X[channel-1,:]
            ax.plot(arange(self.numSamples), x)
            ax.grid(True)
            mid = self.numSamples/2.0
            line = ax.plot([mid, mid], [min(x), max(x)])[0]
            ax.add_line(line)
            ax.set_ylabel('Chan #%d' % channel)
            self.lines.append(line)
            if ax.is_last_row(): ax.set_xlabel('index')
            if ax.is_first_row(): ax.set_title('Evoked response')

            
        return fig

