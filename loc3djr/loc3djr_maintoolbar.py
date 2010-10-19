import gtk
import os 
from shared import shared
from vtksurface import VTKSurface

from pbrainlib.gtkutils import MyToolbar, FileManager
from image_reader import widgets, GladeHandlers
from events import EventHandler, UndoRegistry, Viewer

from afni_read import afni_header_read

import pickle

class MainToolbar(MyToolbar):
    """
    CLASS: MainToolbar
    DESCR: 
    """

    toolitems = (
        ('CT Info', 'Load new 3d image', gtk.STOCK_NEW, 'load_image'),
        #('MRI Info', 'Load new 3d MRI', gtk.STOCK_NEW, 'load_mri'),
        ('Load VTK File', 'Load new VTK mesh', gtk.STOCK_NEW, 'load_vtk'),
        ('Load Registration file', 'Load .reg file', gtk.STOCK_NEW, 'load_registration'),
        ('Electrodes', 'Load markers from file', gtk.STOCK_OPEN, 'load_from'),
        ('Save', 'Save markers', gtk.STOCK_SAVE, 'save'),
        ('Save as ', 'Save markers as new filename', gtk.STOCK_SAVE_AS, 'save_as'),
        ('Save registration as', 'Save registration as new filename', gtk.STOCK_SAVE_AS, 'save_registration_as'),
        (None, None, None, None),
        ('Toggle ', 'Toggle labels display', gtk.STOCK_BOLD, 'toggle_labels'),
        ('Choose', 'Select default marker color', gtk.STOCK_SELECT_COLOR, 'choose_color'),
        (None, None, None, None),
        ('Undo', 'Undo changes', gtk.STOCK_UNDO, 'undo_last'),
        (None, None, None, None),
        ('Properties', 'Set the plane properties', gtk.STOCK_PROPERTIES, 'set_properties'),
        ('Surface', 'Set the surface rendering properties', gtk.STOCK_PROPERTIES, 'show_surf_props'),
        ('Correlation', 'Display Correlations', gtk.STOCK_PROPERTIES, 'show_correlation_props'),
        )


    def __init__(self, owner):
        MyToolbar.__init__(self)

        self.owner = owner

        # set the default color
        da = gtk.DrawingArea()
        cmap = da.get_colormap()
        self.lastColor = cmap.alloc_color(0, 0, 65535)
        # self.build_prop_dialog()
                                    
    def show_surf_props(self, button):
        self.owner.dlgSurf.show()

    def load_correlation_from(fname):
        # opening .mat file with correlation info
        x = scipy.io.loadmat(fname)
        y = x['func_proj']
        print "ch_cmap is " , y.ch_cmap
        print "ch_idx is " , y.ch_idx
        print "ch_names is " , y.ch_names
        print "corr_mat is " , y.corr_mat
        print "disp_data is" , y.disp_data


    def show_correlation_props(self, button):
        dialog = gtk.FileChooserDialog('Choose filename for correlation data')
        dialog.set_filename(shared.get_last_dir())

        dialog.show()
        response = dialog.run()

        if response==gtk.RESPONSE_OK:
            fname = dialog.get_filename()
            dialog.destroy()
            try: EventHandler().load_correlation_from(fname)
            except IOError:
                error_msg(
                    'Could not load correlation from %s' % fname, 
                    )
            
            else:
                shared.set_file_selection(fname)
                self.fileName = fname
        else: dialog.destroy()


    def undo_last(self, button):
        UndoRegistry().undo()

    def toggle_labels(self, button):
        if EventHandler().get_labels_on():                
            EventHandler().set_labels_off()
        else:
            EventHandler().set_labels_on()

    def get_plane_widgets(self):
        pwx = self.owner.pwxyz.pwX
        pwy = self.owner.pwxyz.pwY
        pwz = self.owner.pwxyz.pwZ
        return pwx, pwy, pwz

    def get_markers(self):
        return EventHandler().get_markers()

    def build_prop_dialog(self):
        dlg = gtk.Dialog('Properties')
        #dlg.set_size_request(400,200)

        vbox = dlg.vbox

        frame = gtk.Frame('Opacity')
        frame.show()
        frame.set_border_width(5)
        vbox.pack_start(frame, False, False)


        table = gtk.Table(2,2)
        table.set_homogeneous(False)
        table.show()
        table.set_col_spacings(3)
        table.set_row_spacings(3)
        table.set_border_width(3)
        frame.add(table)

        #EitanP -  start
        frame_size = gtk.Frame('Markers Size')
        frame_size.show()
        frame_size.set_border_width(5)
        vbox.pack_start(frame_size, False, False)

        table_size = gtk.Table(2,2)
        table_size.set_homogeneous(False)
        table_size.show()
        table_size.set_col_spacings(3)
        table_size.set_row_spacings(3)
        table_size.set_border_width(3)
        frame_size.add(table_size)
        #EitanP -  end

        label = gtk.Label('Plane')
        label.show()

        def set_plane_opacity(bar):
            pwx, pwy, pwz = self.get_plane_widgets()
            val = bar.get_value()
            pwx.GetTexturePlaneProperty().SetOpacity(val)
            pwx.GetPlaneProperty().SetOpacity(val)
            pwy.GetTexturePlaneProperty().SetOpacity(val)
            pwy.GetPlaneProperty().SetOpacity(val)
            pwz.GetTexturePlaneProperty().SetOpacity(val) 
            pwz.GetPlaneProperty().SetOpacity(val)
            self.owner.pwxyz.Render()

        scrollbar = gtk.HScrollbar()
        scrollbar.show()
        scrollbar.set_range(0, 1)
        scrollbar.set_value(1)
        scrollbar.connect('value_changed', set_plane_opacity)
        scrollbar.set_size_request(300,20)
        
        table.attach(label, 0, 1, 0, 1)
        table.attach(scrollbar, 1, 2, 0, 1)

        label = gtk.Label('Markers')
        label.show()

        def set_marker_opacity(bar):
            val = bar.get_value()
            for marker in EventHandler().get_markers_as_seq():
                marker.GetProperty().SetOpacity(val)
            
            self.owner.pwxyz.Render()

        scrollbar = gtk.HScrollbar()
        scrollbar.show()
        scrollbar.set_range(0, 1)
        scrollbar.set_value(1)
        scrollbar.connect('value_changed', set_marker_opacity)
        scrollbar.set_size_request(300,20)
        
        table.attach(label,          0, 1, 1, 2)
        table.attach(scrollbar,      1, 2, 1, 2)

        #EitanP -  start
        label = gtk.Label('Markers')
        label.show()
        
        def set_marker_size(bar):
            val = bar.get_value()
            for marker in EventHandler().get_markers_as_seq():
                marker.set_size(val)
            self.owner.pwxyz.Render()            
                        
            self.owner.pwxyz.Render()

        scrollbar_size = gtk.HScrollbar()
        scrollbar_size.show()
        scrollbar_size.set_range(0, 20)
        scrollbar_size.set_value(1)
        scrollbar_size.connect('value_changed', set_marker_size)
        scrollbar_size.set_size_request(300,20)
        table_size.attach(scrollbar_size, 0, 1, 1, 2)
        #EitanP -  end        

        button = gtk.Button('Hide')
        button.show()
        button.set_use_stock(True)
        button.set_label(gtk.STOCK_CANCEL)
        
        def hide(button):
            self.propDialog.hide()
            return True

        button.connect('clicked', hide)
        vbox.pack_start(button, False, False)

        dlg.hide()
        self.propDialog = dlg

    def set_properties(self, *args):
        self.build_prop_dialog()
        self.propDialog.show()

    def load_mri(self, *args):
        # XXX: not currently used
        dialog = gtk.FileSelection('Choose .HEAD file')
        dialog.set_transient_for(widgets['dlgReader'])
        dialog.set_filename(widgets['entryInfoFile'].get_text() or
                            shared.get_last_dir())
        response = dialog.run()
        fname = dialog.get_filename()
        dialog.destroy()
        if response == gtk.RESPONSE_OK:
            d = afni_header_read(fname)
            brik_dimensions = d['DATASET_DIMENSIONS']
            print "header.ORIGIN: ", d['ORIGIN']
            print "header.DATASET_DIMENSIONS: ", d['DATASET_DIMENSIONS']
            print "header.HISTORY_NOTE: ", d['HISTORY_NOTE']
            print "header.DELTA: ", d['DELTA']
            brik_xdim = brik_dimensions[0]
            brik_ydim = brik_dimensions[1]
            brik_zdim = brik_dimensions[2]

            print fname
            base, ext = os.path.splitext(fname)
            brik_fname= "%s.BRIK" % base
            brikfile = file(brik_fname)
            brikfile.seek(0,2)
            brikfile_length = brikfile.tell()
            print "brikfile_length is " , brikfile_length, "divided by xdim*ydim is " , (float(brikfile_length))/(float(brik_xdim)*float(brik_ydim))
            print brikfile

            
    def load_vtk(self, *args):
        
        dialog = gtk.FileSelection('Choose .vtk file')
        dialog.set_transient_for(widgets['dlgReader'])
        dialog.set_filename(widgets['entryInfoFile'].get_text() or
                            shared.get_last_dir())
        response = dialog.run()
        fname = dialog.get_filename()
        dialog.destroy()
        if response == gtk.RESPONSE_OK:
            print "loading vtk file: " , fname
            # this constructor adds the mesh to the renderer
            self.owner.pwxyz.vtksurface = VTKSurface(fname, self.owner.pwxyz.renderer)
        
        
    def load_image(self, *args):
        print "loc3djr_maintoolbar.load_image()"
        debug = False
        reader = None

        pars = None
        
        if debug:
            reader = vtk.vtkImageReader2()
            reader.SetDataScalarTypeToUnsignedShort()
            reader.SetDataByteOrderToLittleEndian()
            reader.SetFileNameSliceOffset(120)
            reader.SetDataExtent(0, 511, 0, 511, 0, 106)
            reader.SetFilePrefix('/home/jdhunter/seizure/data/ThompsonK/CT/raw/1.2.840.113619.2.55.1.1762864819.1957.1074338393.')
            reader.SetFilePattern( '%s%d.raw')
            reader.SetDataSpacing(25.0/512, 25.0/512, 0.125 )

            reader.Update()
        else:
    
            dlg = widgets['dlgReader']

            response = dlg.run()

            if response == gtk.RESPONSE_OK:
                try: reader = widgets.reader
                except AttributeError: 
                    pars = widgets.get_params()
                    pars = widgets.validate(pars)
                    if pars is None:
                        error_msg('Could not validate the parameters', dlg)
                        return
                    reader = widgets.get_reader(pars)
                pars = widgets.get_params()
                pars = widgets.validate(pars)
                
            dlg.hide()


        print "reader=", reader
        if not reader:
            print "hit cancel, see if we can survive"
        else:
            imageData = reader.GetOutput()
            print "pars=", pars
            print "loc3djr_maintoolbar.load_image(): reader.GetOutput() is " , imageData
            print "load_image(): imageData.SetSpacing(", reader.GetDataSpacing(), " )"
            imageData.SetSpacing(reader.GetDataSpacing())
            print "calling EventHandler().notify('set image data', imageData)"
            EventHandler().notify('set image data', imageData)
            

    def save_as(self, button):

        def ok_clicked(w):
            fname = dialog.get_filename()
            shared.set_file_selection(fname)
            try: EventHandler().save_markers_as(fname)
            except IOError:
                error_msg('Could not save data to %s' % fname,
                          )
            else:
                self.fileName = fname
                dialog.destroy()
            
        dialog = gtk.FileSelection('Choose filename for marker')
        dialog.set_filename(shared.get_last_dir())
        dialog.ok_button.connect("clicked", ok_clicked)
        dialog.cancel_button.connect("clicked", lambda w: dialog.destroy())
        dialog.show()

    def load_registration(self, *args):
        dialog = gtk.FileSelection('Choose .reg file')
        dialog.set_transient_for(widgets['dlgReader'])
        dialog.set_filename(widgets['entryInfoFile'].get_text() or
                            shared.get_last_dir())
        response = dialog.run()
        fname = dialog.get_filename()
        dialog.destroy()
        if response == gtk.RESPONSE_OK:
            print "loading reg file: " , fname
            reg_filename = fname
            registration_mat = pickle.load(file(reg_filename, 'r'))
            print "load_registration(): dude registration_mat is ", registration_mat
            # XXX mcc arghhghhh
            self.owner.pwxyz.vtksurface.set_matrix(registration_mat)

    def save_registration_as(self, button):
        def ok_clicked(w):
            fname = dialog.get_filename()
            shared.set_file_selection(fname)
            try: EventHandler().save_registration_as(fname)
            except IOError:
                error_msg('Could not save data to %s' % fname,
                          )
            else:
                self.fileName = fname
                dialog.destroy()
            
        dialog = gtk.FileSelection('Choose filename for registration .reg data file')
        dialog.set_filename(shared.get_last_dir())
        dialog.ok_button.connect("clicked", ok_clicked)
        dialog.cancel_button.connect("clicked", lambda w: dialog.destroy())
        dialog.show()

    def save(self, button):
        try: self.fileName
        except AttributeError:
            self.save_as(button=None)
        else: EventHandler().save_markers_as(self.fileName)

    def load_from(self, button):
	dialog = FileManager() #modernizing the dialog box
	dialog.set_lastdir(shared.get_last_dir())	
	fname = dialog.get_filename('Choose filename for marker info')
        #dialog = gtk.FileSelection()
        
        #dialog.show()        
        #response = dialog.run()
        
        #if response==gtk.RESPONSE_OK:
        #    fname = dialog.get_filename()
        #    dialog.destroy()
        try: EventHandler().load_markers_from(fname)
        except IOError:
            error_msg(
                'Could not load markers from %s' % fname, 
                )
        else:
            shared.set_file_selection(fname)
            self.fileName = fname
        #else: dialog.destroy()
        

    def choose_color(self, button):
        dialog = gtk.ColorSelectionDialog('Choose default marker color')
            
        colorsel = dialog.colorsel

        
        colorsel.set_previous_color(self.lastColor)
        colorsel.set_current_color(self.lastColor)
        colorsel.set_has_palette(True)
    
        response = dialog.run()
        
        if response == gtk.RESPONSE_OK:
            color = colorsel.get_current_color()
            self.lastColor = color
            EventHandler().set_default_color(self.get_normed_rgb(color)) #DEBUG
        dialog.destroy()
	print "******************", EventHandler().get_default_color()

    def get_normed_rgb(self, c):
        color = map(lambda x: x/65536.0, (float(c.red), float(c.green), float(c.blue))) #fixed color bug by switching to floats -eli
	#print "this should be a decimal between 0 and 1", color
	return color


