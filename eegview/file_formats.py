from __future__ import division

import math, re, os, sys, string
try:
	set
except:
	from sets import Set as set
	
import pygtk
pygtk.require('2.0')
import gtk, gobject

from datetime import date, time
import data
from struct import unpack


import numpy

from scipy import fromstring, arange

import datetime

from scipy import zeros, array

import re

def mask(charlist):
        """Construct a mask suitable for string.translate,
        which marks letters in charlist as "t" and ones not as "b" """
        mask=""
        for i in range(256):
                if chr(i) in charlist: mask=mask+"t"
                else: mask=mask+"b"
        return mask

ascii7bit=string.joinfields(map(chr, range(32,127)), "")+"\r\n\t\b"
ascii7bit_mask=mask(ascii7bit)


class FileFormat_AlphaomegaAscii:
    """
    CLASS: FileFormat_AlphaomegaAscii
    DESCR: Reads ASCII-exported data files from the 'Alpha Omega' software
    """
    def get_channel_maps(self, ascfile):
        channel_name_map = {}
        channel_num_map = {}
        channel_sr_map = {}
        channel_count = {} 
        while 1:
            ascline = ascfile.readline()
            if not ascline:
                print "FOUND EOF"
                break
            p = re.compile('[\ \t]*')
            #asc_split = ascline.split('\t')
            asc_split = p.split(ascline)
            if ((asc_split[0] == 'Info') & (asc_split[1] == 'Digital')):
                #print asc_split
                pass
            elif ((asc_split[0] == 'Info') & (asc_split[1] == 'Contin')):
                # looks like this: ['Info', 'Contin', '20001', '25.00000000', '502', 'Micro_1', '\r\n']
                channel_number = int(asc_split[2])
                channel_name = asc_split[5]
                #print "channel_name = " , channel_name
                channel_name_map[channel_number] = channel_name
                channel_num_map[channel_name] = channel_number
                channel_count[channel_number] = 0
                sampling_rate = float(asc_split[3]) * 1000.0
                channel_sr_map[channel_number] = sampling_rate
                #print "sampling_rate = ", sampling_rate 
            elif (asc_split[0] == ('Contin')):
                # looks like this: ['Contin', '20001', '35188800', '-520', '-248', ...]
                channel_number = int(asc_split[1])
                channel_count[channel_number] = channel_count[channel_number] + (len(asc_split)-3)
                #print "found" , len(asc_split)-3, "values for channel ", channel_name_map[channel_number], "total: ", channel_count[channel_number]
        print "channel_name_map: ", channel_name_map
        for k,v in channel_count.iteritems():
            print channel_name_map[k], ":", v, channel_sr_map[k]
        return channel_name_map, channel_num_map, channel_sr_map, channel_count

    def fill_channel_data(self, ascfile, channel_data_to_fill, arbitrary_channel_map, channel_name_map):
        channel_count = {}
        data_index_starts = {}
        data_index_ends = {}
        for k, v in arbitrary_channel_map.iteritems():
            channel_count[v] = 0
            data_index_starts[v] = 0
            data_index_ends[v] = 0
        print "arbitrary_channel_map = ", arbitrary_channel_map
        while 1:
            ascline = ascfile.readline()
            if not ascline:
                print "FOUND EOF"
                break
            p = re.compile('[\ \t]*')
            asc_split = p.split(ascline)
            if (asc_split[0] == ('Contin')):
                # looks like this: ['Contin', '20001', '35188800', '-520', '-248', ...]
                channel_number = int(asc_split[1])
                if not arbitrary_channel_map.has_key(channel_number):
                    continue
                index = arbitrary_channel_map[channel_number]
                values = asc_split[3:]
                float_values = map(float, values)
                float_values_array = array(float_values, 'f')
                #print "float_values_array is type " , type(float_values_array), float_values_array[0:10]
                #sys.exit()
                
                
                #print "values are: ", values
                #print "adding to index " , index
                data_index_ends[index] = data_index_starts[index] + len(values)
                if ((data_index_ends[index]- data_index_starts[index]) != len(float_values)):
                    assert(0) # not inserting the right values for some line
                #print "channel_data[%d(%s), %d:%d]= %d values" % (index, channel_name_map[channel_number], data_index_starts[index],data_index_ends[index], len(float_values))
                channel_data_to_fill[index, data_index_starts[index]:data_index_ends[index]] = float_values
                channel_count[index] = channel_count[index] + (len(asc_split)-3)
                data_index_starts[index] = data_index_ends[index]
        
    
    def __init__(self, path):
        ascfile = file(path)
        beginning_position = ascfile.tell() 
        topline = ascfile.readline()
        #print "FileFormat_AlphaomegaAscii(): top line is: ", topline
        p = re.compile('[\ \t\r\n]*')
        top_split = p.split(topline)
        #print "FileFormat_AlphaomegaAscii(): top split is: ", top_split
        # ['C:\\Logging_Data\\A2112001.map', 'Thr', '21/12/2005', '21:39:21', '']
        date_str = top_split[2]
        time_str = top_split[3]
        date_split = date_str.split('/')
        time_split = time_str.split(':')
        alphaomegadate = datetime.datetime(int(date_split[2]), int(date_split[1]), int(date_split[0]), int(time_split[0]), int(time_split[1]), int(time_split[2])) 
        
        
        
        channel_name_map, channel_num_map, channel_sr_map, channel_count = self.get_channel_maps(ascfile)
        ascfile.seek(0) 
        ascline = ascfile.readline()
        print "FileFormat_AlphaomegaAscii(): top line is this crap ", ascline

        # XXX: arbitrarily choose which channels to take
        #dbs_0_channelname = 'DBS_0'
        dbs_0_channelname = 'LFP_1'

        print "channel_num_map is ", channel_num_map
        dbs0_num = channel_num_map[dbs_0_channelname]
        arbitrary_sr = channel_sr_map[dbs0_num]
        arbitrary_ndatapts = channel_count[dbs0_num]
        arbitrary_channel_list = []
        arbitrary_channel_map = {}
        i = 0
        for k,v in channel_count.iteritems():
            if (channel_sr_map[k] == arbitrary_sr):
                arbitrary_channel_list.append(k)
                arbitrary_channel_map[k]= i
                i = i + 1

        print "channels with appropriate sampling rate: ", arbitrary_channel_list

        print "allocating channel_data of size (%d, %d)" % ( len(arbitrary_channel_list), arbitrary_ndatapts)
        channel_data = zeros((len(arbitrary_channel_list), arbitrary_ndatapts), 'f')


        self.fill_channel_data(ascfile, channel_data, arbitrary_channel_map, channel_name_map)

        print "WHOA ok channel_data[0,0:10] looks like", channel_data[0, 0:10]

        amp = data.Amp()
        amp_channels = []
        i = 1
        for k,v in arbitrary_channel_map.iteritems():
            print "appending (", i, channel_name_map[k], k, ")"
            amp_channels.append((i, channel_name_map[k], k))
            i = i + 1
        amp.extend(amp_channels)
        
        params = {
            'date' : alphaomegadate,
            'filename' : path,     
            'channels' : len(arbitrary_channel_list),
            'freq' : arbitrary_sr,
            'file_type': 8,
            'raw_data': channel_data
        }

        self.eeg = data.EEGFileSystem(path, amp, params)
        

    
