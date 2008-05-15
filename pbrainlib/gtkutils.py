import os, sys
import errno, StringIO, traceback

import gobject, gtk
from gtk import gdk

import datetime

def is_string_like(obj):
    if hasattr(obj, 'shape'): return 0 # this is a workaround
                                       # for a bug in numeric<23.1
    try: obj + ''
    except (TypeError, ValueError): return 0
    return 1

def exception_to_str(s = None):

   sh = StringIO.StringIO()
   if s is not None: print >>sh, s
   traceback.print_exc(file=sh)
   return sh.getvalue()



def donothing_callback(*args):
    pass

class ProgressBarDialog(gtk.Dialog):
    "Use attribute bar to control the progress bar"
    def __init__(self, title, parent, msg='Almost there....', size=(300, 40)):
        gtk.Dialog.__init__(self, title=title, flags=gtk.DIALOG_MODAL)

        if parent is not None:
            self.set_transient_for(parent)

        self.bar = gtk.ProgressBar()
        self.bar.set_size_request(size[0], size[1])

        self.bar.set_text(msg)
        self.bar.set_fraction(0)
        self.bar.show()
        self.vbox.pack_start(self.bar)

def raise_msg_to_str(msg):
    """msg is a return arg from a raise.  Join with new lines"""
    if not is_string_like(msg):
        msg = '\n'.join(map(str, msg))
    return msg
    
def error_msg(msg, parent=None, title=None):
    dialog = gtk.MessageDialog(
        parent         = None,
        type           = gtk.MESSAGE_ERROR,
        buttons        = gtk.BUTTONS_OK,
        message_format = msg)
    if parent is not None:
        dialog.set_transient_for(parent)
    if title is not None:
        dialog.set_title(title)
    else:
        dialog.set_title('Error!')
    dialog.show()
    dialog.run()
    dialog.destroy()
    return None

def simple_msg(msg, parent=None, title=None):
    dialog = gtk.MessageDialog(
        parent         = None,
        type           = gtk.MESSAGE_INFO,
        buttons        = gtk.BUTTONS_OK,
        message_format = msg)
    if parent is not None:
        dialog.set_transient_for(parent)
    if title is not None:
        dialog.set_title(title)
    dialog.show()
    dialog.run()
    dialog.destroy()
    return None

def _get_label(l):
    if type(l)==type(''): return l
    else: return l.get_label()
        
def str2num_or_err(s, label, parent=None):
    "label can be a string or label widget"
    label = _get_label(label)
    try: return float(s)
    except ValueError:
        return error_msg('%s entry must be a number; you entered "%s"' %
                  (label, s), parent)

def str2posnum_or_err(s, labelWidget, parent=None):
    label = _get_label(labelWidget)
    val = str2num_or_err(s, labelWidget, parent)
    if val > 0 or val is None: return val

    msg = '%s must be a positive number.\nYou supplied "%s"' %\
          (label, s)

    return error_msg(msg, parent)

def str2negnum_or_err(s, labelWidget, parent=None):
    label = _get_label(labelWidget)
    val = str2num_or_err(s, labelWidget, parent)
    if val < 0 or val is None: return val

    msg = '%s must be a positive number.\nYou supplied "%s"' %\
          (label, s)

    return error_msg(msg, parent)

def str2int_or_err(s, labelWidget, parent=None):
    label = _get_label(labelWidget)
    try: return int(s)
    except ValueError:
        if s.find('0x')==0: # looks like hex
            try: return int(s, 16)
            except ValueError: pass
    except TypeError: pass
    msg = '%s must be an integer.\nYou supplied "%s"' %\
          (label, s)
    
    return error_msg(msg, parent)

def str2posint_or_err(s, labelWidget, parent=None):
    label = _get_label(labelWidget)
    val = str2int_or_err(s, labelWidget, parent)
    if val > 0 or val is None: return val

    msg = '%s must be a positive integer.\nYou supplied "%s"' %\
          (label, s)

    return error_msg(msg, parent)

