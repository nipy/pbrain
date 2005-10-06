from __future__ import division
import os, pickle, sys
import vtk

import gtk
import gtk.glade
from gtk import gdk
from GtkGLExtVTKRenderWindowInteractor import GtkGLExtVTKRenderWindowInteractor
from GtkGLExtVTKRenderWindow import GtkGLExtVTKRenderWindow

from Numeric import array

from pbrainlib.gtkutils import error_msg, simple_msg, ProgressBarDialog,\
     str2posint_or_err, str2posnum_or_err, str2int_or_err
from shared import shared

import distutils.sysconfig



# We put all of our gtk signal handlers into a class.  This lets us bind
# all of them at once, because their names are in the class dict.
class GladeHandlers:
    def on_buttonDir_clicked(button=None):

            
        dialog = gtk.FileSelection('Choose image file directory')
        dialog.set_filename(shared.get_last_dir())
        dialog.set_transient_for(widgets['dlgReader'])
        dialog.set_filename(widgets['entryDir'].get_text())
        response = dialog.run()

        if response == gtk.RESPONSE_OK:
            dir = dialog.get_filename()
            if os.path.isdir(dir):
                widgets['entryDir'].set_text(dir)
                shared.set_file_selection(dir)
                dialog.destroy()
            else:            
                error_msg('%s is not a directory' % dir, dialog)
        else:
           dialog.destroy()

    def on_buttonOpenInfo_clicked(button=None):
                   
        dialog = gtk.FileSelection('Choose info file')
        dialog.set_transient_for(widgets['dlgReader'])
        dialog.set_filename(widgets['entryInfoFile'].get_text() or
                            shared.get_last_dir())
        response = dialog.run()
        fname = dialog.get_filename()
        dialog.destroy()
        if response == gtk.RESPONSE_OK:
           if widgets.load_params_from_file(fname):
              GladeHandlers.__dict__['on_buttonPreview_clicked']()
              shared.set_file_selection(fname)
        
    def on_buttonSaveAsInfo_clicked(button=None):

            
        dialog = gtk.FileSelection('Choose info file to save parameters to')
        dialog.set_transient_for(widgets['dlgReader'])
        dialog.set_filename(widgets['entryInfoFile'].get_text() or
                            shared.get_last_dir())
        response = dialog.run()
        fname = dialog.get_filename()
        dialog.destroy()
        if response == gtk.RESPONSE_OK:
            widgets.save_params_to_file(fname)
            shared.set_file_selection(fname)

    def on_buttonSaveInfo_clicked(button=None):

       fname = widgets['entryInfoFile'].get_text()
       if fname=='':
          GladeHandlers.__dict__['on_buttonSaveAsInfo_clicked']()
          return
       widgets.save_params_to_file(fname)

    def on_buttonPreview_clicked(button=None):
        
        pars = widgets.get_params()
        pars = widgets.validate(pars)
        if pars is None: return
        reader = widgets.get_reader(pars)
        inDim1, inDim2 = pars.dimensions
        
        outDim1, outDim2 = widgets.outDim
        scale1 = outDim1/inDim1
        scale2 = outDim2/inDim2
        resample = vtk.vtkImageResample()
        resample.SetInput(reader.GetOutput())
        resample.SetAxisMagnificationFactor(0, scale1)
        resample.SetAxisMagnificationFactor(1, scale2)
        
        widgets.viewer.SetInput(resample.GetOutput())
        widgets.preview.Render()

        # set up the scroll bars
        widgets['hscrollbarColorLevel'].set_range(0, 2000)
        widgets['hscrollbarColorLevel'].set_value(1000)
        widgets['hscrollbarColorWindow'].set_range(0, 6000)
        widgets['hscrollbarColorWindow'].set_value(2000)
        widgets['hscrollbarSlice'].set_range(0, pars.last-pars.first+1)
        widgets['hscrollbarSlice'].set_value(0.5*(pars.last-pars.first))

    def on_buttonOK_clicked(button=None):
       pass
       #widgets['dlgReader'].hide()

    
    def on_buttonCancel_clicked(button=None):
        gtk.main_quit()

    def on_radiobuttonDimOther_toggled(button=None):
        if button.get_active(): otherSens = 1
        else: otherSens = 0
        widgets['entryDim1'].set_sensitive(otherSens)
        widgets['entryDim2'].set_sensitive(otherSens)
        
    def on_radiobuttonBytes1_toggled(button=None):

        # if BMP is on, turn of the vol16 widgets
        if widgets['radiobuttonBytes1'].get_active(): sens = 0
        else: sens = 1

        group = widgets['radiobuttonOrderBig'].get_group()            
        for b in group:
            b.set_sensitive(sens)

        widgets['labelMask'].set_sensitive(sens)
        widgets['labelHeader'].set_sensitive(sens)
        widgets['entryMask'].set_sensitive(sens)
        widgets['entryHeader'].set_sensitive(sens)

    def on_hscrollbarColorWindow_value_changed(bar):        
        widgets.viewer.SetColorWindow(bar.get_value())
        widgets.preview.Render()

    def on_hscrollbarColorLevel_value_changed(bar):
        #print 'color level changed', bar.get_value()
        widgets.viewer.SetColorLevel(bar.get_value())
        widgets.preview.Render()

    def on_hscrollbarSlice_value_changed(bar):
        print 'slice #', bar.get_value()
        widgets.viewer.SetZSlice(int(bar.get_value()))
        widgets.preview.Render()