class FileFormat_NeuroscanAscii:
    """
    CLASS: FileFormat_NeuroscanAscii
    DESCR: Parses ASCII file exported from the 'Neuroscan' software
    """
    electrode_labels = []
    channel_names = []
    channel_numbers = []
    zerochans = []
    newchannels = []

    def istext(self, file, check=1024, mask=ascii7bit_mask):
        """Returns true if the first check characters in file
        are within mask, false otherwise"""

        try:
            s=file.read(check)
            s=string.translate(s, mask)
            if string.find(s, "b") != -1: return 0
            return 1
        except (AttributeError, NameError): # Other exceptions?
            return istext(open(file, "r"))



    def parse_electrode_labels(self, ascline):
        electrode_strs = ascline.split ('\t')
        #print electrode_strs, len(electrode_strs)
        for i in electrode_strs:
            #print "i is " , i
            # somehow drop leading whitespace from the string after the bracket
            p = re.compile('\[\ *(.*)\]')
            m =  p.match(i)
            if (m):
                curr_electrode_label =  m.groups(0)[0]
                #print "FileFormat_NeuroscanAscii(): curr_electrode_label =", curr_electrode_label
                self.electrode_labels.append(curr_electrode_label)


        #print "electrode_labels: " , self.electrode_labels
        for i in self.electrode_labels:
            j = 0
            while (j < len(i)):
                if (i[j] == ' '):
                    j+=1
                    break #we shouldn't have any leading whitespace here, see above
                if (i[j] in string.ascii_letters):
                    j+=1
                    continue #labels should all start with letters
                if (i[j] in string.digits):
                    start = i[0:j]
                    end = i[j:]
                    full = start + ' ' + end #add in the missing space already
                    print "file_format found spaceless label, changing to: ", full
                    i = full
                    break                       
            electrode_label_split = i.split(' ')
            # special case for when the electrode name is just one string - -b
            # put 'NS' in front arbitrarily. (XXX: for Sozari, kind of wack)
            #print "len(electrode_label_split)=",len(electrode_label_split)
            if (len(electrode_label_split) == 1):
                electrode_label_split = ['NS', electrode_label_split[0]]
            self.channel_names.append(electrode_label_split[0])
            print "electrode_label_split = ", electrode_label_split, "appending"
            self.channel_numbers.append(int(electrode_label_split[1]))

    def parse_sampling_rate(self, ascline):
        sr_strs = ascline.split ('\t')
        print "parse_sampling_rate(): ", sr_strs, len(sr_strs)
        self.sampling_rate = float(sr_strs[1])
        
    def chanbutswitch(self, widget, channelnum):
        if widget.get_active():
            self.zerochans.append(channelnum)
        else:
            self.zerochans.remove(channelnum)
        print self.zerochans
        
    def numbify(self, widget, *args):
        text = widget.get_text().strip()
        widget.set_text(''.join([i for i in text if i in '0123456789']))
               
    def manipulate_channels(self,n_channels,channels,channel_data):
        #right here we will have a new functionality that allows adding zeroed channels and taking out channels, with user input. -eli
        
        
        dlg = gtk.Dialog("Channel Manipulation")
        dlg.connect("destroy", dlg.destroy)
        dlg.set_size_request(400,400)
        scrolled_window = gtk.ScrolledWindow(None, None)
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        dlg.vbox.pack_start(scrolled_window, True, True, 0)
        scrolled_window.show()

        table = gtk.Table(2,(1+len(self.electrode_labels)))
        table.set_row_spacings(8)
        table.set_col_spacings(8)
        scrolled_window.add_with_viewport(table)
        table.show()
        #attach format: obj, beg end x, beg end y
        l1 = gtk.Label("zero?            channel")
        l1.show()

        l2 = gtk.Label("    added zeroed channels:")
        l2.show()

        table.attach(l1,0,1,0,1)
        table.attach(l2,1,2,0,1)
        #an array to control the check boxes
        chanbuts = []
        for i in range(0, len(self.electrode_labels)):
            s1 = "                %s" % (channels[i],)
            chanbuts.append(gtk.CheckButton(s1))
            chanbuts[i].show()
            chanbuts[i].connect("toggled", self.chanbutswitch, channels[i][0])
            table.attach(chanbuts[i], 0,1,i+1,i+2)
            
        dlg.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        dlg.add_button(gtk.STOCK_OK, gtk.RESPONSE_OK)
        dlg.add_button("Add zero channel", 32) #32 is my favorite number
        dlg.set_default_response(gtk.RESPONSE_OK)
    
        dlg.show()
        
        nc = 0
        while 1:
            
            response = dlg.run()
    
            
            if response==32:
                n_channels+=1
                #here we want to add a new channel.
                dlg2 = gtk.Dialog("Add a zeroed channel")
                dlg2.connect("destroy", dlg2.destroy)
                dlg2.set_size_request(300,100)
                table2 = gtk.Table(3,2)
                table2.show()
                table2.set_row_spacings(4)
                table2.set_col_spacings(4)
                linput = gtk.Label("channel num:")
                linput.show()
                lgnum = gtk.Label("grid number:")
                lgnum.show()
                lgname = gtk.Label("grid name:")
                lgname.show()
                ecnum = gtk.Entry()
                ecnum.set_width_chars(3)
                ecnum.connect('changed', self.numbify)
                ecnum.set_text("%d" % n_channels)
                ecnum.show()
                egnum = gtk.Entry()
                egnum.set_width_chars(3)
                egnum.connect('changed', self.numbify) #make sure we only get numbers here
                egnum.show()
                egname = gtk.Entry()
                egname.set_width_chars(3)
                egname.show()
                
                table2.attach(linput,0,1,0,1)
                table2.attach(lgname,1,2,0,1)
                table2.attach(lgnum,2,3,0,1)
                table2.attach(ecnum,0,1,1,2)
                table2.attach(egname,1,2,1,2)
                table2.attach(egnum,2,3,1,2)
                dlg2.vbox.pack_start(table2, True, True)
                
                dlg2.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
                dlg2.add_button(gtk.STOCK_OK, gtk.RESPONSE_OK)
                
                dlg2.set_default_response(gtk.RESPONSE_OK)
                dlg2.show()
                while 1:
                    response2 = dlg2.run()
    
                    if response2==gtk.RESPONSE_OK:
                        nc +=1
                        #here take the newly gathered userinput info and apply it
                        self.newchannels.append((int(ecnum.get_text()),egname.get_text().strip(),int(egnum.get_text())))
                        l3 = gtk.Label(self.newchannels[nc-1])
                        l3.show()
                        table.attach(l3,1,2,nc, nc+1)
                        dlg2.destroy()
                        break
                    if response2==gtk.RESPONSE_CANCEL:
                        n_channels-=1
                        dlg2.destroy()
                        break
                
            if response==gtk.RESPONSE_OK:
                dlg.destroy()
                #here take the newly gathered userinput info and apply it    
                #we'll zero out the chosen channels first, so that when we insert new ones, things still line up
                
                for i in self.zerochans:
                    print "zeroing out channel ", i
                    #z should be the row of zero-indexed channel_data array corresponding to all of the data for the channel we want to zero
                    z = channel_data[i-1,:]
                    z[:] = 0
                    #this is a hacky fix for a documented bug in numpy whereby comparing large arrays of all zeroes with themselves throws a yucky, badly traced error. It should insignificantly effect calculations.                    
                    z[1] = .001
                
                #sort the newchannels list by channel number. otherwise they won't add correctly:
                self.newchannels = sorted(self.newchannels, key = lambda a: a[0])
                #the channels list is a mess to work with, so I'll make it more useful temporarily:
                tempchannels = []
                for chan in channels:
                    tempchannels.append((chan[1],chan[2]))
                
                cc = 0
                varried = 50
                #now to insert the new channels + zeroed data IN THE RIGHT PLACE hopefully                            
                for newchan in self.newchannels:
                    #fix the raw data with the new zeros, hopefully inserting a column into the array
                    nz = numpy.zeros((len(channel_data[1])))
                    #this is a temporary test to check the validity of the coherence calculations. 
                    #I am adding a sin wave to every zeroed out channel that we add on with the 
                    #add button, but only in parts of the range, not the whole thing.
                    #but since we are looking at averaged sweeps, I'm going to add it on every 7 seconds or 
                    #3584 points.
                    #varried starts at 50 and is subsequently 64
                    """
                    ind = arange(varried,len(channel_data[1])-3584+.01,3584)
                    print "FILE_FORMATS: testing sin wave with index: ", ind
                    for index in ind:
                        r = 0
                        while r < 50:
                            nz[index+r] = math.sin((math.pi/180)*r)
                            r = r+1
                    print "FILE_FORMATS: testing with added column nz: "
                    for n in nz:
                        print "NZ! ", n
                    varried = 64
                    """
                    #this is the end of the test block
                    
                    nz[1] = .001 #this is the same hack as just above
                    #print "nz.shape, channel_data.shape, newchan[0]", nz.shape, channel_data.shape, newchan[0]
                    if newchan[0] <= channel_data.shape[0]:
                        channel_1, channel_2 = numpy.vsplit(channel_data,[newchan[0] - 1 + cc])
                        #print "make sure columns are split right: ", channel_1.shape, channel_2.shape
                        channel_data = numpy.vstack((channel_1, nz, channel_2))
                    else:
                        channel_data = numpy.vstack((channel_data,nz))
                    
                    #put the new channel info in
                    tempchannels.insert(newchan[0]-1 + cc, (newchan[1], newchan[2]))
                    cc += 1
                finalchannels = []
                for i in range(0,len(tempchannels)):
                    #add the indexes back into these tuples
                    finalchannels.append((i + 1, tempchannels[i][0], tempchannels[i][1]))
                channels = finalchannels 
                break
                        
            if response==gtk.RESPONSE_CANCEL:
                n_channels -= len(self.newchannels) #unwind any added zerochans
                self.newchannels = []
                self.zerochans = []
                dlg.destroy()
                #don't actually use the new userinput info
                break
        return n_channels, channels, channel_data


    def __init__(self, path):
        newheader = 0
        almostdone = 0
        line_count = 0
        with open(path) as ascfile:
            for line in ascfile:
                found_eof = 0
                n_channels = -1
        
                ascline = line.strip()
                #the following few lines are a hack to get around a problem I've been having with random EOFs strangely peppered through neuroscanascii files before the true EOF -eli
                if not ascline:
                    almostdone = 1
                    continue
                if almostdone == 1:
                    if not ascline:
                        break
                    else:
                        almostdone = 0
                if (ascline[0] == '['):
                    # on initial parse, grab "electrode_labels" (a.k.a. "channels" for Amp class)
                    if newheader == 1:
                        print "parsing electrode_labels: ",ascline
                        electrode_labels = self.parse_electrode_labels(ascline)
                        newheader = 0
                    #skip to the next line:
                    if (ascline == '[Electrode Labels]'):
                        newheader = 1
                    
                    elif (ascline.find('[Rate]') == 0):
                        sampling_rate = self.parse_sampling_rate(ascline)
                else:
                    if (n_channels == -1):
                        n_channels = len(ascline.split('\t'))
                    else:
                        if (n_channels != len(ascline.split('\t'))):
                            print "wtf , got %d channels but already had %d n_channels", (len(ascline.split('\t')), n_channels)
                    line_count = line_count + 1

        print "line_count is " , line_count
        #changing channel data to a numpy array
        #default dtype is numpy.float64
        #note: tested for validity; also seems to speed up program noticably
        channel_data = numpy.zeros((n_channels, line_count))
        print "channel_data.shape is " , channel_data.shape

        line_count = 0
        almostdone = 0
        with open(path) as ascfile:
            for line in ascfile:
                ascline = line.strip()
                if almostdone == 1:
                    if not ascline:
                        break
                    else:
                        almostdone = 0
                if not ascline:
                    almostdone = 1
                    continue
                elif (ascline[0] == '['):
                    continue
                asc_split = ascline.split('	')
                # we now have n_channels channel values which basically consist of a column of data in channel_data, sweet
                #slicing works pretty much the same for numpy arrays
                #print asc_split[0:n_channels]
                channel_data[:, line_count] = map(float, asc_split[0:n_channels])
                line_count += 1

        #"ok, done with channel_data. assigned " , channel_assign_count, " channels"
        print "new linecount!! ", line_count
        amp = data.Amp()

        channels = []
                        
        for i in range(0, len(self.electrode_labels)):
            print "appending to channels " , ((i+1, self.channel_names[i], self.channel_numbers[i]))
            channels.append((i+1, self.channel_names[i], self.channel_numbers[i]))

        print "electrode_labels = ", self.electrode_labels
        print "channels = ", channels
        
        n_channels, channels, channel_data = self.manipulate_channels(n_channels,channels,channel_data)
        #pass forward the zeroed channel info so that coherence results aren't skewed!
        #self.zerochans.append(self.newchannels)
            
        amp.extend(channels)

        params = {
            'date' : datetime.datetime.now(),
            'filename' : path,     
            'channels' : n_channels,
            'freq' : self.sampling_rate,
            'file_type': 7,
            'raw_data': channel_data
        }


        print "called amp.extend(channels); amp=", amp

        self.eeg = data.EEGFileSystem(path, amp, params)


                