def str2negint_or_err(s, labelWidget, parent=None):
    label = _get_label(labelWidget)
    val = str2int_or_err(s, labelWidget, parent)
    if val < 0 or val is None: return val

    msg = '%s must be a negative integer.\nYou supplied "%s"' %\
          (label, s)

    return error_msg(msg, parent)



class Dialog_FileChooser(gtk.FileChooserDialog):
    def __init__(self, defaultDir, okCallback, title='Select file',
                 parent=None, previous_dirnames=[]):
        """wrap some of the file selection boilerplate.  okCallback is
        a function that takes a Dialog_FileSelection instance as a
        single arg."""
        gtk.FileChooserDialog.__init__(self, action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                       buttons=(gtk.STOCK_CANCEL,
                                                gtk.RESPONSE_CANCEL,
                                                gtk.STOCK_OPEN,
                                                gtk.RESPONSE_OK),title=title, parent=parent)

        self.okCallback = okCallback

        self.connect('file-activated', self.okCallback)

        if (previous_dirnames[0]):
            self.set_current_folder(previous_dirnames[0])

        history_combobox = gtk.combo_box_new_text()
        for d in previous_dirnames:
            if (len(d) > 0):
                history_combobox.append_text(d)

        def history_combobox_changed(combobox):
            self.set_current_folder(combobox.get_active_text())

        history_combobox.connect('changed', history_combobox_changed)

        self.set_extra_widget(history_combobox)
        
        self.set_default_size(1000, 600)
        self.set_default_response(gtk.RESPONSE_OK)
        self.show()

    def run(self):
        if (gtk.Dialog.run(self) == gtk.RESPONSE_OK):
            self.okCallback(self)
    
class Dialog_FileSelection(gtk.FileSelection):
    
    def __init__(self, defaultDir, okCallback, title='Select file',
                 parent=None):
        """wrap some of the file selection boilerplate.  okCallback is
        a function that takes a Dialog_FileSelection instance as a
        single arg."""
        gtk.FileSelection.__init__(self, title)
        self.defaultDir = defaultDir
        self.okCallback = okCallback
        gtk.FileSelection.__init__(self, title=title)
        self.set_filename(defaultDir + os.sep)
        self.connect("destroy", lambda w: self.destroy())

        self.ok_button.connect("clicked", self.file_ok_sel)
        self.cancel_button.connect("clicked",
                                   lambda *args: self.destroy())
        if parent is not None:
            self.set_transient_for(parent)

        self.set_default_size(1000, 600)
        self.show()

    def get_default_dir(self):
        return self.defaultDir
    
    def file_ok_sel(self, w):
        filename = self.get_filename()
        (path, fname) = os.path.split(filename)
        self.defaultDir = path
        self.okCallback(self)


class Dialog_DirSelection(gtk.FileSelection):
    
    def __init__(self, defaultDir, okCallback, title='Select directory'):
        """
        A file selection dialog that forces the user to choose a
        directory.

        okCallback is a function that takes a Dialog_DirSelection
        instance as a single arg.

        """

        self.defaultDir = defaultDir
        self.okCallback = okCallback
        gtk.FileSelection.__init__(self, title=title)
        self.set_filename(defaultDir + os.sep)
        self.connect("destroy", lambda w: self.destroy())

        self.ok_button.connect("clicked", self.file_ok_sel)
        self.cancel_button.connect("clicked",
                                   lambda w: self.destroy())
        self.show()

    def get_default_dir(self):
        return self.defaultDir
    
    def file_ok_sel(self, w):
        thisDir = self.get_filename()
        if not os.path.isdir(thisDir):
            simple_msg(
                'You must select a directory\n%s is not a dir' %
                thisDir)
            return

        self.defaultDir = thisDir
        self.okCallback(self)



