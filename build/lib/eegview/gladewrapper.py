import gtk.glade
import os, re
from borgs import Shared

from pbrainlib.gtkutils import donothing_callback

# add an extra reference to dialogs to workaround gc bug
# http://bugzilla.gnome.org/show_bug.cgi?id=92955
storeref = {}

class PrefixWrapper:
    """

    Base class for wrapping glade widgets where all functions and
    entries have a namespace prefix.  Provides __getitem__ and handler
    dict so handler class doesn't have to use the prefix internally.
    All public callable methods in the derived class beginning with
    'on_' will be mapped to the signal autoconnect.

    For example, a class implementing the dialog named 'dialogHimom'
    where all the widgets and signal handlers have the prefix
    'dlgHi_', which defined a widget dlgHi_entryName and a handler
    dlgHi_on_buttonOK_clicked could access the widget with

      self['entryName'].get_text()

    and should define the handler

      def on_buttonOK_clicked(self, event):
          pass  #do something

    
    Derived classes must define at the class level 'dialog' and 'prefix', eg

        class Dialog_HiMom(PrefixWrapper):

            prefix = 'dlgHi_'
            widgetName = 'dialogHimom'

            def __init__(self):
                pass #do something

            def on_buttonOK_clicked(self, event):
                pass  #do something

    Derived classes must override get_params and set_params.  See the
    doc string for those functions for details.

    The base class will define self.widget so the derived class can
    conveniently refer to itself.
    
    Note, you don't need to use the prefix when creating the dialog in
    glade.  I create the dialog using simple names, like entryText and
    checkbuttonRemoveMean and define signal handlers using the glade
    defaults, ie, on_checkbuttonRemoveMean_toggled.  Then I exit glade
    and edit the *.glade with a text editor.  After the line <widget
    ...}, replace all instances of 

       id="
         with
       id="prefix

    and all instances of

      handler="
        with
      handler="prefix

    Save the dialog.  You can restart glade or implement you class
    handler.  See the file main.py for a sample dialog.

    If a someWidget isn's found in the glade file to match
    on_someWidget_signal, the autoconnector will look for an attribute
    self.someWdiget

    """

    rgx = re.compile('on_([^_]+)_(\w+)')
    def __init__(self):

        # Verify that the derived classes have defined their dialog
        # name and prefix        
        try: self.prefix, self.widgetName
        except AttributeError:
            msg = 'derived classes must define attributes prefix'+\
                  ' and widgetName'
            raise NotImplementedError, msg
        self.widget = Shared.widgets.get_widget(self.widgetName)
        self.initParams = self.get_params()
        storeref[self.widgetName] = self

    def autoconnect(self):

        self.connectionIds = []
        handlers = {}
        for name in dir(self):
            if not callable(getattr(self, name)): continue
            m = self.rgx.match(name)
            if m is None: continue
            wName, signal = m.group(1), m.group(2)
            #if name=='on_drawingArea_expose_event': continue

            thisWidget = Shared.widgets.get_widget(self.prefix+wName)
            if thisWidget is None:
                try: thisWidget = getattr(self, wName)
                except AttributeError:
                    print 'Could not find widget %s for %s' % \
                          (self.prefix+wName, self.widgetName)
                    continue
                

            try:
                id = thisWidget.connect(signal, getattr(self, name))
            except TypeError, msg:
                print 'Caught a TypeError msg %s\n\nTrying to connect %s with %s' %\
                      (msg, signal, name)
                
            #if name is'on_drawingArea_button_press_event':
            #    print 'Connecting %s to %s with id %d' % (wName, name, id)
            self.connectionIds.append( (thisWidget, id) )

    def disconnect(self):
        for w, id in self.connectionIds:
            w.disconnect(id)


    def get_params(self):
        """
        Return a dictionary of strings to values.  The strings should
        *not* use a widget naming convention, because the users of
        this class does not need to know about widgets.  So if you
        have a check button called buttonRemoveMean, return a
        dictionary that maps 'RemoveMean' to the button state, eg

        m = {'RemoveMean' : self['buttonRemoveMean'].get_active()}

        """
        
        return {}

    def set_params(self, m):
        """
        Set the widget values using the values in the dictionary.  Eg,
        continuing with the example from get_params, do

        self['buttonRemoveMean'].set_active(m['RemoveMean'])

        """

        pass

    def __getitem__(self, key):
        """Allow the derived classes to do

        self['someWidget']

        instead of

        Shared.widgets.get_widget('prefixsomeWidget')

        """
        return Shared.widgets.get_widget(self.prefix + key)


    def hide_widget(self):
        self.widget.hide()
        self.disconnect()

    def show_widget(self):
        self.widget.show()
        self.autoconnect()

    def get_widget(self):
        return self.widget

    def on_buttonCancel_clicked(self, event):             
        self.set_params(self.initParams)
        self.hide_widget()

    def i_am_prepared_to_die(self):
        """
        free the stored ref to self to allow deletion.  call me when you are
        really ready to be garbage collected by an errant garbage collector"""
        try: del storedref[self.widgetName]
        except KeyError: pass