class FileFormat_AxonAscii:
    """
    CLASS: FileFormat_AxonAscii
    DESCR: Parses ASCII file exported from the 'Axon' software
    """
    def __init__(self, path):
        """
        Given a .axonascii filename, create a EEGFileSystem object w/ appropriate member variables
        (e.g. date, filename, channels, freq, fiel_type, raw_data)

        This is ugly, but so is the file format.
        """
        ascfile = file(path)
        ascfile.readline() # skip blank line
        ascfile.readline() # skip blank line
        name_line = ascfile.readline().split(": ")
        name = ((name_line[1])[:-2])
        #print "load_axonascii(): name is \'%s\'" % name
        date_line = ascfile.readline().split(":  ")
        date = (date_line[1])[:-2]
        [datestamp, timestamp] = date.split(", ")
        axondate = self.get_axondate(datestamp, timestamp)
        #print "load_axonascii(): date is", axondate # we want to use the first date in the data stream, though, not this one

        ampset = set()
        n_channels = 0
        channels = []
        n_lines = 0

        beginning_position = ascfile.tell()

        # do loop to determine # of channels and their indices/names.. and also to find sampling rate!
        curr_amp_num = 1 # we fake the "amplifier" indices
        
        old_axondate = None
        have_calculated_sr = False
        sampling_rate = -1

        sampling_rate_counter = 0
        sampling_rate_counter_channel = -1
    
        while 1:
            ascline = ascfile.readline()
            asc_split = ascline.split(',')
            if (len(asc_split) <2): # last (presumably blank) line
                break

            #curr_amp_num = int(asc_split[0])  # mcc XXX
            channel_str = asc_split[1]
            channel_str = re.sub('\"', '', channel_str)
            channel_str_split = channel_str.split(':')
            curr_channel_num = int(channel_str_split[0])
            curr_channel_name = channel_str_split[1]
        
            curr_axondate = self.get_axondate(asc_split[2], asc_split[3])
        
            curr_vals = (asc_split[4:])

            #if curr_amp_num in ampset:
            if curr_channel_num in ampset:
                if (have_calculated_sr == False):
                    #print "load_axonascii(): ", curr_channel_num, "curr_axondate = ", curr_axondate, " and old_axondate=", old_axondate, "len(curr_vals)=", len(curr_vals)
                    #print "load_axonascii(): curr-old axondates=", curr_axondate - old_axondate, type(curr_axondate-old_axondate)
                    if (round(float((curr_axondate-old_axondate).seconds)) == 0):
                        if (sampling_rate_counter_channel == -1):
                            #print "initializing sampling_rate_counter_channel=", curr_channel_num, "with value ", len(curr_vals)
                            sampling_rate_counter_channel = curr_channel_num
                            sampling_rate_counter += len(curr_vals)
                        elif (sampling_rate_counter_channel == curr_channel_num):
                            #print "got another bunch of ", len(curr_vals) , "on sampling_rate_counter_channel=", sampling_rate_counter_channel
                            sampling_rate_counter += len(curr_vals)
                        
                    else:
                        # mcc: XXX should this next if statement be commented ?? this seems necessary for certain example files
                        #if (sampling_rate_counter == 0):
                        sampling_rate_counter += len(curr_vals)
                        sampling_rate = float(sampling_rate_counter)/float((curr_axondate-old_axondate).seconds)
                        print "load_axonascii(): sampling rate = " , float(sampling_rate_counter), "/ " , float((curr_axondate-old_axondate).seconds) , "=",  sampling_rate
                        have_calculated_sr = True
                n_channels = len(ampset)
            else:
                #print "load_axonascii(): axon channel %d/%s: read %d vals at date %s" % (curr_channel_num, curr_channel_name, len(curr_vals), str(curr_axondate))
                old_axondate = curr_axondate
                #ampset.add(curr_amp_num)
                ampset.add(curr_channel_num)
                #print "load_axonascii(): adding to channels:  ", curr_amp_num, curr_channel_name, curr_channel_num
                channels.append((curr_amp_num, curr_channel_name, curr_channel_num))
                #print "load_axonascii(): adding %d/%s/%d" % (curr_amp_num, curr_channel_name, curr_channel_num)
            n_lines = n_lines + 1
            curr_amp_num += 1

        channel_data = zeros((n_lines, 500), 'f')

        #print "load_axonascii(): ok we found n_channels=%d" % (n_channels)

        # seek back to beginning
        ascfile.seek(beginning_position, 0)

        curr_line_num = 0
        # repeat until end of file...
        for ascline in ascfile:
            asc_split = ascline.split(',')
            if (len(asc_split) <2): # last (presumably blank) line
                break

            # XXX: we will be building a standard "Amp" class for eegview
            curr_amp_num = int(asc_split[0]) 

            channel_str = asc_split[1]
            channel_str = re.sub('\"', '', channel_str)
            channel_str_split = channel_str.split(':')
            curr_channel_num = int(channel_str_split[0])
            curr_channel_name = channel_str_split[1]
        
            curr_axondate = self.get_axondate(asc_split[2], asc_split[3])
            if (curr_line_num == 0):
                # save the first time! get_date() should now work on the EEGFileSystem object
                axondate = curr_axondate

            curr_vals = (asc_split[4:])

            #print "channel %d/%s: read %d vals at date %s" % (curr_channel_num, curr_channel_name, len(curr_vals), str(curr_axondate))

            index = 0
            for x in curr_vals:
                channel_data[curr_line_num][index] = float(x)
                index = index + 1

            #print "computed channel_data[%d] = " % curr_line_num, channel_data[curr_line_num][0:4], "..."
    
            curr_line_num = curr_line_num+1
        
        #print "n_channels = ", n_channels
        #print "and channels = ", channels
       
        params = {
            'date' : axondate,
            'filename' : path,     
            'channels' : n_channels,
            'freq' : sampling_rate,
            'file_type': 6,
            'raw_data': channel_data
        }

        amp = data.Amp()
        amp.extend(channels)

        #print "called amp.extend(channels); amp=", amp

        self.eeg = data.EEGFileSystem(path, amp, params)
    
        
    def get_axondate(self, axon_datestr, axon_timestr):
        """
        Given a date string and time string from the .axonascii format, return a datetime.datetime instance
        """
        [datestamp, timestamp] = [axon_datestr, axon_timestr]
        datestamp = re.sub('\"', '', datestamp)
        timestamp = re.sub('\"', '', timestamp)
        date_split = datestamp.split('/')
        time_split = timestamp.split(':')
        # mccXXX: this may not properly handle am/pm timestamp differences!
        axondate = datetime.datetime(int(date_split[2]), int(date_split[0]), int(date_split[1]), int(time_split[0]), int(time_split[1]), int(time_split[2])) 
        return axondate


    
    
  
