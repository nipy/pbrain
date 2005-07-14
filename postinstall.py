"""
See for example
http://www.geocrawler.com/archives/3/14884/2002/10/0/9979630/


"""

import sys, os
import distutils.sysconfig

if sys.platform[:3] != 'win':
    sys.exit()

startMenuDir = get_special_folder_path('CSIDL_STARTMENU')

desktopDir = get_special_folder_path('CSIDL_COMMON_DESKTOPDIRECTORY')


target = os.path.join(
    distutils.sysconfig.PREFIX,
    'lib', 'site-packages', 'eegview', 'eegview.py')
filename = os.path.join(desktopDir, 'eegview.py.lnk')

create_shortcut(target, 'Shortcut to eegview', filename)

print 'Created shortcut from %s to %s' % (filename,  target)

target = os.path.join(
    distutils.sysconfig.PREFIX,
    'lib', 'site-packages', 'loc3djr', 'loc3djr.py')
filename = os.path.join(desktopDir, 'loc3djr.py.lnk')

create_shortcut(target, 'Shortcut to eegview', filename)

print 'Created shortcut from %s to %s' % (filename,  target)