class WidgetsWrapper:
    gladeFile =  'image_reader.glade'
    def __init__(self):
    
        if os.path.exists(self.gladeFile):
            theFile = self.gladeFile
        else:
            theFile = os.path.join(
                distutils.sysconfig.PREFIX,
                'share', 'pbrain', self.gladeFile)

        self.widgets = gtk.glade.XML (theFile)
        self.widgets.signal_autoconnect(GladeHandlers.__dict__)
        #self['entryDir'].set_text('/home/jdhunter/python/examples/vtk/images/')
        self.outDim = 256, 256
        
        self.viewer = vtk.vtkImageViewer()
        
        self.preview = GtkGLExtVTKRenderWindow()
        self.preview.set_size_request(self.outDim[0], self.outDim[1])
        self.preview.show()

        self.renderer = self.viewer.GetRenderer()
        self.preview.GetRenderWindow().AddRenderer(self.renderer)
        self['vboxPreview'].pack_start(self.preview, False, False)
        self['vboxPreview'].reorder_child(self.preview, 1)
        
    # Gives us the ability to do: widgets['widget_name'].action()
    def __getitem__(self, key):
        return self.widgets.get_widget(key)

    def get_params(self):
        if widgets['radiobuttonDim256'].get_active(): dim = 256, 256
        elif widgets['radiobuttonDim512'].get_active(): dim = 512, 512
        elif widgets['radiobuttonDimOther'].get_active():
            dim = (widgets['entryDim1'].get_text(),
                   widgets['entryDim2'].get_text())

        
        if widgets['radiobuttonBytes1'].get_active():
            readerClass = 'vtkBMPReader'
        elif widgets['radiobuttonBytes2'].get_active():
            readerClass = 'vtkImageReader2'
        else: readerClass = None
        if widgets['radiobuttonOrderBig'].get_active(): order = 'big endian'
        elif widgets['radiobuttonOrderLittle'].get_active(): order = 'little endian'
        else: order = None


        p = Params()
        
        p.order = order
        p.readerClass = readerClass
        p.dimensions = dim
        p.dir = widgets['entryDir'].get_text()
        p.prefix = widgets['entryPrefix'].get_text()
        p.extension = widgets['entryExt'].get_text()
        p.pattern = widgets['entryPattern'].get_text()
        p.first = widgets['entryFirst'].get_text()
        p.last = widgets['entryLast'].get_text()
        p.dfov = widgets['entryDFOV'].get_text()
        p.spacing = widgets['entrySpacing'].get_text()
        p.header = widgets['entryHeader'].get_text()
        p.mask = widgets['entryMask'].get_text()

        return p

    def load_params_from_file(self, fname):
       dialog = self['dlgReader']
       try: s = file(fname, 'r').read()
       except IOError:
          error_msg('Could not open %s for reading' % fname, dialog)
          return 0

       p = Params()
       p.from_string(s)

       widgets.set_params(p)     
       widgets['entryInfoFile'].set_text(fname)
       return 1

    def save_params_to_file(self, fname):
       """
       Pickle the params to file fname.  If successful return 1
       """

       dialog = self['dlgReader']

       pars = widgets.get_params()
       pars = widgets.validate(pars)
       if pars is None:
          error_msg('Invalid parameters')
          return 0

       try: fh = file(fname, 'w')
       except IOError:
          error_msg('Could not open %s for writing' % fname, dialog)
          return 0


       fh.write(str(pars))
       widgets['entryInfoFile'].set_text(fname)
       return 1

    def set_params(self, o):
       

       if o.readerClass=='vtkImageReader2': bytes2=1
       else: bytes2 = 0

       group = widgets['radiobuttonOrderBig'].get_group()            
       for b in group: b.set_sensitive(bytes2)
       widgets['labelMask'].set_sensitive(bytes2)
       widgets['labelHeader'].set_sensitive(bytes2)
       widgets['entryMask'].set_sensitive(bytes2)
       widgets['entryHeader'].set_sensitive(bytes2)

       if o.order == 'big endian':
          widgets['radiobuttonOrderBig'].set_active(1) 
       elif o.order == 'little endian':
          widgets['radiobuttonOrderLittle'].set_active(1)

       if bytes2:
          widgets['radiobuttonBytes2'].set_active(1) 
       else:
          widgets['radiobuttonBytes1'].set_active(1)



       if o.dimensions[0] == 256 and o.dimensions[1] == 256:
          widgets['radiobuttonDim256'].set_active(1)
       elif o.dimensions[0] == 512 and o.dimensions[1] == 512:
          widgets['radiobuttonDim512'].set_active(1)
       else:
          widgets['radiobuttonDimOther'].set_active(1)
          widgets['entryDim1'].set_text(str(o.dimensions[0]))
          widgets['entryDim2'].set_text(str(o.dimensions[1]))


       if os.path.isdir(o.dir):
          widgets['entryDir'].set_text(o.dir)

       widgets['entryPrefix'].set_text(o.prefix)
       widgets['entryExt'].set_text(o.extension)
       widgets['entryPattern'].set_text(o.pattern)
       widgets['entryFirst'].set_text(str(o.first))
       widgets['entryLast'].set_text(str(o.last))
       widgets['entryDFOV'].set_text(str(o.dfov))
       widgets['entrySpacing'].set_text(str(o.spacing))

       widgets['entryHeader'].set_text(str(o.header))

       if o.mask is not None: mask = str(o.mask)
       else: mask = ''
       widgets['entryMask'].set_text(mask)

    def validate(self, o):
        dlg = self['dlgReader']

        if len(o.pattern)==0:
            msg = 'You must supply a number pattern for entry %s.\n' % \
                  self['labelPattern'].get_label() + 'Consider "%d"'
            return error_msg(msg, dlg)

        if o.pattern[0]!='%':
            msg = '%s format string must begin with a %%.\n' % \
                  self['labelPattern'].get_label() + 'Consider "%d"'
            return error_msg(msg, dlg)

        if widgets['radiobuttonDimOther'].get_active():
            dim1, dim2 = o.dimensions
            val = dim1 = str2posint_or_err(dim1, 'Other: dimension 1', dlg)
            if val is None: return None
            val = dim2 = str2posint_or_err(dim2, 'Other: dimension 2', dlg)
            if val is None: return None
            o.dimensions = dim1, dim2
            
            
        val = o.first = str2int_or_err(o.first, widgets['labelFirst'], dlg)
        if val is None: return None

        val = o.last = str2posint_or_err(o.last, widgets['labelLast'], dlg)
        if val is None: return None

        fnames = self.get_file_names(o)
        for fname in fnames:
            if not os.path.exists(fname):
                return error_msg('Could not find file %s' % fname, dlg)
            if o.readerClass=='vtkBMPReader':
                reader = vtk.vtkBMPReader()
                b = reader.CanReadFile(fname)
                if not b:
                    return error_msg('Could not read file %s with reader %s'
                                     % (fname, o.readerClass), dlg)

        # Depth Field Of View
        val = o.dfov = str2posnum_or_err(o.dfov, widgets['labelDFOV'], dlg)
        if val is None: return None

        # Spacing between slices
        val = o.spacing = str2posnum_or_err(
            o.spacing, widgets['labelSpacing'], dlg)
        if val is None: return None

        # Size of header
        if o.header=='': o.header = 0
        else:
           val = o.header = str2int_or_err(
              o.header, widgets['labelHeader'], dlg)
           if val is None: return None

        # Data mask
        if o.mask is not None:
           if o.mask=='': o.mask = None

           else:
               val = o.mask = str2int_or_err(
                   o.mask, widgets['labelMask'], dlg)
               if val is None: return None

        return o
    
    def get_file_names(self, o):
        fnames = []

        if os.path.isdir(o.dir): dir = o.dir
        else:
           infopath = widgets['entryInfoFile'].get_text()
           dir, fname = os.path.split(infopath)
        

        fmt = os.path.join( dir, o.prefix ) + o.pattern
        if len(o.extension) > 0:
            fmt += '.' + o.extension

        #print fmt
        for i in range(o.first, o.last+1):
            fname = fmt %i
            fnames.append(fname)
        return fnames
    
    def get_reader(self, o):
       
        reader = get_reader(o)
        self.reader = reader
        return reader

    def get_color_level(self):
        return self['hscrollbarColorLevel'].get_value()

    def get_color_window(self):
        return self['hscrollbarColorWindow'].get_value()

    def get_slice_number(self):
        return self['hscrollbarSlice'].get_value()