class NeuroscanEpochFile:
    """
    CLASS: NeuroscanEpochFile
    DESCR: 
    """
    ### note we haven't implemented accepted/rejected sweeps
    def __init__(self, fname):

        rgx = re.compile('^\[([A-Za-z\s]+)\](.*)')
        header = {}
        fh = file(fname, 'r')
        while 1:
            line = fh.readline().strip()
            if not len(line): raise ValueError('Bad file')
            if line.startswith('[Epoch Header]'): break
            m = rgx.match(line)
            if m:
                key = m.group(1)
                val = m.group(2)
                #print line, key, val
                header[key] = val

        params = {
            'pid' : 0,
            'date' : header['Date'] + ' ' + header['Time'],
            'filename' : fname,     
            'description' : '',  
            'channels' : int(header['Channels']),
            'freq' : float(header['Rate']),
            'classification' : 99,
            'file_type' : 14,     
            'behavior_state' : 99, 
            }
        
        self.channels = params['channels']
        self.points = int(header['Points'])
        self.sweeps = int(header['Sweeps'])

        self.X = zeros((self.sweeps*self.points, self.channels), 'd')

        sweepnum = 0
        while 1:
            if line.startswith('[Epoch Header]'):
                self.parse_epoch(fh, sweepnum)
                sweepnum+=1                
            else:
                break
            line = fh.readline()

        params['epochdata'] = self.X
        self.eeg = data.EEGFileSystem(fname, params)

            
    def parse_epoch(self, fh, sweepnum):
        for i in range(5): junk = fh.readline()

        start = sweepnum*self.points
        for i in range(self.points):
            line  = fh.readline()            # a string
            vals = map(float, line.split())  # a list of floats
            #print sweepnum, start, i, self.X.shape
            self.X[start+i] = nx.array(vals)