def ignore_or_act(msg, actionCallback, title='Ignore?', parent=None):

    
    d = gtk.Dialog(title, flags=gtk.DIALOG_MODAL)
    l = gtk.Label(msg)
    l.show()
    d.vbox.pack_start(l)

    if parent is not None:
        d.set_transient_for(parent)
        
    def destroy_callback(*args):
        d.destroy()

    b = gtk.Button('Ignore')
    b.connect('clicked', destroy_callback)
    b.show()
    d.vbox.pack_start(b)

    b = gtk.Button('Fix')
    b.connect('clicked', actionCallback)
    b.show()
    d.vbox.pack_start(b)

    d.show()



def not_implemented(parent=None, *args):
    "Popup a message for a widget that doesn't have a callback implemented yet"
    
    simple_msg('Not implemented yet; sorry!',
                  title='Error: Feature Unimplemented',
                  parent=parent)

def yes_or_no(msg, title, responseCallback, parent=None):
    """
    Pop up a yes or no dialog.  A typical response callback would look like

    def response(dialog, response):
        if response==gtk.RESPONSE_YES:
            print 'yes, yes!'
        elif response==gtk.RESPONSE_NO:
            print 'oh no!'
        else:
            print 'I am deeply confused'
        dialog.destroy()
    """

    dialog = gtk.MessageDialog(
        parent         = parent,
        flags          = gtk.DIALOG_DESTROY_WITH_PARENT,
        type           = gtk.MESSAGE_INFO,
        buttons        = gtk.BUTTONS_YES_NO,
        message_format = msg)

    dialog.set_title(title)
    dialog.connect('response', responseCallback)
    dialog.show()


def make_option_menu_from_strings(keys):
    
    menu = gtk.Menu()
    itemd = {}
    for k in keys:
        menuItem = gtk.MenuItem(k)
        menuItem.show()
        menu.append(menuItem)
        itemd[menuItem] = k
    return menu, itemd





class FileManager:
    if sys.platform=='win32':
        last = 'C:\\'
    else: 
        last = os.getcwd()

    def __init__(self, parent=None):
        self.parent = parent
        self.additionalWidget = None

        self.last_dirs = ['','','','','',
                          '','','','',''] # queue of 10 directories...

    def set_lastdirs(self, dirs):
        self.last_dirs = dirs
        
    def get_lastdir(self):
        #return self.last
        return self.last_dirs[0]

    def get_lastdirs(self):
        #return self.last
        return self.last_dirs

    def set_lastdir(self, s):
        if os.path.isdir(s):
            self.last = s
        elif os.path.isfile(s):
            basedir, fname = os.path.split(s)
            self.last = basedir

        else: pass #? 

        if (self.last not in self.last_dirs):
            self.last_dirs.pop()
            self.last_dirs.insert(0,self.last)
        

    def get_filename(self, fname=None, title='Select file name', parent=None):
        self.ok_fullpath = None
        
        def ok_callback(dlg):
            self.ok_fullpath =  dlg.get_filename()
            self.set_lastdir(self.ok_fullpath)
            dlg.destroy()

        dlg = Dialog_FileChooser(defaultDir=self.get_lastdir(), okCallback=ok_callback, title=title, parent=parent, previous_dirnames=self.get_lastdirs())
        dlg.run()
        dlg.destroy()
        return self.ok_fullpath


