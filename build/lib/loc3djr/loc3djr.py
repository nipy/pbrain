import pygtk
pygtk.require('2.0')
import gtk

from plane_widgets import PlaneWidgetsWithObservers

window = gtk.Window()
window.set_title("Loc3D Jr")
window.connect("destroy", gtk.mainquit)
window.connect("delete_event", gtk.mainquit)
window.set_border_width(10)
window.set_size_request(640, 480)  #w,h
window.show()

pwo = PlaneWidgetsWithObservers(window)
pwo.show()
window.add(pwo)

def idle(*args):
    pwo.mainToolbar.load_image()
    return gtk.FALSE

gtk.idle_add(idle)

gtk.mainloop()
