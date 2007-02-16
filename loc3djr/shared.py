import os

class Shared(object):
    lastSel = ''
    #lastSel = os.getcwd() + os.sep
    def set_file_selection(self, name):
        """
        Set the filename or dir of the most recent file selected
        """
        self.lastSel = name

    def get_last_dir(self):
        """
        Return the dir name of the most recent file selected
        """

        return os.path.dirname(self.lastSel) + os.sep

        

shared = Shared()