def get_num_range(minLabel='Min', maxLabel='Max',
                  title='Enter range', parent=None, as_times=False):
    'Get a min, max numeric range'
    dlg = gtk.Dialog(title)
    if parent is not None:
        dlg.set_transient_for(parent)
    vbox = dlg.vbox

    labelMin = gtk.Label(minLabel)
    labelMin.show()

    labelMax = gtk.Label(maxLabel)
    labelMax.show()

    entryMin = gtk.Entry()
    entryMin.show()
    entryMin.set_width_chars(10)
    
    entryMax = gtk.Entry()
    entryMax.show()
    entryMax.set_width_chars(10)
    entryMax.set_activates_default(True)
    
    table = gtk.Table(2,2)
    table.show()
    table.set_row_spacings(4)
    table.set_col_spacings(4)

    table.attach(labelMin, 0, 1, 0, 1)
    table.attach(labelMax, 1, 2, 0, 1)
    table.attach(entryMin, 0, 1, 1, 2)
    table.attach(entryMax, 1, 2, 1, 2)
    dlg.vbox.pack_start(table, True, True)

    dlg.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
    dlg.add_button(gtk.STOCK_OK, gtk.RESPONSE_OK)
    dlg.set_default_response(gtk.RESPONSE_OK)

    dlg.show()

    while 1:
        response = dlg.run()

        if response==gtk.RESPONSE_OK:
            if (as_times):
                # mcc XXX: what's the magic code word to unfurl an array into a tuple or untupled comma-separated variables?
                x= map(int, (entryMin.get_text()).split(':'))
                try:
                    minVal = datetime.time(x[0], x[1], x[2])
                except ValueError:
                    msg = exception_to_str('ValueError: minVal not in HH:MM:SS format')
                print "get_num_range (as_times=True): minVal = " , str(minVal)
            else:
                minVal = str2num_or_err(entryMin.get_text(), labelMin, parent)
            if minVal is None: continue
            if (as_times):
                x= map(int, (entryMax.get_text()).split(':'))
                try:
                    maxVal = datetime.time(x[0], x[1], x[2])
                except ValueError:
                    msg = exception_to_str('ValueError: maxVal not in HH:MM:SS format')
                print "get_num_range (as_times=True): maxVal = " , str(maxVal)
            else:
                maxVal = str2num_or_err(entryMax.get_text(), labelMax, parent)
            if maxVal is None: continue

            if minVal>maxVal:
                msg = '%s entry must be greater than %s entry' % \
                      (maxLabel, minLabel)
                error_msg(msg, parent, title='Invalid Entries')
                continue
            dlg.destroy()
            return minVal, maxVal
        else:
            dlg.destroy()
            return None
        
    

def select_name(names, title='Select Name'):
    'Use radio buttons to select from a list of names'
    dlg = gtk.Dialog(title)

    vbox = dlg.vbox


    buttond = {}
    buttons = []
    for name in names:
        if len(buttons):
            button = gtk.RadioButton(buttons[0])
        else:
            button = gtk.RadioButton(None)
        buttons.append(button)
        button.set_label(name)
        button.show()
        vbox.pack_start(button, True, True)
        buttond[button] = name
    hbox = gtk.HBox()
    hbox.show()
    vbox.pack_start(hbox, False, False)

    dlg.add_button('Cancel', gtk.RESPONSE_CANCEL)
    dlg.add_button('OK', gtk.RESPONSE_OK)
    dlg.show()

    response = dlg.run()

    if response == gtk.RESPONSE_OK:
        for button, name in buttond.items():
            if button.get_active():
                dlg.destroy()
                return name
    dlg.destroy()            
    return None


def make_option_menu( names, func=None ):
    """
    Make an option menu with list of names in names.  Return value is
    a optMenu, itemDict tuple, where optMenu is the option menu and
    itemDict is a dictionary mapping menu items to labels.  Eg

    optmenu, menud = make_option_menu( ('Bill', 'Ted', 'Fred') )

    ...set up dialog ...
    if response==gtk.RESPONSE_OK:
       item = optmenu.get_menu().get_active()
       print menud[item]  # this is the selected name


    if func is not None, call func with menuitem and label when
    selected; eg the signature of func is

            def func(menuitem, s):
                pass
    """
    #optmenu = gtk.OptionMenu()
    #optmenu.show()
    #menu = gtk.Menu()
    #menu.show()
    #d = {}
    #for label in names:
    #    item = gtk.MenuItem(label)
    #    menu.append(item)
    #    item.show()
    #    d[item] = label
    #    if func is not None:
    #        item.connect("activate", func, label)
    #optmenu.set_menu(menu)
    #return optmenu, d

    combobox = gtk.combo_box_new_text()
    for label in names:
        combobox.append_text(label)
    combobox.set_active(0)
    combobox.connect('changed', func)
    combobox.show_all()
    return combobox