class W18Header:
    """
    CLASS: W18Header
    DESCR: 
    """
    def __init__(self, fh): 

        self.name = unpack('19s', fh.read(19))[0].strip()
        self.oper = unpack('5s', fh.read(5))[0].strip()
        self.tapeno = unpack('7s', fh.read(7))[0].strip()
        self.eegno  = unpack('13s', fh.read(13))[0].strip()
        self.comment = unpack('16s', fh.read(16))[0].strip()

        self.starttime = unpack('l', fh.read(4))[0]
        self.endtime = unpack('l', fh.read(4))[0]
        self.reclength = unpack('l', fh.read(4))[0]
        self.currtime = unpack('l', fh.read(4))[0]

        self.rhythm = unpack('c', fh.read(1))[0]
        self.sigmodac = unpack('c', fh.read(1))[0]


        self.samplerate = unpack('B', fh.read(1))[0]
        self.numchannels = unpack('B', fh.read(1))[0]
        self.montagecode = unpack('B', fh.read(1))[0]
        self.dirty = unpack('B', fh.read(1))[0]
        self.online = unpack('B', fh.read(1))[0]
        self.recordlengthPnts = unpack('B', fh.read(1))[0]

        self.reserved = unpack('172s', fh.read(172))

class W18Record:
    """
    CLASS: W18Record
    DESCR: 
    """
    def __init__(self, s):
        self.data = fromstring(s[:18000], UInt8)
        self.data.shape = -1, 18
        self.timestamp = unpack('8s', s[18000:18008])[0].strip()    # char [8]
        self.rec_no = unpack('L', s[18008:18012])[0]        # unsigned long
        self.ux_time = unpack('L', s[18012:18016])[0]       # unsigned long
        self.smimage = unpack('8s', s[18016:18024])[0].strip()      # char [8]
        self.ox_rec_ptr = unpack('B', s[18024])[0]          # unsigned char
        self.oxes= unpack('64B', s[18025:18089])         # unsigned char [64]
        self.rates = unpack('64B', s[18089:18153])       # unsigned char [64]
        self.ox_acq_time = unpack('64H', s[18153:18281]) # unsigned int [64] (ushort?)
        self.filstruct = unpack('150s', s[18281:18431])[0].strip()  # char [150]


