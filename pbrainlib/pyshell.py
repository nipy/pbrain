#
#       Py_Shell.py : inserts the python prompt in a gtk interface
#

import sys, code, os
import __builtin__


import gtk, gobject, pango

PS1=">>> "
PS2="... "
TAB_WIDTH=4

BANNER="Python "+sys.version+"\n"




class Completer:
  """
  Taken from rlcompleter, with readline references stripped, and a local dictionary to use.
  """
  def __init__(self,locals):
    self.locals = locals

  def complete(self, text, state):
    """Return the next possible completion for 'text'.
    This is called successively with state == 0, 1, 2, ... until it
    returns None.  The completion should begin with 'text'.

    """
    if state == 0:
      if "." in text:
        self.matches = self.attr_matches(text)
      else:
        self.matches = self.global_matches(text)
    try:
      return self.matches[state]
    except IndexError:
      return None

  def global_matches(self, text):
    """Compute matches when text is a simple name.

    Return a list of all keywords, built-in functions and names
    currently defines in __main__ that match.

    """
    import keyword
    matches = []
    n = len(text)
    for list in [keyword.kwlist, __builtin__.__dict__.keys(), self.locals.keys()]:
      for word in list:
        if word[:n] == text and word != "__builtins__":
          matches.append(word)
    return matches

  def attr_matches(self, text):
    """Compute matches when text contains a dot.

    Assuming the text is of the form NAME.NAME....[NAME], and is
    evaluatable in the globals of __main__, it will be evaluated
    and its attributes (as revealed by dir()) are used as possible
    completions.  (For class instances, class members are are also
    considered.)

    WARNING: this can still invoke arbitrary C code, if an object
    with a __getattr__ hook is evaluated.

    """
    import re
    m = re.match(r"(\w+(\.\w+)*)\.(\w*)", text)
    if not m:
      return
    expr, attr = m.group(1, 3)
    object = eval(expr, self.locals, self.locals)
    words = dir(object)
    if hasattr(object,'__class__'):
      words.append('__class__')
      words = words + get_class_members(object.__class__)
    matches = []
    n = len(attr)
    for word in words:
      if word[:n] == attr and word != "__builtins__":
        matches.append("%s.%s" % (expr, word))
    return matches

def get_class_members(klass):
  ret = dir(klass)
  if hasattr(klass,'__bases__'):
     for base in klass.__bases__:
       ret = ret + get_class_members(base)
  return ret







class Dummy_File:

    def __init__(self, buffer, tag):
        """Implements a file-like object for redirect the stream to the buffer"""
        
        self.buffer = buffer
        self.tag = tag

    def write(self, text):
        """Write text into the buffer and apply self.tag"""
        iter=self.buffer.get_end_iter()
        self.buffer.insert_with_tags(iter,text,self.tag)

    def writelines(self, l):
        map(self.write, l)

    def flush(self):
        pass

    def isatty(self):
        return 1



