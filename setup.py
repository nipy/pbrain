"""
 python2.3 setup.py bdist_wininst --install-script=postinstall.py

"""
from distutils.core import setup
import sys,os
import glob

data = []
data.extend(glob.glob('gui/*.png'))
data.extend(glob.glob('gui/*.xpm'))
data.extend(glob.glob('gui/*.glade'))
data.extend(glob.glob('gui/*.gladep'))

setup(name="pbrain",
      version= '0.8',
      description = "Integrated EEG, CT and MRI analysis",
      author = "John D. Hunter & Eli Albert",
      author_email="ealbert@bsd.uchicago.edu",
      long_description = """
      These packages to allow you to analyize and visualize EEG data
      either in a traditional chart based screen or spatially using
      electrode locations
      """,
      packages=['eegview', 'loc3djr', 'pbrainlib'],
      data_files=[('share/pbrain', data)],
      platforms='any',
      scripts=['postinstall.py'],
      )