def get_num_value(labelStr='Value', title='Enter value', parent=None,
                  default=None):
    'Get a numeric value'
    dlg = gtk.Dialog(title)
    if parent is not None:
        dlg.set_transient_for(parent)
    vbox = dlg.vbox

    label = gtk.Label(labelStr)
    label.show()


    entry = gtk.Entry()
    entry.show()
    entry.set_width_chars(10)
    entry.set_activates_default(True)
    if default is not None:
        entry.set_text('%1.4f' % default)

    hbox = gtk.HBox()
    hbox.show()
    hbox.pack_start(label, True, True)
    hbox.pack_start(entry, True, True)
    
    dlg.vbox.pack_start(hbox, True, True)

    dlg.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
    dlg.add_button(gtk.STOCK_OK, gtk.RESPONSE_OK)
    dlg.set_default_response(gtk.RESPONSE_OK)

    dlg.show()

    while 1:
        response = dlg.run()

        if response==gtk.RESPONSE_OK:
            val = str2num_or_err(entry.get_text(), label, parent)
            if val is None: continue
            dlg.destroy()
            return val
        else:
            dlg.destroy()
            return None
        

def get_two_nums(label1Str='Min', label2Str='Max',
                 title='Enter numbers', parent=None,
                 tooltip1=None, tooltip2=None):
    'Get two numeric values'
    dlg = gtk.Dialog(title)
    if parent is not None:
        dlg.set_transient_for(parent)
    vbox = dlg.vbox

    label1 = gtk.Label(label1Str)
    label1.show()

    label2 = gtk.Label(label2Str)
    label2.show()

    entry1 = gtk.Entry()
    entry1.show()
    entry1.set_width_chars(10)
    
    entry2 = gtk.Entry()
    entry2.show()
    entry2.set_width_chars(10)
    entry2.set_activates_default(True)
    
    table = gtk.Table(2,2)
    table.show()
    table.set_row_spacings(4)
    table.set_col_spacings(4)

    table.attach(label1, 0, 1, 0, 1)
    table.attach(label2, 1, 2, 0, 1)
    table.attach(entry1, 0, 1, 1, 2)
    table.attach(entry2, 1, 2, 1, 2)
    dlg.vbox.pack_start(table, True, True)

    dlg.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
    dlg.add_button(gtk.STOCK_OK, gtk.RESPONSE_OK)
    dlg.set_default_response(gtk.RESPONSE_OK)

    dlg.show()

    while 1:
        response = dlg.run()

        if response==gtk.RESPONSE_OK:
            val1 = str2num_or_err(entry1.get_text(), label1, parent)
            if val1 is None: continue
            val2 = str2num_or_err(entry2.get_text(), label2, parent)
            if val2 is None: continue

            dlg.destroy()
            return val1, val2
        else: return None
        


def add_button_icon_pixmap(button, pixmap, orientation='left'):
    button.realize()
    label = gtk.Label(button.get_children()[0].get())
    button.remove(button.get_children()[0])

    if orientation is None:
        box = gtk.HBox(spacing=0)
        box.pack_start(pixmap, False, False, 0)        

    if orientation in ('left', 'right'):
        box = gtk.HBox(spacing=5)
    elif orientation in ('top', 'bottom'):
        box = gtk.VBox(spacing=5)
    if orientation in ('left', 'top'):
        box.pack_start(pixmap, False, False, 0)
        box.pack_start(label, False, False, 0)
    elif orientation in ('right', 'bottom'):
        box.pack_start(label, False, False, 0)
        box.pack_start(pixmap, False, False, 0)

    hbox = gtk.HBox()
    if box is not None:
        hbox.pack_start(box, True, False, 0)
    hbox.show_all()
    button.add(hbox)