def get_reader(o):

    if o.readerClass=='vtkBMPReader':
        ReaderClass = vtk.vtkBMPReader
    elif o.readerClass=='vtkImageReader2':
        ReaderClass = vtk.vtkImageReader2
    reader = ReaderClass()
    
    if ReaderClass==vtk.vtkImageReader2:
        reader.SetDataScalarTypeToUnsignedShort()
        if o.order=='big endian':
            reader.SetDataByteOrderToBigEndian()
        else:
            reader.SetDataByteOrderToLittleEndian()
        rows, cols = o.dimensions
        reader.SetFileNameSliceOffset(o.first)
        reader.SetDataExtent(0, rows-1, 0, cols-1, 0, o.last-o.first)
        reader.FileLowerLeftOn()
        if o.mask is not None:
            reader.SetDataMask(o.mask)

        if o.header!=0:
            reader.SetHeaderSize(o.header)


    elif ReaderClass==vtk.vtkBMPReader:
         reader.SetDataExtent(0, o.dimensions[0]-1,
                              0, o.dimensions[1]-1,
                              o.first, o.last)
    else:
        raise NotImplementedError, "Can't handle reader %s" % o.readerClass


    if sys.platform != 'darwin':
        progressDlg = ProgressBarDialog(title='Loading files',
                                        parent=widgets['dlgReader'],
                                        msg='Almost there....',
                                        size=(300,40)
                                        )
        progressDlg.show()

        def progress(r, event):
            #print 'abort progress', r.GetAbortExecute()
            val = r.GetProgress()
            progressDlg.bar.set_fraction(val)            
            if val==1: progressDlg.destroy()
            while gtk.events_pending(): gtk.main_iteration()


        reader.AddObserver('ProgressEvent', progress)


    if os.path.isdir(o.dir): dir = o.dir
    else:
       infopath = widgets['entryInfoFile'].get_text()
       dir, fname = os.path.split(infopath)
    
    reader.SetFilePrefix(dir)
    pattern = os.path.join( '%s', o.prefix + o.pattern )
    if len(o.extension) > 0:
        pattern += '.' + o.extension
    reader.SetFilePattern(pattern)
    reader.SetDataSpacing(o.dfov/o.dimensions[0],
                          o.dfov/o.dimensions[1],
                          o.spacing )
    reader.Update()
    return reader


