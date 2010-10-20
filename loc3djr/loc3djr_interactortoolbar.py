import gtk
from events import EventHandler

class InteractorToolbar(gtk.Toolbar):
    """
    CLASS: InteractorToolbar
    DESCR: 
    """
    def add_toolbutton1(self, icon_name, text, tip_text, tip_private, clicked_function, clicked_param1=None):
        iconSize = gtk.ICON_SIZE_SMALL_TOOLBAR
        iconw = gtk.Image()
        iconw.set_from_stock(icon_name, iconSize)
            
        toolitem = gtk.ToolButton(iconw, text)
        #toolitem = gtk.ToolButton(iconw)
        toolitem.set_icon_widget(iconw)
        toolitem.show_all()
        toolitem.set_tooltip(self.tooltips1, tip_text, tip_private)
        toolitem.connect("clicked", clicked_function, clicked_param1)
        #toolitem.connect("scroll_event", clicked_function)
        self.insert(toolitem, -1)

    def __init__(self):
        gtk.Toolbar.__init__(self)
        
        self.tooltips1 = gtk.Tooltips()

        iconSize = gtk.ICON_SIZE_SMALL_TOOLBAR
        
        #self.set_border_width(5)
        self.set_style(gtk.TOOLBAR_BOTH)
        #self.set_style(gtk.TOOLBAR_ICONS)
        
        #self.set_orientation(gtk.ORIENTATION_VERTICAL)
        self.add_toolbutton1(gtk.STOCK_REFRESH, 'Enable interact', 'Enable mouse rotate pan/zoom', 'Private', self.notify, 'mouse1 interact')
        self.add_toolbutton1(gtk.STOCK_REFRESH, 'Reset Camera', 'If this button used to do something else, right now it resets the camera', 'Private', self.notify, 'vtk interact')
        self.add_toolbutton1(gtk.STOCK_BOLD, 'Label markers', 'Label clicked markers', 'Private', self.notify, 'mouse1 label')
        self.add_toolbutton1(gtk.STOCK_APPLY, 'Select markers', 'Select clicked markers', 'Private', self.notify, 'mouse1 select')
        self.add_toolbutton1(gtk.STOCK_CLEAR, 'Set color', 'Set marker color', 'Private', self.notify, 'mouse1 color')
        self.add_toolbutton1(gtk.STOCK_GO_FORWARD, 'Move', 'Move markers', 'Private', self.notify, 'mouse1 move')
        self.add_toolbutton1(gtk.STOCK_DELETE, 'Delete', 'Delete clicked markers', 'Private', self.notify, 'mouse1 delete')        

        self.show_all()

    def notify(button, event, data):
        print "notify ", button, event, data
        EventHandler().notify(data)