def add_button_icon(button, file, orientation='left'):
    button.realize()
    window = button.get_parent_window()
    xpm, mask = gtk.create_pixmap_from_xpm(window, None, file)
    pixmap = gtk.Image()
    pixmap.set_from_pixmap(xpm, mask)
    add_button_icon_pixmap(button, pixmap, orientation)


class OpenSaveSaveAsHBox(gtk.HBox):
    

    def __init__(self, fmanager, openhook=None, savehook=None, parent=None):
        """
        fmanager is a FileManager instance

        openhook is a function with signature ok = openhook(fh)
        savehook is a function with signature ok = savehook(fh)
        """
        gtk.HBox.__init__(self)
        self.set_spacing(3)
        self.fmanager = fmanager
        self.openhook = openhook
        self.savehook = savehook
        self.parentWin = parent
        self.filename = None

        label = gtk.Label('File')
        label.show()
        self.pack_start(label, False, False)

        button = gtk.Button(stock=gtk.STOCK_OPEN)
        button.show()
        button.connect('clicked', self.open)
        self.pack_start(button, True, True)

        button = gtk.Button(stock=gtk.STOCK_SAVE)
        button.show()
        button.connect('clicked', self.save)
        self.pack_start(button, True, True)


        button = gtk.Button(stock=gtk.STOCK_SAVE_AS)
        button.show()
        button.connect('clicked', self.save_as)
        self.pack_start(button, True, True)

        
    def open(self, button):
        filename = self.fmanager.get_filename(title='Select input file')
        if filename is not None:
            try: infile = file(filename, 'r')
            except IOError, msg:
                msg = exception_to_str('Could not open %s' % filename)
                error_msg(msg, parent=self.parentWin)
            else:
                self.filename = filename
                if self.openhook is not None:
                    ok = self.openhook(infile)
                    

    def save_as(self, button):
        filename = self.fmanager.get_filename(
            title='Select filename to save to')
        if filename is None: return
        self.save(button=None, filename=filename)


    def save(self, button, **kwargs):

        filename = kwargs.get('filename', self.filename)
        if filename is None: filename = self.fmanager.get_filename(
            title='Save to filename')
        if filename is None: return

        try:
            outfile = file(filename, 'w')
        except IOError, msg:
            msg = exception_to_str('Could not write markers to %s' % filename)
            error_msg(msg, parent=self.parentWin)
            return
        else:
            if self.savehook is not None:
                ok = self.savehook(outfile)
                if ok:
                    self.filename = filename
                    simple_msg('Saved markers to %s' % filename,
                               parent=self.parentWin)


class ButtonAltLabel(gtk.Button):
    """
    Use a gtk stock button with alternative label
    """
    def __init__(self, labelStr, stock):
        'label is a string and stock is a gtk.STOCK_* ID'
        gtk.Button.__init__(self, stock=stock)
        alignment = self.get_children()[0]
        hbox = alignment.get_children()[0]
        image, label = hbox.get_children()
        label.set_text(labelStr)
    

