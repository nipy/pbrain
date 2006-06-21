from __future__ import division
import sys, os, math

import gtk, gobject

from events import Observer

#from Numeric import fromstring, arange, Int16, Float, log10, zeros
from scipy import fromstring, arange, Int16, Float, log10, zeros
from scipy import arange, sin, pi, zeros, ones, reshape, Float, Float0, \
     greater_equal, transpose, array, arange, resize, Int16, \
     absolute, nonzero, rand


from matplotlib.figure import Figure
from matplotlib.backends.backend_gtkagg import FigureCanvasGTKAgg as FigureCanvas

import mpl_windows
from  mpl_windows import MPLWin

from utils import filter_grand_mean, all_pairs_eoi, cohere_bands, power_bands,\
     cohere_pairs, cohere_pairs_eeg, get_best_exp_params,\
     get_exp_prediction, read_cohstat

from matplotlib.mlab import detrend_none, detrend_mean, detrend_linear,\
     window_none, window_hanning, log2


class CoherenceWin(mpl_windows.MPLWin):
    _title = "Coherence for given channel"

    freq_min = 0
    freq_max = 250
        
    def __init__(self, eegplot):
        self.ylim = None

        MPLWin.__init__(self, eegplot)

        eois = self.eegplot.get_eoi()

        self.coh_make_toolbar()

    def get_msg(self, x,y):
        return  't = %1.2f, v=%1.2f' % (x, y)

    def freq_min_changed(self, entry):
        print "CoherenceWin.freq_min_changed", entry, ": value is " , int(entry.get_text())
        self.freq_min = int(entry.get_text())
        
        # XXX: cause make_plot() to recalculate in the same way that , say, paging the main eegview window does
        self.make_plot()

    def freq_max_changed(self, entry):
        print "CoherenceWin.freq_max_changed", entry, ": value is " , int(entry.get_text())
        self.freq_max = int(entry.get_text())

        # XXX: cause make_plot() to recalculate in the same way that , say, paging the main eegview window does
        self.make_plot()


    def coh_make_toolbar(self):
        # adding entries here for frequency band pass

        self.freq_entry1 = gtk.Entry()
        self.freq_entry1.set_width_chars(5)        
        self.freq_entry1.set_text('0')
        self.freq_entry1.show()
        self.freq_entry1.connect("activate", self.freq_min_changed)
        
        #toolbar.append_widget(self.freq_entry1, 'min freq', '')
        toolitem = gtk.ToolItem()
        toolitem.show()
        toolitem.set_tooltip(
            self.toolbar.tooltips,
            'min freq', 'Private')
        toolitem.add(self.freq_entry1)
        self.toolbar.insert(toolitem, -1)

        self.freq_entry2 = gtk.Entry()
        self.freq_entry2.set_width_chars(5)        
        self.freq_entry2.set_text('250')
        self.freq_entry2.show()
        self.freq_entry2.connect("activate", self.freq_max_changed)

        #toolbar.append_widget(entry1, 'min freq', '')
        toolitem = gtk.ToolItem()
        toolitem.show()
        toolitem.set_tooltip(
            self.toolbar.tooltips,
            'max freq', 'Private')
        toolitem.add(self.freq_entry2)
        self.toolbar.insert(toolitem, -1)

        
    def make_plot(self, *args):

        # get the old limits
        #self.axes.cla()
        # XXX: ?!?
        self.axes.grid(True)

        tup = self.get_data()
        if tup is None: return

        # ok but we also want to get the data for all NON-selected
        # electrodes, and then calculate coherence. ARGH. at the
        # very least, do this for all electrodes in the EOI!
        #
        # we will probably have to roll a lot of this by hand as
        # EEGPlot is not forthcoming about the content of non-selected channels.
        # conveniently it does however provide a get_eeg() function

        eois = self.eegplot.get_eoi()
        print "CoherenceWin.make_plot(): eois= ", eois

        eeg = self.eegplot.get_eeg()

        # get all the other vectors for non-selected EOI channels.
        #
        # we can start by getting everything (sigh)

        tmin, tmax = self.eegplot.get_time_lim()

        t, data = eeg.get_data(tmin, tmax)

        data2 = array(data)

        print "CoherenceWin: data2[100:110,1] is " , data2[100:110,1]

        electrode_to_indices_dict = eeg.get_amp().get_electrode_to_indices_dict()

        # now data[:, self.eegplot.indices[self.eegplot.eoiIndDict[eoi]]] is data for a given EOI eoi

        print "CoherenceWin.make_plot(): we have data2.shape " , data2.shape, " and eegplot._selected = ", self.eegplot._selected
        
        eoi_pairs = [(self.eegplot._selected, eoi) for eoi in eois]

        print "CoherenceWin.make_plot(): eoi_pairs=" , eoi_pairs

        Cxy, Phase, freqs, Pxx = self.compute_coherence(eeg, t, data2, eoi_pairs)

        i = 1
        axes = None
        self.fig.clear()
        for eoi_pair in eoi_pairs:
            coh_vec = Cxy.get(eoi_pair)

            #print "CoherenceWin.make_plot(): self.fig.add_subplot(%d,%d,%d)" % (len(Cxy), 1, i)
            axes = self.fig.add_subplot(len(Cxy),1,i)
            if (i==1):
                axes.set_title('Coherence for %s' % str(eoi_pair[0]))
            
            axes.set_ylabel("%s" % str(eoi_pair[1]), rotation='horizontal', fontsize=8)
            print "CoherenceWin.make_plot(): doing pair ", str(eoi_pair)
            
            print "CoherenceWin.make_plot(): dude coh_vec[0:20] is ", coh_vec[0:20], "freqs[0:20] = ", freqs[0:20]

            # mccXXX: all I want is a subrange of the freqs and the corresponding y values.
            # there is obviously some one-line way to do this. ask jdh sometime
            final_freqs = []
            for f in freqs:
                if ((f >= self.freq_min) & (f <= self.freq_max)):
                    final_freqs.append(f)
            final_freqs = array(final_freqs)

            print "freqs[0:10] look like this of length " , freqs[0:10], len(freqs)
            print "final_freqs[0:10] look like this of length " , final_freqs[0:10], len(final_freqs)

            if (eoi_pair[0] != eoi_pair[1]):
                # get color used in main EEG viewer
                axes.plot(freqs, coh_vec, self.eegplot.get_color(eoi_pair[1]))
            elif (eoi_pair[0] == eoi_pair[1]):
                axes.plot(freqs, coh_vec, 'r')

            axes.set_xlim(self.freq_min, self.freq_max)

            axes.set_ylim([-0.1, 1.1])

            if (i == 1):
                axes.set_yticks([1.0])
            elif (i == len(eoi_pairs)):
                axes.set_yticks([0.0])
            else:
                axes.set_yticks([])


            if (i != len(Cxy)):
                axes.set_xticklabels([])


            
            i = i + 1

        print "CoherenceWin.make_plot(): self.canvas.draw()!!!"
        self.canvas.draw()
        return 


    def compute_coherence(self, eeg, t, data, eoi_pairs):
        """
        **********************************************************************
        **********************************************************************
        """
        def progress_callback(frac,  msg):
            print msg, frac
            # XXX: make a progress bar ??
            #if frac<0 or frac>1: return
            #self.progBar.set_fraction(frac)
            #while gtk.events_pending(): gtk.main_iteration()
            
        dt = 1.0/eeg.freq
        Nt = len(t)
        NFFT = int(2**math.floor(log2(Nt)-2))
        oldnfft= NFFT
        print 'NFFT =', NFFT
        #NFFT = min(NFFT, 512)

        print "compute_coherence: Nt=", Nt, "doing NFFT=", NFFT, "instead of " , oldnfft

        #self.filterGM = None # XXX : should we add this button


        if self._filterGM:            
            data = filter_grand_mean(data)
        Cxy, Phase, freqs, Pxx = cohere_pairs_eeg(
            eeg,
            eoi_pairs,
            data = data,
            NFFT = NFFT,
            detrend = detrend_none,
            window = window_none,
            # MCCXXX: changing this arbitrarily to see what happens
            noverlap = 477,
            #noverlap = 0,
            #preferSpeedOverMemory = 1,
            preferSpeedOverMemory = False,
            progressCallback = progress_callback,
            returnPxx=True,
            )
        print "CoherenceWin.compute_coherence(): uhhh did that just work ? Cxy, Phase, freqs, Pxx:" , len(Cxy), len(Phase), freqs.shape, len(Pxx)
        # view3 does this stuff where we look at particular bands. we don't (yet)
        # 
        #
        #bands = ( (1,4), (4,8), (8,12), (12,30), (30,50), (70,100) )
        #cxyBands, phaseBands = cohere_bands(
        #    Cxy, Phase, freqs, eoi_pairs, bands,
        #    progressCallback=progress_callback,
        #    )
        #pxxBand = power_bands(Pxx, freqs, bands)

        return Cxy, Phase, freqs, Pxx
    
        
