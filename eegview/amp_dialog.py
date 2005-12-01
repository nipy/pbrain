from __future__ import division
import sys, os, math
import vtk

import gtk, gobject

from data import Amp


class AmpDialog(gtk.Dialog):
    def __init__(self, channels):
        gtk.Dialog.__init__(self, 'Channel num to electrode mapping')

        self.channels = channels
        self.numChannels = len(channels)
        
        self.set_size_request(300,600)
        scrolledWin = gtk.ScrolledWindow()
        scrolledWin.show()
        self.vbox.pack_start(scrolledWin, True, True)

        vbox = gtk.VBox()
        vbox.show()
        scrolledWin.add_with_viewport(vbox)        

        table=gtk.Table(self.numChannels+1, 3)
        table.set_col_spacings(3)
        table.show()
        vbox.pack_start(table, True, True)

        labelCnum = gtk.Label('Channel')
        labelCnum.show()

        labelName = gtk.Label('Grid name')
        labelName.show()
        labelNum = gtk.Label('Grid num')
        labelNum.show()

        table.attach(labelCnum, 0, 1, 0, 1,
                     xoptions=gtk.EXPAND, yoptions=gtk.EXPAND)
        table.attach(labelName, 1, 2, 0, 1,
                     xoptions=gtk.EXPAND, yoptions=gtk.EXPAND)
        table.attach(labelNum, 2, 3, 0, 1,
                     xoptions=gtk.EXPAND, yoptions=gtk.EXPAND)
        entries = []
        for i,cnum in enumerate(channels):
            label = gtk.Label('%d' % cnum)
            label.show()
            entryName = gtk.Entry()
            entryName.show()
            entryName.set_width_chars(10)
            entryNum = gtk.Entry()
            entryNum.show()
            entryNum.set_width_chars(10)
            table.attach(label, 0, 1, i+1, i+2,
                         xoptions=gtk.EXPAND, yoptions=gtk.EXPAND)
            table.attach(entryName, 1, 2, i+1, i+2,
                         xoptions=gtk.EXPAND, yoptions=gtk.EXPAND)
            table.attach(entryNum, 2, 3, i+1, i+2,
                         xoptions=gtk.EXPAND, yoptions=gtk.EXPAND)
            entries.append((label, entryName, entryNum))

        self.entries = entries
            
        frame = gtk.Frame('Auto fill')
        frame.show()
        vbox.pack_start(frame, True, True)
        frame.set_border_width(5)

        vboxFrame = gtk.VBox()
        vboxFrame.show()
        frame.add(vboxFrame)
        
        table = gtk.Table(2,3)
        table.set_col_spacings(3)
        table.set_row_spacings(3)
        table.show()
        vboxFrame.pack_start(table, True, True)
        
        label = gtk.Label('Grid name')
        label.show()
        entryGname = gtk.Entry()
        entryGname.show()
        entryGname.set_width_chars(10)
        table.attach(label, 0, 1, 0, 1,
                     xoptions=gtk.EXPAND, yoptions=gtk.EXPAND)
        table.attach(entryGname, 0, 1, 1, 2,
                     xoptions=gtk.EXPAND, yoptions=gtk.EXPAND)

        labelStart = gtk.Label('Chan# Start')
        labelStart.show()
        entryStart = gtk.Entry()
        entryStart.show()
        entryStart.set_width_chars(10)
        entryStart.set_text('1')
        
        table.attach(labelStart, 1, 2, 0, 1,
                     xoptions=gtk.EXPAND, yoptions=gtk.EXPAND)
        table.attach(entryStart, 1, 2, 1, 2,
                     xoptions=gtk.EXPAND, yoptions=gtk.EXPAND)

        labelEnd = gtk.Label('Chan# End')
        labelEnd.show()
        entryEnd = gtk.Entry()
        entryEnd.show()
        entryEnd.set_width_chars(10)
        entryEnd.set_text('%d'%len(entries))
        
        table.attach(labelEnd, 2, 3, 0, 1,
                     xoptions=gtk.EXPAND, yoptions=gtk.EXPAND)
        table.attach(entryEnd, 2, 3, 1, 2,
                     xoptions=gtk.EXPAND, yoptions=gtk.EXPAND)

        def fill_it(button):
            gname = entryGname.get_text()
            cstart = str2int_or_err(entryStart.get_text(), labelStart, parent=self)

            if cstart is None: return
            cend = str2int_or_err(entryEnd.get_text(), labelEnd, parent=self)
            if cend is None: return

            cnt = 1

            if cend>len(entries):
                #TODO: i not defined
                error_msg('Channel #%d out of range' % i, parent=self)
                return


            for i in range(cstart, cend+1):
                label, ename, enum = entries[i-1]
                ename.set_text(gname)
                enum.set_text('%d'%cnt)
                cnt += 1
            
        button = gtk.Button(stock=gtk.STOCK_EXECUTE)
        button.show()
        vboxFrame.pack_start(button, False, False)

        button.connect('clicked', fill_it)


        self.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        self.add_button(gtk.STOCK_OK, gtk.RESPONSE_OK)

    def get_amp(self):
        
        while 1:
            response = self.run()

            if response==gtk.RESPONSE_OK:
                trodes = []
                for i, tup in enumerate(self.entries):
                    label, ename, enum = tup
                    gname = ename.get_text()
                    if not len(gname):
                        error_msg('Empty grid name on channel %d' % i+1, parent=self)
                        break
                    gnum = str2int_or_err(enum.get_text(), label, parent=self)
                    if gnum is None: break
                    trodes.append( (i+1, gname, gnum) )
                else:
                    self.hide()
                    amp = Amp()
                    amp.extend(trodes)
                    return amp
            else:
                self.hide()
                return
                    

                
                
        