class SpreadSheet(gtk.Window):
    """
Example usage

data = (
    ('First', 'Last', 'Age', 'Weight'),
    ('John', 'Hunter', '33', '165'),
    ('Miriam', 'Sierig', '56', '187'),
    )
sheet = SpreadSheet(data)
sheet.show_all()
gtk.main()
    
    """
    def __init__(self, rows, fmanager, title='Spreadsheet'):
        gtk.Window.__init__(self)
        
        self.rows = rows
        self.fmanager = fmanager
        self.numRows = len(rows)
        self.numCols = len(rows[0])

        self.set_title(title)
        self.set_border_width(8)

        vbox = gtk.VBox(False, 8)
        self.add(vbox)

        # todo add toolbar here
        toolbar = self.make_toolbar()
        vbox.pack_start(toolbar, False, False)

        sw = gtk.ScrolledWindow()
        sw.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        sw.set_policy(gtk.POLICY_NEVER,
                      gtk.POLICY_AUTOMATIC)
        vbox.pack_start(sw, True, True)

        model = self.create_model()

        self.treeview = gtk.TreeView(model)
        self.treeview.set_rules_hint(True)
        sw.add(self.treeview)

        self.add_columns()

        self.set_default_size(600, 600)

        self.add_events(gdk.BUTTON_PRESS_MASK |
                       gdk.KEY_PRESS_MASK|
                       gdk.KEY_RELEASE_MASK)




    def add_columns(self):
        model = self.treeview.get_model()
        renderer = gtk.CellRendererText()

        for i in range(self.numCols):
            column = gtk.TreeViewColumn('%d'%i, gtk.CellRendererText(), text=i)
            self.treeview.append_column(column)

    def create_model(self):
        types = [gobject.TYPE_STRING]*self.numCols
        store = gtk.ListStore(*types)

        for row in self.rows:
            iter = store.append()
            pairs = []
            for i, entry in enumerate(row): pairs.extend((i, entry))
            store.set(iter, *pairs)
        return store


    def make_toolbar(self):

        toolbar  = gtk.Toolbar()
        iconSize = gtk.ICON_SIZE_SMALL_TOOLBAR
        toolbar.set_border_width(5)
        toolbar.set_style(gtk.TOOLBAR_ICONS)
        toolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)


        iconw = gtk.Image() # icon widget
        iconw.set_from_stock(gtk.STOCK_SAVE, iconSize)
        button = toolbar.append_item(
            'Save',
            'Save as CSV',
            'Private',
            iconw,
            self.save)
        return toolbar
    
    def save(self, *args):
        filename = self.fmanager.get_filename()
        if filename is None: return
        lines = []
        basename, ext = os.path.splitext(filename)
        if ext.lower() != '.csv':
            filename += '.csv'
        # todo: add csv extension
        fh = file(filename, 'w', False)
        for row in self.rows:
            print >>fh, ','.join(row)
        fh.close()







        
class MyToolbar(gtk.Toolbar):
    """
    Compatability toolbar for pygtk2.2 and 2.4 (thanks to Steve
    Chaplin in the mpl gtk backend) for basic code

    Derived must provide toolitems, eg
    toolitems = [ 
      (button_str, tooltip_str, STOCK, callback_str),
      (button_str, tooltip_str, STOCK, callback_str),
      ]

    Examples:
        ('CT Info', 'Load new 3d image', gtk.STOCK_NEW, 'load_image'),
        ('Markers', 'Load markers from file', gtk.STOCK_OPEN, 'load_from'),
        (None, None, None, None),

    None will add a separator.  If the callback is 'some_callback',
    derived must define

    def some_callback(self, button):
        blah


   
    """
    iconSize = gtk.ICON_SIZE_SMALL_TOOLBAR
    def __init__(self):
        gtk.Toolbar.__init__(self)
        self.set_border_width(5)
        self.set_style(gtk.TOOLBAR_BOTH)

        if gtk.pygtk_version >= (2,4,0):
            self._init_toolbar2_4()
        else:
            self._init_toolbar2_2()


    def _init_toolbar2_2(self):

        for text, tooltip_text, stock, callback in self.toolitems:
            if text == None:
                 self.append_space()
                 continue
            
            image = gtk.Image()
            image.set_from_stock(stock, self.iconSize)
            w = self.append_item(text,
                                 tooltip_text,
                                 'Private',
                                 image,
                                 getattr(self, callback)
                                 )

    def _init_toolbar2_4(self):

        self.tooltips = gtk.Tooltips()

        for text, tooltip_text, stock, callback in self.toolitems:
            if text == None:
                self.insert( gtk.SeparatorToolItem(), -1 )
                continue
            image = gtk.Image()
            image.set_from_stock(stock, self.iconSize)
            tbutton = gtk.ToolButton(image, text)
            self.insert(tbutton, -1)
            tbutton.connect('clicked', getattr(self, callback))
            tbutton.set_tooltip(self.tooltips, tooltip_text, 'Private')



        self.show_all()