class PopUp:

    def __init__(self, text_view, list, position):
        self.text_view=text_view
        
        #avoid duplicate items in list
        tmp={}
        n_chars=0
        for item in list:
            dim=len(item)
            if dim>n_chars:
                n_chars=dim
            tmp[item]=None 
        list=tmp.keys()
        list.sort()
        
        self.list=list
        self.position=position
        self.popup=gtk.Window(gtk.WINDOW_POPUP)
        frame=gtk.Frame()
        sw=gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        model=gtk.ListStore(gobject.TYPE_STRING)
        for item in self.list:
            iter=model.append()
            model.set(iter, 0, item)
        self.list_view=gtk.TreeView(model)
        self.list_view.connect("row-activated", self.hide)
        self.list_view.set_property("headers-visible", gtk.FALSE)
        selection=self.list_view.get_selection()
        selection.connect("changed",self.select_row)
        selection.select_path((0,))
        renderer=gtk.CellRendererText()
        column=gtk.TreeViewColumn("",renderer,text=0)
        self.list_view.append_column(column)
        sw.add(self.list_view)
        frame.add(sw)
        self.popup.add(frame)
        
        #set the width of the popup according with the length of the strings
        contest=self.popup.get_pango_context()
        desc=contest.get_font_description()
        lang=contest.get_language()
        metrics= contest.get_metrics(desc, lang)
        width= pango.PIXELS(metrics.get_approximate_char_width()* n_chars)
        if width>80:
            self.popup.set_size_request(width,90)
        else:
            self.popup.set_size_request(80,90)
        self.show_popup()

 
    def hide(self, *arg):
        self.popup.hide()
         
    def show_popup(self):
        buffer=self.text_view.get_buffer()
        iter=buffer.get_iter_at_mark(buffer.get_insert())
        
        rectangle=self.text_view.get_iter_location(iter)
        absX, absY=self.text_view.buffer_to_window_coords(gtk.TEXT_WINDOW_TEXT, 
                                   rectangle.x+rectangle.width+20 ,
                                   rectangle.y+rectangle.height+50)
        parent=self.text_view.get_parent()
        self.popup.move(self.position[0]+absX, self.position[1]+absY)
        self.popup.show_all()

             

    def prev(self):
        sel=self.list_view.get_selection()
        model, iter=sel.get_selected()
        newIter=model.get_path(iter)
        if newIter!=None and newIter[0]>0:
            path=(newIter[0]-1,)
            self.list_view.set_cursor(path)
            

    def next(self):
        sel=self.list_view.get_selection()
        model, iter=sel.get_selected()
        newIter=model.iter_next(iter)
        if newIter!=None:
            path=model.get_path(newIter)
            self.list_view.set_cursor(path)


    def sel_confirmed(self):
        sel=self.list_view.get_selection()
        self.select_row(sel)
        self.hide()

                                                                                                                                                
    def select_row(self, selection):
        model, iter= selection.get_selected()
        name=model.get_value(iter,0)
        buffer=self.text_view.get_buffer()
        end=buffer.get_iter_at_mark(buffer.get_insert())
        start=end.copy()
        start.backward_char()
        while start.get_char() not in " ,()[]":
            start.backward_char()
        start.forward_char()
        buffer.delete(start,end)
        iter=buffer.get_iter_at_mark(buffer.get_insert())
        buffer.insert(iter,name)


