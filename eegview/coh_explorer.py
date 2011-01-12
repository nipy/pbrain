from __future__ import division
import sys, os, math, copy, gc
import pylab as p
import vtk

from scipy import array, zeros, ones, sort, absolute, sqrt, divide,\
     argsort, take, arange
import numpy
import pygtk
pygtk.require('2.0')
import gtk
import gobject
from matplotlib.backends.backend_gtkagg import FigureCanvasGTKAgg as FigureCanvas
from matplotlib.backends.backend_gtkagg import NavigationToolbar
from matplotlib.figure import Figure
from events import Observer
from shared import fmanager

class CohExplorer(gtk.Window, Observer):
    """this class will implement an entirely new view, launching from view3, allowing exploration and data discovery based on coherence dumps from the dump coherences button in the view3 window. """
    def __init__(self, eoi):
        gtk.Window.__init__(self)
        Observer.__init__(self)
        
        self.t_data = {}
        self.channels = eoi
        print "explorer channels are: ", self.channels
        
        self.resize(512,512)
        self.set_title('Coherence Explorer')
        
        vbox = gtk.VBox()
        vbox.show()
        self.add(vbox)
        buttonEntry = gtk.Entry()
        self.dumpfile = None
        def load_file(button):
            dumpfile = fmanager.get_filename(title="Select dump file:")
            if dumpfile is None: return
            if not os.path.exists(dumpfile):
                print 'File %s does not exist' % dumpfile
                return

            try: fh = file(dumpfile)
            except IOError, msg:
                msg = exception_to_str('Could not open %s' % dumpfile)
                error_msg(msg)
                return
            fh.close() 
            self.dumpfile = dumpfile
            buttonEntry.set_text(str(self.dumpfile))
            self.read_data(self.dumpfile)
            return
            
    
        buttonSave = gtk.Button(stock=gtk.STOCK_OPEN)
        buttonSave.show()
        buttonSave.connect('clicked', load_file)
        buttonEntry.show()
        
        hbox = gtk.HBox()
        hbox.show()
        hbox.set_spacing(3)
        vbox.pack_start(hbox, True, True)
        hbox.pack_start(buttonEntry, False, False)
        hbox.pack_start(buttonSave, False, False)
        load_file(buttonSave)
        self.fig = self.make_fig()
        self.canvas = FigureCanvas(self.fig)  # a gtk.DrawingArea
        self.canvas.show()
        vbox.pack_start(self.canvas, True, True)      
        
            
    def read_data(self, df):
        #the spec is a dict from name of trode to list containing numsamples and sumsamples
        #and a dict from time to above dict
        f = open(df, 'rb')
        nl = 100
        col = 4
        i = 0
        trodelist = []
        tr = {}
        skip = 0
        tnext = 0
        while 1:
            line = f.readline()
            if (i == nl):
                break
            if (skip == 1):
                skip = 0
                continue
            if (tnext == 1):
                tnext = 0
                tcur = int(line)
                #print "current time is ", tcur
                tr = copy.deepcopy(tr) #trodes is a dict from name of trode to tuple containing numsamples and sumsamples. copies are important.
                tr = {} #get ready
                trodelist.append(tr) #add  tr to the list of data
                
                #print "appended new list at index ", i
                
                self.t_data[tcur] = trodelist[i] #add the time to the dict, get ready to add the trodes data at that time
                i += 1
                continue
                
            if (line[0] == '['):
                if (line[1:5] == 'swee'):
                    skip = 1
                    continue
                elif (line[1:5] == 'leng'):
                    skip = 1
                    continue
                elif (line[1:5] == 'offs'):
                    tnext = 1
                    continue
            line = line.split(',')
            if (math.isnan(float(line[col]))):
                line[col] = 0 
            for z in (0,1):
                if (line[z] in tr):
                    item = tr[line[z]]
                    item[0] += 1
                    item[1] += float(line[col]) #add the new data, for delta only
                else:
                    tr[line[z]] = [1, float(line[col])]
        
    def make_fig(self):
        fig = Figure(figsize=(15,15), dpi=72)
        self.lines = []
        N = len(self.channels)
        self.ax = fig.add_subplot(1,1,1) #new singleplot configuration
        colordict = ['#A6D1FF','green','red','cyan','magenta','yellow','white']
        keys = self.t_data.keys()
        keys = sorted(keys)
        del keys[-1] #for some reason the last time key is coming out null sometimes in the data?
        dumpchans = self.t_data[0].keys()
        #print "dumpchans!!", dumpchans
        #print "timeKEYS: ", keys
        #print "EOI: ", self.channels
        
        
        counter = 0
        xdata = []
        for i in self.t_data[0]: #go through the ordered channel list one by one
            xdata.append([]) #keep all the channel data seperate
            #print "this is the channelkey: ", i
            isplit = i.split(" ")
            isplit = isplit[0],int(isplit[1])
            if not isplit in self.channels: #make sure the channel we plot is in the view3 display
                print "channel error! on channel ", i
            color = colordict[((counter)%7)]
            for t in keys: #at each time point
                (ns,ss) = self.t_data[t][i] #get the data out
                x1 = ss/ns #find the average
                xdata[counter].append(x1)
            newp = self.ax.plot(arange(len(xdata[counter])), xdata[counter], color, label=(str(i))) #plot a channel
            #print "at time ", counter, "xdata has ", len(xdata[counter]), " channels."
            counter += 1
        return fig
