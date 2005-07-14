import os

class Shared(object):
    #lastSel = '/home/jdhunter/python/projects/loc3djr/data/ct/'
    lastSel = '/home/jdhunter/seizure/data/ThompsonK/CT/raw/'
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