def get_w18_data(fh, indmin, indmax):
    block0 = int(math.floor(indmin/1000))
    block1 = int(math.floor(indmax/1000))

    a = zeros( (indmax-indmin, 18), UInt8)
    ind=0
    for i in range(block0, block1+1):
        if i==0: pos = 256
        else: pos = i*18432
        fh.seek(pos)
        s = fh.read(18432)
        if not len(s): raise ValueError('passed the end of file')
        record = W18Record(s)

        if block0==block1:
            a = record.data[indmin-block0*1000:indmax-block0*1000]
        elif i==block0:
            N = (block0+1)*1000 - indmin 
            a[:N] = record.data[-N:]
            ind = N
        elif i==block1:
            N = indmax-i*1000
            a[ind:ind+N] = record.data[:N]
        else:
            a[ind:ind+1000] = record.data
            ind += 1000
    return a.astype('d')
    #return a

def to_hertz(s):
    assert(s.find('Hz')>=0)
    val, hz = s.split()
    return float(val)

def parse_date(d):
    vals = d.split('/')
    assert(len(vals)==3)
    m,d,y = [int(val) for val in vals]
    return date(y,m,d)

def parse_time(t):
    vals = t.split(':')
    h = int(vals[0])
    m = int(math.floor(float(vals[1])))
    s = float(vals[1])
    seconds = int(s)
    micros = int((seconds%1)*1e6)
    return time(h, m, seconds, micros)

