import gobject, gtk

from plane_widgets import PlaneWidgetsWithObservers

window = gtk.Window()
window.set_title("Loc3D Jr")
window.connect("destroy", gtk.main_quit)
window.connect("delete_event", gtk.main_quit)
window.set_border_width(10)
window.set_size_request(640, 480)  #w,h
window.show()

pwo = PlaneWidgetsWithObservers(window)
pwo.show()
window.add(pwo)

def idle(*args):
    pwo.mainToolbar.load_image()
    return False

gobject.idle_add(idle)

gtk.main()