class Shell_Gui:

    def __init__(self,with_window=1,banner=BANNER, label_text="Interactive Python Shell", namespace=None):
        
        
        self.banner=banner
        box=gtk.HBox()
        box.set_homogeneous(gtk.FALSE)
        box.set_border_width(4)
        box.set_spacing(4)
        sw=gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC,gtk.POLICY_AUTOMATIC)
        t_table=gtk.TextTagTable()
        # creates three tags
        tag_err=gtk.TextTag("error")
        tag_err.set_property("foreground","red")
        tag_err.set_property("font","monospace 10")
        t_table.add(tag_err)
        
        tag_out=gtk.TextTag("output")
        tag_out.set_property("foreground","blue")
        tag_out.set_property("font","monospace 10")
        t_table.add(tag_out)
        
        tag_in=gtk.TextTag("input")
        tag_in.set_property("foreground","black")
        tag_in.set_property("font","monospace 10")
        t_table.add(tag_in)

        tag_no_edit=gtk.TextTag("no_edit")
        tag_no_edit.set_property("editable",gtk.FALSE)
        t_table.add(tag_no_edit)
        
        self.buffer=gtk.TextBuffer(t_table)
        #add the banner
        self.buffer.set_text(self.banner+PS1)
        start,end=self.buffer.get_bounds()
        self.buffer.apply_tag_by_name("output",start,end)
        self.buffer.apply_tag_by_name("no_edit",start,end)

        self.view=gtk.TextView()
        self.view.set_buffer(self.buffer)
        self.view.connect("key_press_event", self.key_press)
        self.view.connect("drag_data_received",self.drag_data_received)
        self.view.set_wrap_mode(gtk.WRAP_CHAR)
        sw.add(self.view)
        box.pack_start(sw)

        #creates  two dummy files
        self.dummy_out=Dummy_File(self.buffer,tag_out)
        self.dummy_err=Dummy_File(self.buffer,tag_err)
        
        #creates the console
        if namespace is None: namespace = {}
        self.core=code.InteractiveConsole(namespace)

        #autocompletation capabilities
        self.completer = Completer(self.core.locals)
        self.popup=None
        
        #creates history capabilities
        self.history=[" "]
        self.history_pos=0

        #add buttons
        b_box=gtk.Toolbar()
        b_box.set_orientation(gtk.ORIENTATION_VERTICAL)
        b_box.set_style(gtk.TOOLBAR_ICONS)
        b_box.insert_stock(gtk.STOCK_CLEAR,"Clear the output", None, self.clear_text, None,-1)
        b_box.insert_stock(gtk.STOCK_SAVE,"Save the output", None, self.save_text, None,-1)
        b_box.insert_stock(gtk.STOCK_PREFERENCES,"Preferences", None, None, None,-1)
        if with_window:
            b_box.append_space()
            b_box.insert_stock(gtk.STOCK_QUIT,"Close Shell", None, self.quit, None,-1)
        
        
        box.pack_start(b_box,expand=gtk.FALSE)
        frame=gtk.Frame(label_text)
        frame.show_all()
        frame.add(box)
        
        
        if with_window:
            self.gui=gtk.Window()
            self.gui.add(frame)
            self.gui.connect("delete-event",self.quit)
            self.gui.set_default_size(520,200)
            self.gui.show_all()
        else:
            self.gui=frame
        




    def key_press(self, view, event):
        if self.popup!=None:
            
            if event.keyval ==gtk.gdk.keyval_from_name("Up"):
                self.popup.prev()
                return gtk.TRUE 
            elif event.keyval ==gtk.gdk.keyval_from_name("Down"):
                self.popup.next()
                return gtk.TRUE 
            elif event.keyval ==gtk.gdk.keyval_from_name("Return"):
                self.popup.sel_confirmed()
                self.popup=None
                return gtk.TRUE 
            else:
                self.popup.hide()
                self.popup=None
        else:
            if event.keyval ==gtk.gdk.keyval_from_name("Up"):
                
                if self.history_pos>0:
                    # remove text into the line...
                    end=self.buffer.get_end_iter()
                    start=self.buffer.get_iter_at_line(end.get_line())
                    start.forward_chars(4)
                    self.buffer.delete(start,end)
                    #inset the new text
                    pos=self.buffer.get_end_iter()
                    self.buffer.insert(pos, self.history[self.history_pos])
                    self.history_pos-=1
                else:
                    gtk.gdk.beep()
                self.view.emit_stop_by_name("key-press-event")
                return gtk.TRUE
                
            elif event.keyval ==gtk.gdk.keyval_from_name("Down"):
    
                if self.history_pos<len(self.history)-1:
                    # remove text into the line...
                    end=self.buffer.get_end_iter()
                    start=self.buffer.get_iter_at_line(end.get_line())
                    start.forward_chars(4)
                    self.buffer.delete(start,end)
                    #inset the new text
                    pos=self.buffer.get_end_iter()
                    self.history_pos+=1
                    self.buffer.insert(pos, self.history[self.history_pos])
                    
                else:
                    gtk.gdk.beep()
                self.view.emit_stop_by_name("key-press-event")
                return gtk.TRUE
            
            elif event.keyval ==gtk.gdk.keyval_from_name("Tab"):
                iter=self.buffer.get_iter_at_mark(self.buffer.get_insert())
                self.buffer.insert(iter,TAB_WIDTH*" ")
                return gtk.TRUE
            
            elif event.keyval ==gtk.gdk.keyval_from_name("Return"):
                command=self.get_line()
                self.exec_code(command)
                start,end=self.buffer.get_bounds()
                self.buffer.apply_tag_by_name("no_edit",start,end)
                self.buffer.place_cursor(end)
                return gtk.TRUE
                
            elif event.keyval ==gtk.gdk.keyval_from_name("space") and event.state & gtk.gdk.CONTROL_MASK:
                self.complete_text()
                return gtk.TRUE
            
    

    def clear_text(self,*widget):
        dlg=gtk.Dialog("Clear")
        dlg.add_button("Clear",1)
        dlg.add_button("Reset",2)
        dlg.add_button(gtk.STOCK_CLOSE,gtk.RESPONSE_CLOSE)
        dlg.set_default_size(250,150)
        hbox=gtk.HBox()
        #add an image
        img=gtk.Image()
        img.set_from_stock(gtk.STOCK_CLEAR, gtk.ICON_SIZE_DIALOG)
        hbox.pack_start(img)
        
        #add text
        text="You have two options:\n"
        text+="   -clear only the output window\n"
        text+="   -reset the shell\n"
        text+="\n What do you want to do?"
        label=gtk.Label(text)
        hbox.pack_start(label)
        
        hbox.show_all()
        dlg.vbox.pack_start(hbox)
        
        ans=dlg.run()
        dlg.hide()
        if ans==1:
            self.buffer.set_text(self.banner+PS1)
            start,end=self.buffer.get_bounds()
            self.buffer.apply_tag_by_name("output",start,end)
            self.buffer.apply_tag_by_name("no_edit",start,end)
        elif ans==2:
            self.buffer.set_text(self.banner+PS1)
            start,end=self.buffer.get_bounds()
            self.buffer.apply_tag_by_name("output",start,end)
            self.buffer.apply_tag_by_name("no_edit",start,end)
            #creates the console
            self.core=code.InteractiveConsole()
            #reset history
            self.history=[" "]
            self.history_pos=0
        self.view.grab_focus()


    def save_text(self, *widget):
        dlg=gtk.Dialog("Save to file")
        dlg.add_button("Commands",1)
        dlg.add_button("All",2)
        dlg.add_button(gtk.STOCK_CLOSE,gtk.RESPONSE_CLOSE)
        dlg.set_default_size(250,150)
        hbox=gtk.HBox()
        #add an image
        img=gtk.Image()
        img.set_from_stock(gtk.STOCK_SAVE, gtk.ICON_SIZE_DIALOG)
        hbox.pack_start(img)
        
        #add text
        text="You have two options:\n"
        text+="   -save only commands\n"
        text+="   -save all\n"
        text+="\n What do you want to save?"
        label=gtk.Label(text)
        hbox.pack_start(label)
        
        hbox.show_all()
        dlg.vbox.pack_start(hbox)
        
        ans=dlg.run()
        dlg.hide()
        if ans==1 :
            def ok_save(button, data=None):
                win =button.get_toplevel()
                win.hide()
                name=win.get_filename()
                if os.path.isfile(name):
                    box=gtk.MessageDialog(dlg,
                                      gtk.DIALOG_DESTROY_WITH_PARENT,
                                      gtk.MESSAGE_QUESTION,gtk.BUTTONS_YES_NO,
                                    name+" already exists; do you want to overwrite it?"
                                    )
                    ans=box.run()
                    box.hide()
                    if ans==gtk.RESPONSE_NO:
                        return
                try:
                    file=open(name,'w')
                    for i in self.history:
                        file.write(i)
                        file.write("\n")
                    file.close()
                    
                        
                except Exception, x:
                    box=gtk.MessageDialog(dlg,
                                      gtk.DIALOG_DESTROY_WITH_PARENT,
                                      gtk.MESSAGE_ERROR,gtk.BUTTONS_CLOSE,
                                    "Unable to write \n"+
                                    name+"\n on disk \n\n%s"%(x)
                                    )
                    box.run()
                    box.hide()
                    
            def cancel_button(button):
                win.get_toplevel()
                win.hide()
                
            win=gtk.FileSelection("Save Commands...")
            win.ok_button.connect_object("clicked", ok_save,win.ok_button)
            win.cancel_button.connect_object("clicked", cancel_button,win.cancel_button)
            win.show()
        elif ans==2:
            def ok_save(button, data=None):
                win =button.get_toplevel()
                win.hide()
                name=win.get_filename()
                if os.path.isfile(name):
                    box=gtk.MessageDialog(dlg,
                                      gtk.DIALOG_DESTROY_WITH_PARENT,
                                      gtk.MESSAGE_QUESTION,gtk.BUTTONS_YES_NO,
                                    name+" already exists; do you want to overwrite it?"
                                    )
                    ans=box.run()
                    box.hide()
                    if ans==gtk.RESPONSE_NO:
                        return
                try:
                    start,end=self.buffer.get_bounds()
                    text=self.buffer.get_text(start,end,0)
                    file=open(name,'w')
                    file.write(text)
                    file.close()
                    
                except Exception, x:
                    box=gtk.MessageDialog(dlg,
                                      gtk.DIALOG_DESTROY_WITH_PARENT,
                                      gtk.MESSAGE_ERROR,gtk.BUTTONS_CLOSE,
                                    "Unable to write \n"+
                                    name+"\n on disk \n\n%s"%(x)
                                    )
                    box.run()
                    box.hide()
                    
            def cancel_button(button):
                win.get_toplevel()
                win.hide()
                
            win=gtk.FileSelection("Save Log...")
            win.ok_button.connect_object("clicked", ok_save,win.ok_button)
            win.cancel_button.connect_object("clicked", cancel_button,win.cancel_button)
            win.show()
        dlg.destroy()
        self.view.grab_focus()
        

          
    def get_line(self):
        iter=self.buffer.get_iter_at_mark(self.buffer.get_insert())
        line=iter.get_line()
        start=self.buffer.get_iter_at_line(line)
        end=start.copy()
        end.forward_line()
        command=self.buffer.get_text(start,end,0)
        if  (command[:4]==PS1 or command[:4]==PS2):
            command=command[4:]
        return command
        
        
    def complete_text(self):
        end=self.buffer.get_iter_at_mark(self.buffer.get_insert())
        start=end.copy()
        start.backward_char()
        while start.get_char() not in " ,()[]=":
            start.backward_char()
        start.forward_char()
        token=self.buffer.get_text(start,end,0).strip() 
        completions = []
        try:
            p=self.completer.complete(token,len(completions))
            while p != None:
              completions.append(p)
              p=self.completer.complete(token, len(completions))
        except:
            return 
        if len(completions)==1:
            self.buffer.delete(start,end)
            iter=self.buffer.get_iter_at_mark(self.buffer.get_insert())
            self.buffer.insert(iter,completions[0])
        elif len(completions)>1:
            #show a popup 
            if isinstance(self.gui, gtk.Frame):
                rect=self.gui.get_allocation()
                app=self.gui.window.get_root_origin()
                position=(app[0]+rect.x,app[1]+rect.y)
            else:    
                position=self.gui.window.get_root_origin()

            self.popup=PopUp(self.view, completions, position) 

         
    def replace_line(self, text):
        iter=self.buffer.get_iter_at_mark(self.buffer.get_insert())
        line=iter.get_line()
        start=self.buffer.get_iter_at_line(line)
        start.forward_chars(4)
        end=start.copy()
        end.forward_line()
        self.buffer.delete(start,end)
        iter=self.buffer.get_iter_at_mark(self.buffer.get_insert())
        self.buffer.insert(iter, text)
        
        
                          
    def sdt2files(self):
        """switch stdin stdout stderr to my dummy files"""
        self.std_out_saved=sys.stdout
        self.std_err_saved=sys.stderr
        
        sys.stdout=self.dummy_out
        sys.stderr=self.dummy_err
        
        
        
        
        

    def files2sdt(self):
        """switch my dummy files to stdin stdout stderr  """
        sys.stdout=self.std_out_saved
        sys.stderr=self.std_err_saved
        



    def drag_data_received(self, source, drag_context, n1, n2, selection_data, long1, long2):
        print selection_data.data
        
        
    def exec_code(self, text):
        """Execute text into the console and display the output into TextView"""
        
        #update history
        self.history.append(text)
        self.history_pos=len(self.history)-1
        
        self.sdt2files()
        sys.stdout.write("\n")
        action=self.core.push(text)
        if action==0:
            sys.stdout.write(PS1)
        elif action==1:
            sys.stdout.write(PS2)
        self.files2sdt()
        self.view.scroll_mark_onscreen(self.buffer.get_insert())



    def quit(self,*args):
        if __name__=='__main__':
            gtk.main_quit()
        else:
            if self.popup!=None:
                self.popup.hide()
            self.gui.hide()