def int_or_none(s):
    try : return int(s)
    except ValueError: return None
    
def list_ints(s):

    return [int_or_none(val) for val in s.split(',')]

class FileFormat_BNI:
    """
    CLASS: FileFormat_BNI
    DESCR: Parses 'Nicolet' .BNI/.EEG file pair
    """

    keys = set(['FileFormat', 'Filename', 'Comment', 'PatientName',
                'PatientId', 'PatientDob', 'Sex', 'Examiner', 'Date',
                'Time', 'Rate', 'EpochsPerSecond', 'NchanFile',
                'NchanCollected', 'UvPerBit', 'MontageGaped',
                'MontageRaw', 'DataOffset', 'eeg_number',
                'technician_name', 'last_meal', 'last_sleep',
                'patient_state', 'activations', 'sedation',
                'impressions', 'summary', 'age', 'medications',
                'diagnosis', 'interpretation', 'correlation',
                'medical_record_number', 'location',
                'referring_physician', 'technical_info', 'sleep',
                'indication', 'alertness', 'DCUvPerBit', 'NextFile'])

    converters = {
        'PatientDob' : parse_date,
        'Date':  parse_date,
        'Time':  parse_time,
        'Rate':  to_hertz,
        'EpochsPerSecond':  float,
        'NchanFile':  int,
        'NchanCollected':  int,
        'UvPerBit':  float,
        'MontageGaped':  list_ints,
        'MontageRaw':  list_ints,
        'DataOffset':  int,
        'DCUvPerBit':  float,
        }

    rgxTrode = re.compile('([a-zA-Z]+)-*(\d*)')

    def __init__(self, bnifile):
        "Parse a bni file; bnih is a bni filename"

        self.params = {}

        assert(os.path.exists(bnifile))

        self.bnipath, self.bnifname = os.path.split(bnifile)
        bnih = file(bnifile, 'r')
        seen = {}  # make sure there are no duplicate labels
        errors = []
        self.labeld = {} # a dict from cnum to label
        channeld = {} # mapping from anum->(gname, gnum)        
        seenanum = {}
        for line in bnih:
            vals = line.split('=',1)
            if len(vals)==2 and vals[0].strip() in self.keys:
                key = vals[0].strip()
                val = vals[1].strip()                
                if not len(val): continue
                #print 'converting', key
                converter =  self.converters.get(key, str)
                self.params[key] = converter(val)
                if key=='NextFile':
                    break

                
            line = line.strip()
            if len(line)==0: continue
            vals = line.split('=')
            if len(vals)==2:
                self.__dict__[vals[0].strip()] = vals[1].strip()
                continue
                
            vals = line.split(',') #113,FZ,30,70,1,60,1,MONITOR

            
            if len(vals)==8:
                anum = int(vals[0])
                if anum in seenanum.keys():
                    print 'duplicate amp num', anum
                    print '\tNew: ', line
                    print '\tOld: ', seenanum[anum]
                seenanum[anum] = line
                trode = vals[1]
                if len(trode) and trode[0]=='0':
                    trode = 'O' + trode[1:]
                self.labeld[anum] = trode
                m = self.rgxTrode.match(trode)
                if m is not None:
                    gname = m.group(1)
                    num = m.group(2)
                    if len(num): gnum = int(num)
                    elif gname[-1]=='Z': gnum = 0
                    else:
                        errors.append('Empty electrode num on line\n\t%s' % line)
                        continue
                    key = (gname, gnum)
                    
                    if seen.has_key(key):
                        if gname.find('empty')<0: # dupicate empty channels ok
                            errors.append('Duplicate label %s %d on line %s' %(gname, gnum, line))
                            continue
                    else: seen[key]=1
                    channeld[anum] = (gname, gnum) 
                else:
                    errors.append("Error parsing BNI file on line: %s\n  Electrode labeled '%s' doesn't match pattern" % (line, trode))
            elif len(channeld):
                # end of the first montage
                break
            
            if len(channeld)>=self.params['NchanFile']:
                print >> sys.stderr, 'Found more channels than indicated; bni file says %d'%self.params['NchanFile']
                break
        
        if len(errors):
            print >>sys.stderr, 'Found the following nonfatal errors'
            for msg in errors:
                print msg

        self.channels = [ (key, val[0], val[1]) for key, val in channeld.items()]
        #print "FileFormat_BNI.__init__(): self.channels is " , self.channels
        self.channels.sort()

    def get_label(self, cnum):
        """
        Get the label for channel cnum.  cnum is the number from the
        BNI file, ie indexed from 1.  Label is the label from the BNI,
        not split into name, num.

        Return None if no label for that channel num
        """
        return self.labeld.get(cnum)

    def get_eeg(self, eegpath):

        assert(self.params.has_key('Filename'))
        #assert(len(self.channels)==self.params['NchanFile'])

        fullpath = self.params['Filename']
        amp = data.Amp()
        amp.extend(self.channels)

        if eegpath is None:
            raise RuntimeError('Could not find %s' % eegpath)

        if self.params.has_key('Date') and self.params.has_key('Time'):
            sd = self.params['Date'].strftime('%Y-%m-%d')
            st = self.params['Time'].strftime('%H:%M:%S')
            datestr = '%s %s' % (sd, st)

            basename, fname = os.path.split(eegpath)

        print "FileFormat_BNI.get_eeg(): date is ", datestr

        print "FileFormat_BNI.get_eeg(): channels is ", self.params['NchanFile']

        params = {
            'pid' : self.params.get('PatientId', 'Unknown'),
            'date' : datetime.datetime.combine(self.params['Date'], self.params['Time']),
            'filename' : fname,     
            'description' : self.params.get('Comment', ''),  
            'channels' : self.params['NchanFile'],     
            'freq' : self.params.get('Rate'),
            'classification' : 99,
            'file_type' : 1,     
            'behavior_state' : 99, 
            }

        eeg = data.EEGFileSystem(eegpath, amp, params)
        scale = self.params.get('UvPerBit', None)
        eeg.scale = scale
        eeg.amp = amp

        #print "FileFormat_BNI.get_eeg(): eeg.amp=", eeg.amp
        return eeg

def getbni(bnipath):
    bni = FileFormat_BNI(bnipath)
    basename, ext = os.path.splitext(bnipath)

    # sometimes there is an eeg ext, sometimes not
    if os.path.exists(basename):    
        fullpath = basename
    elif os.path.exists(basename + '.eeg'):
        fullpath = basename + '.eeg'


    # this returns a eegview.data.EEGFileSystem instance
    eeg = bni.get_eeg(fullpath)
    return bni, eeg