class Params:
   """
   order         big endian|little endian (str)
   readerClass   vtkBMPReader|vtkImageReader2 (str)
   dimensions    dim1 dim2 (int int)
   dir           pathname  (str)
   prefix        prefix    (str)
   extension     extension (str)
   pattern       format    (str)
   first         int
   last          int
   dfov          float
   spacing       float
   header        int
   mask          hexint
   """
   order         = 'little endian'
   readerClass   = 'vtkImageReader2'
   dimensions    = 512, 512
   dir           = ''
   prefix        = ''
   extension     = '.raw'
   pattern       = '%d'
   first         = 1
   last          = 100
   dfov          = 25.0
   spacing       = 0.5
   header        = 0
   mask          = None

   def __repr__(self):

      lines = [
         'order       : %s' % self.order,
         'readerClass : %s' % self.readerClass,
         'dimensions  : %d %d' % self.dimensions,
         'dir         : %s' % self.dir,
         'prefix      : %s' % self.prefix,
         'extension   : %s' % self.extension,
         'pattern     : %s' % self.pattern,
         'first       : %d' % self.first,
         'last        : %d' % self.last,
         'dfov        : %1.3f' % self.dfov,
         'spacing     : %1.3f' % self.spacing,
         'header      : %d' % self.header,
         'mask        : %s' % self.mask,
         ]
      return '\n'.join(lines)

   def from_string(self, s):

      def twoints(s):
         return [int(val) for val in s.split()]

      def int_or_none(s):
         try: return int(s)
         except ValueError: return None

      converters = {
         'dimensions' : twoints,
         'first'      : int,
         'last'       : int,
         'dfov'       : float,
         'spacing'    : float,
         'header'     : int_or_none,
         'mask'       : int_or_none,
         }
      for line in s.split('\n'):
         if not len(line) or line.startswith('#'): continue
         key, val = line.split(':', 1)
         key = key.strip()
         val = val.strip()
         self.__dict__[key] = converters.get(key, str)(val)
         
         
         
         
         


widgets = WidgetsWrapper()


