from __future__ import division
import sys, os, math, copy, gc
import pylab as p
import vtk

from scipy import array, zeros, ones, sort, absolute, sqrt, divide,\
     argsort, take, arange, nonzero
import numpy
import pygtk
pygtk.require('2.0')
import gtk
import gobject
from matplotlib.backends.backend_gtkagg import FigureCanvasGTKAgg as FigureCanvas
from matplotlib.backends.backend_gtkagg import NavigationToolbar
from matplotlib.figure import Figure
from matplotlib import axes
from matplotlib.widgets import Cursor
import mpl_toolkits.mplot3d.axes3d as p3
from events import Observer
from shared import fmanager
from pbrainlib.gtkutils import error_msg, simple_msg, make_option_menu,\
     get_num_value, get_num_range, get_two_nums, str2int_or_err,\
     OpenSaveSaveAsHBox, ButtonAltLabel, str2num_or_err, exception_to_str

class CohExplorer(gtk.Window, Observer):
    """this class will implement an entirely new view, launching from view3, allowing exploration and data discovery based on coherence dumps from the dump coherences button in the view3 window. """
    def __init__(self, eoi, freq):
        gtk.Window.__init__(self)
        Observer.__init__(self)
        self.bandlist = ['delta', 'theta', 'alpha', 'beta', 'gamma', 'high']
        self.t_data = {} #this is the dictionary used in read_data, from time points to channel cohs unaveraged
        self.x_data = {} #this is the dictionary used in make_fig, from channel labels to xdata
        self.channels = eoi
        self.eegfreq = freq
        self.datares = 0
        self.fig = Figure(figsize=(15,15), dpi=72)
        self.canvas = FigureCanvas(self.fig)  # a gtk.DrawingArea
        self.canvas.show()
        self.canvas.mpl_connect('motion_notify_event', self.motion_notify_event)
        self.canvas.mpl_connect('button_press_event', self.button_press_event)
        self.canvas.mpl_connect('button_release_event', self.button_release_event)   
        print "explorer channels are: ", self.channels
        
        self.resize(700,512)
        self.set_title('Coherence Explorer')
        
        self.band = self.bandlist[0] #start with delta
        self.length = 12 #start with a tiny amount of lines
        vbox = gtk.VBox()
        vbox.show()
        self.add(vbox)
        saveEntry = gtk.Entry()
        self.dumpfile = None
        self.oldlength = 12
        self.opt = 'multi'
        self.optchanged = 0
        self.chansel = []
        self.oldsel = []
        self.stdsel = []
        self.stddevstate = 0
        
        def plot(button):
            self.length = int(self.ms2lines(float(self.lengthEntry.get_text())))
            if (self.length > self.oldlength or self.optchanged == 1):
                del self.t_data
                self.t_data = {}
                print "coh_explor: linelength: ", self.length
                self.read_data(self.dumpfile, self.length, self.opt)
            del self.x_data
            self.x_data = {}
            self.make_fig(self.band)
            
            self.oldlength = copy.deepcopy(self.length)
            self.optchanged = 0
            for linesel in self.chansel:
                self.lines[linesel][0].set_color('w')
                self.lines[linesel][0].set_linewidth(5)
            self.canvas.draw()
        
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
            saveEntry.set_text(str(self.dumpfile))
            if not self.datares: #this happens only on load, hopefully
                self.read_data(self.dumpfile, self.length, self.opt)
            else: #read data sets the input entry to ms at the end and from then on should be in ms 
                self.read_data(self.dumpfile, self.ms2lines(self.length), self.opt)
            
            return
            
    
        buttonSave = gtk.Button(stock=gtk.STOCK_OPEN)
        buttonSave.show()
        buttonSave.connect('clicked', load_file)
        saveEntry.show()
        buttonChans = gtk.Button("Chans")
        buttonChans.show()
        buttonChans.connect('clicked', self.load_chans)
        
        def set_active_band(combobox):
            model = combobox.get_model()
            index = combobox.get_active()
            label = model[index][0]
            self.band = label
            return
        def set_opts(combobox):
            self.optchanged = 1
            model = combobox.get_model()
            index = combobox.get_active()
            label = model[index][0]
            self.opt = label
            
        bandMenu = make_option_menu(self.bandlist, func=set_active_band)
        optMenu = make_option_menu(['coh', 'phase', 'cohphase'], func=set_opts)
        
        lEntry = gtk.Label()
        lEntry.set_text("ms")
        lEntry.show()
        self.lengthEntry = gtk.Entry()
        self.lengthEntry.set_text(str(self.length))
        self.lengthEntry.show()
        buttonPlot = gtk.Button(stock=gtk.STOCK_EXECUTE) #the execute button replots with changes
        buttonPlot.show()
        buttonPlot.connect('clicked', plot)
        
        lNorm = gtk.Label()
        lNorm.set_text("norm: ")
        lNorm.show()
        self.buttonNorm = gtk.CheckButton()
        self.buttonNorm.set_active(False)
        self.buttonNorm.show()
        
        lInst = gtk.Label()
        lInst.set_text("inst: ")
        lInst.show()
        self.buttonInst = gtk.CheckButton()
        self.buttonInst.set_active(False)
        self.buttonInst.show()
        
           
        hbox = gtk.HBox()
        hbox.show()
        hbox.set_spacing(3)
        vbox.pack_start(hbox, False, False)
        hbox.pack_start(saveEntry, False, False)
        hbox.pack_start(buttonSave, False, False)
        hbox.pack_start(buttonChans, False, False)
        hbox.pack_start(bandMenu, False, False)
        hbox.pack_start(self.lengthEntry, False, False)
        hbox.pack_start(lEntry, False, False)
        hbox.pack_start(optMenu, False, False)
        hbox.pack_start(lNorm, False, False)
        hbox.pack_start(self.buttonNorm, False, False)
        hbox.pack_start(buttonPlot, False, False)
        hbox.pack_start(lInst, False, False)
        hbox.pack_start(self.buttonInst, False, False)
        
        self.statBar = gtk.Label()
        self.statBar.set_alignment(0,0)
        self.statBar.show()
        self.progBar = gtk.ProgressBar()
        #self.progBar.set_size_request(10, 100)
        self.progBar.set_orientation(0)  # bottom-to-top
        self.progBar.set_fraction(0)
        self.progBar.show()
        load_file(buttonSave) #load a file on startup
        self.make_fig(self.band) #and plot it
        
        vbox.pack_start(self.canvas, True, True)
        vbox.pack_start(self.statBar, False, False)
        vbox.pack_start(self.progBar, False, False)
   
    def load_chans(self, button):
        dlg = gtk.Dialog("Channel Manipulation")
        dlg.connect("destroy", dlg.destroy)
        dlg.set_size_request(400,400)
        scrolled_window = gtk.ScrolledWindow(None, None)
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        dlg.vbox.pack_start(scrolled_window, True, True, 0)
        scrolled_window.show()

        table = gtk.Table(2,(1+len(self.channels)))
        table.set_row_spacings(8)
        table.set_col_spacings(8)
        scrolled_window.add_with_viewport(table)
        table.show()
        #attach format: obj, beg end x, beg end y
        l1 = gtk.Label("show            channel")
        l1.show()

        table.attach(l1,0,1,0,1)
        #an array to control the check boxes
        chanbuts = []
        for i in range(0, len(self.channels)):
            s1 = "                %s" % (self.channels[i],)
            chanbuts.append(gtk.CheckButton(s1))
            chanbuts[i].show()
            if self.channels[i] in self.chansel:
                chanbuts[i].set_active(True) #reactivate previously active channels
            chanbuts[i].connect("toggled", self.chanswitch, self.channels[i])
            table.attach(chanbuts[i], 0,1,i+1,i+2)
        butOK = gtk.Button("OK")    
        butOK.connect('clicked', (lambda b, x: x.destroy()), dlg)
        butOK.show()
        dlg.vbox.pack_start(butOK, False, False)
        dlg.show()
        
    
    def chanswitch(self, widget, channelnum):
        print channelnum
        if channelnum in self.lines.keys():
            if widget.get_active():
                self.chansel.append(channelnum)
                self.lines[channelnum][0].set_color('w')
                self.lines[channelnum][0].set_linewidth(5)
            else:
                self.chansel.remove(channelnum)
                self.lines[channelnum][0].set_color('r')
                self.lines[channelnum][0].set_linewidth(1)
            self.canvas.draw()
    def motion_notify_event(self, event):
        return False
    def button_press_event(self, event):       
        if not event.inaxes: return
        x, y = event.xdata, event.ydata
        #if event.button==1: #really we want to do the below for right and left clicks
        if event.inaxes == self.ax: #check if buttonpress is in axes
            print "clicked at: ", x, y
            keys = self.lines.keys() #get the line dict keys (channels names)
            xlen = len(self.lines[keys[0]][0].get_ydata()) #number of plotted points per channel 
            xlim = self.ax.get_xlim() #x axes scale
            xindex = int((x * xlen)/abs(xlim[1]-xlim[0])) #which point have we clicked closest to?
            xdiff = abs(x - self.lines[keys[0]][0].get_xdata()[xindex])
            ysdiff = {} #will be a dict from channel name to distance to y click
            ysfull = {}
            for key in keys:
                ys = (self.lines[key][0].get_ydata()[xindex]) #get the y value at the closest plotted point - I don't think extrapolating along a line is necessary, although at lower resolutions this tends to miss quite a bit so maybe I'll add that.
                ysdiff[key] = abs(ys - float(y)) #distance
                ysfull[key] = ys

            if event.button==1:
                if self.stddevstate==0: #if we haven't rightclicked right before this
                    
                    miny = min(ysdiff.items(), key = lambda x: x[1]) [0] #mininum yval
                    if (self.oldsel != []): #color switching
                        self.lines[self.oldsel[0]][0].set_color(self.oldsel[1])
                        self.lines[self.oldsel[0]][0].set_linewidth(1)
                        self.oldsel = []
                    for (key, color) in self.stdsel: #reset the blue lines if we aren't in stdsel state anymore
                        self.lines[key][0].set_color(color)
                        self.lines[key][0].set_linewidth(1)
                    self.stdsel = [] #reset stdsel                                                              
                    
                    
                    self.oldsel.append(copy.deepcopy(miny))
                    self.oldsel.append(self.lines[miny][0].get_color())
                    self.lines[miny][0].set_color('y')
                    self.lines[miny][0].set_linewidth(5)
                    self.canvas.draw()
                    self.statBar.set_text("Closest Channel: %s at value (%f, %f) has xval diff of %f." %(str(miny), x, y, xdiff)) #display channel name and position of click. should hopefully already be in ms.
                else: #if we've primed the system with a rightclick
                    #ysarray = numpy.zeros([len(ysfull)])
                    self.statBar.set_text("Clicked at (%f, %f) has xval diff of %f." %(x, y, xdiff))
                    #ysarray = ysfull.values()
                    #ysstd = numpy.std(ysarray)
                    #ysmean = numpy.mean(ysarray)
                    for key in ysfull: #for each yval at the new closest point
                        if (ysfull[key] >= self.stddevstate):
                            #this key should be printed and highlighted
                            print "channel ", key, " is above sig val."
                            self.stdsel.append((key, self.lines[key][0].get_color())) #a tuple of key and old color
                            self.lines[key][0].set_color(Color(102,255,51))
                            self.lines[key][0].set_linewidth(4) #make the affected lines blue and wider
                    
                    self.canvas.draw()
                    self.stddevstate = 0 #reset the state switch for the next right click
                
            if event.button==3:
                for (key, color) in self.stdsel: #reset the blue lines if we aren't in stdsel state anymore
                    self.lines[key][0].set_color(color)
                    self.lines[key][0].set_linewidth(1)
                self.stdsel = []
                        
                # recall that the dict ysfull should have all of the y values at the closest plotted point to the click for each channel indexed by key
                ysarray = numpy.zeros([len(ysfull)])
                for key in ysfull:
                    print "key: ", key, " = ", ysfull[key]
                print "Clicked at (%d, %d)" %(x, y)
                self.statBar.set_text("Clicked at (%d, %d)" %(x, y))
                ysarray = ysfull.values()
                ysstd = numpy.std(ysarray)
                ysmean = numpy.mean(ysarray)
                ysstd99_above = ysstd * 2.33 + ysmean #any y value above this range is significant compared to the range here
                self.stddevstate = ysstd99_above #save the sig val for the next left click
                print "stddevstate: ", self.stddevstate
                self.statBar.set_text("Clicked at (%f, %f), producing a 99 perc. over std dev val of %f" %(x, y, self.stddevstate))
        return False
    
    def button_release_event(self, event):
        self.canvas.draw()
        return False
    
    def lines2ms(self, lines):
        if not self.datares:
            error_msg("header error in dumpfile: data res not set!")
        return (lines*self.datares/self.eegfreq)*1000
    def lineaxis2ms(self, lines):
        if not self.datares:
            error_msg("header error in dumpfile: data res not set!")
        ll = copy.deepcopy(lines)
        lenll = len(ll)
        for i in arange(0,lenll):
            kk = (i*self.datares/self.eegfreq)*1000
            ll[i] = kk
        return ll
    def ms2lines(self, ms):
        if not self.datares:
            error_msg("header error in dumpfile: data res not set!")
        return (ms/1000)*self.eegfreq/self.datares
            
    def read_data(self, df, length, opt):
    
        def progress_callback(frac,  msg):
                if frac<0 or frac>1: return
                self.progBar.set_fraction(frac)
                while gtk.events_pending(): gtk.main_iteration()
        #file looks like:
        #'E1,E2,delta 1-4,theta 4-8,alpha 8-12,beta 12-30,gamma 30-50,high gamma 70-100,delta phase,theta phase,alpha phase,beta phase,gamma phase,high gamma phase'    
        #the spec is a dict from name of trode to list containing numsamples (for each band!) and sumsamples
        #and a dict from time to above dict
        f = open(df, 'rb')
        nl = length
        i = 0
        offcounter = 0
        trodelist = []
        tr = {}
        skip = 0
        tnext = 0
        cc = 0
        sweeplen = 0
        while 1:
            if (i != cc and i%10 == 0):
                progress_callback(i/nl, "almost done..")
            line = f.readline()
            if (i > nl):
                break
            if (line == ""):
                break
            if (skip >= 1):
                if (skip == 1):
                    if (sweeplen != 0):
                        if (sweeplen != int(line)):
                            error_msg("invalid dump file: changing sweep length")
                    else:
                        sweeplen = int(line) #set the sweeplength and make sure it stays the same
                skip = 0
                continue
            if (tnext == 1):
                tnext = 0
                tcur = int(line)
                if (offcounter < 10):
                    offcounter += 1
                if (offcounter == 10):
                        offcounter += 1
                        self.datares = tcur/9 #figure out how sharp the data dump is (set during autopaging).
                        print "coh_explor: datares: ", self.datares
                        self.lengthEntry.set_text(str(self.lines2ms(self.length))) #should give 12 (the default) lines in ms
                        #note: later I will make a new data format that assumes all params set initially, with no inner headers.
                #print "current time is ", tcur
                tr = copy.deepcopy(tr) #trodes is a dict from name of trode to tuple containing numsamples and sumsamples. copies are important.
                tr = {} #get ready
                trodelist.append(tr) #add  tr to the list of data
                
                #print "appended new list at index ", i
                
                self.t_data[tcur] = trodelist[i] #add the time to the dict, get ready to add the trodes data at that time
                i += 1
                continue
            cc = copy.deepcopy(i)    
            if (line[0] == '['):
                if (line[1:5] == 'swee'):
                    skip = 1
                    continue
                elif (line[1:5] == 'leng'):
                    skip = 2
                    continue
                elif (line[1:5] == 'offs'):
                    tnext = 1
                    continue
            line = line.split(',')
            zstart = 0
            zend = 1
            cstart = 2
            cend = 8
            if (opt == 'coh'):
                cstart = 2
                cend = 8
            if (opt == 'phase'):  
                cstart = 9
                cend = 14
            if (opt == 'cohphase'):
                cstart = 2
                cend = 14                
            
            for col in arange(cstart,cend): #change nan to 0
                if (math.isnan(float(line[col]))):
                    line[col] = 0 
            for z in (zstart,zend):
                if opt == 'cohphase':
                    if (line[z] in tr):
                        pass
                    else:
                        tr[line[z]] = map(float,line[cstart:cend]) #just grab the whole thing as a different point each time
                else:
                    if (line[z] in tr):
                        item = tr[line[z]]
                        item[0] += 1
                        item[1] = [ab+ac for ab,ac in zip(item[1], map(float,line[cstart:cend]))] #add the new data, for all bands
                    else:
                        tr[line[z]] = [1, map(float,line[cstart:cend])]
            
        f.close()
        #self.lengthEntry.set_text(str(self.lines2ms(self.length)))
        
    def make_fig(self, band):
        #this function modifies self.fig
        self.fig.clear()
        
        
        self.lines = {}
        col = self.bandlist.index(band)#find the band's index for the t_data
        N = len(self.channels)
        if (self.opt != 'cohphase'):
            self.ax = self.fig.add_subplot(111, autoscaley_on=True, yscale='linear', adjustable='box') 
            #self.ax = axes.Axes(self.fig, rect=)
            #self.ax.set_ylim(0,.1, auto=True)
        if (self.opt == 'cohphase'):
            self.ax = p3.Axes3D(self.fig)
        self.ax.set_yscale('linear')
        if self.buttonNorm.get_active():
            self.ax.set_ylim(.5,.5) #silly hack to get the norm to autoscale better
        #self.ax.set_frame_on(False)
        self.ax.set_autoscaley_on(True)
        self.cursor = Cursor(self.ax, useblit=True, linewidth=1, color='white')
        self.cursor.horizOn = True
        self.cursor.vertOn = True
        colordict = ['#A6D1FF','green','red','cyan','magenta','yellow','orange']
        keys = self.t_data.keys()
        keys = sorted(keys)
        del keys[-1] #for some reason the last time key is coming out null sometimes in the data?
        dumpchans = self.t_data[0].keys()
        counter = 0
        xdata = []
        ydata = []
        
        
        #print "chankeys: ", self.t_data[0]
        for i in self.t_data[0]: #go through the ordered channel list one by one
            xdata.append([]) #keep all the channel data seperate
            ydata.append([])
            #print "this is the channelkey: ", i
            isplit = i.split(" ")
            isplit = isplit[0],int(isplit[1])
            #if not isplit in self.channels: #make sure the channel we plot is in the view3 display
                #print "channel error! on channel ", i
            color = colordict[((counter)%7)]
            
            #experimental section: preparing to normalize data
            sumY = 0
            oldX1 = 999
            for t in keys: #at each time point. we don't want to use more of t_data than is asked for. took out index: #[0:self.length]
                if (self.opt != 'cohphase'):
                    (ns,ss) = self.t_data[t][i] #get the data out
                    ssband = ss[col] #choose the band
                    x1 = ssband/ns #find the average
                    
                    if self.buttonNorm.get_active():
                        #experimental: to normalize
                        sumY += x1
                    
                    if self.buttonInst.get_active():
                        if oldX1 == 999:
                            oldX1 = x1 #if it's the first time, change is 0
                        change = abs(x1 - oldX1) #distance between last val and new val
                        oldX1 = x1 #set last val to new val
                        x1 = change #going to set xdata to change
                    
                    
                    xdata[counter].append(x1)
                if (self.opt == 'cohphase'):
                    ss = self.t_data[t][i] #get the data out
                    sscoh = ss[col]
                    ssphase = ss[col + 6]
                    #x1 = sscoh/ns
                    #y1 = ssphase/ns
                    xdata[counter].append(ssphase)
                    ydata[counter].append(sscoh)
            self.x_data[isplit] = xdata[counter] #save the channel's data into an organized dict of channels
            
            if self.buttonNorm.get_active():
                #experimental: find average
                sumY /= len(keys)
            
            if (self.opt != 'cohphase'):
                if self.buttonNorm.get_active():
                    #experimental: normalize data
                    avgdiff = sumY - .5
                    for u in range(len(keys)):
                        xdata[counter][u] -= avgdiff
                        #print "xdata at ", counter, ", ", u, " for ", i, " is ", xdata[counter][u]      
                        if xdata[counter][u] < .01:
                            print "smaller: ", counter, u, i, xdata[counter][u]
                           
                self.lines[isplit] = self.ax.plot(self.lineaxis2ms(keys), xdata[counter], color, label=(str(i))) #plot a channel """arange(len(xdata[counter]))""" """[0:self.length-1]"""
                #print "at time ", counter, "xdata has ", len(xdata[counter]), " channels."
            if (self.opt == 'cohphase'):
                self.lines[isplit] = self.ax.plot3D(ydata[counter], self.lineaxis2ms(keys), xdata[counter], color, label = (str(i)))
            counter += 1
        #if self.buttonNorm.get_active():
        
        self.ax.relim()
        self.ax.autoscale_view(tight=True,scalex=True, scaley=True)
        self.ax.patch.set_facecolor('black') #black bg
        #self.ax.set_ylim(bottom=.35,top=.75, auto=False)
        self.progBar.set_fraction(0)
        return
