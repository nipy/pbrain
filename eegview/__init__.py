import os, sys


import CodeRegistry
from Code import Code

CodeRegistry.register_code(
    'race',
    Code( [ ('Unknown' , 99),
            ('White' , 0),
            ('Black' , 1),
            ('Asian' , 2),
            ('Hispanic' , 3),
            ('Other' ,  98),
            
            ] ) )

CodeRegistry.register_code(
    'sex',
    Code( [ ('M', 0),
            ('F', 1),
            ('?', 99)
            ] ) )

CodeRegistry.register_code(
    'consent',
    Code( [ ('No', 0),
            ('Yes', 1),
            ('?', 99)
            ] ) )

CodeRegistry.register_code(
    'Employment',
    Code( [ ('Unknown' , 99),
            ('Employed' , 0),
            ('Unemployed' , 1),
            ('Part-time' , 2),
            ('Retired' , 3),
            ('Student' , 4),
            ('Pre-employment age' , 5),
            ('Other' , 98),
            
            ] ) )

CodeRegistry.register_code(
    'Surgery Type',
    Code( [  ('Unknown' , 99),
             ('Temporal lobectomy' , 0),
             ('Frontal lobectomy' , 1),
             ('Topectomy' , 2),
             ('Hemispherectomy' , 3),
             ('Callosotemy' , 4),
             ('Subpial transection' , 5),
             ('Multiple cortical transection' , 6),
             ('Transventricular Amygdalo/hippocampectomy', 7),
             ('Other' ,  98),
             
             ] ) )

CodeRegistry.register_code(
    'EEG classification',
    Code( [  ('Unknown' , 99),
             ('Ictal' , 0),
             ('Pre-ictal' , 1),
             ('Post-ictal' , 2),
             ('Inter-ictal' , 3),
             ('Ictal and interictal' , 4),
             ('Focal discharge' , 5),
             ('Other' ,  98),
             
             ] ) )

CodeRegistry.register_code(
    'EEG type',
    Code( [ ('Unknown' , 99),
            ('Stable focal onset w/ generalization' , 0),
            ('Stable seizure path w/ generalization' , 1),
            ('Multifocal onset w/ generalization' , 2),
            ('Stable focal onset w/o generalization' , 3),
            ('Stable seizure path w/o generalization' , 4),
            ('Multifocal onset w/o generalization' , 5),
            ('Stable interictal focal activity consistent w/ focal start of seizure' , 6),
            ('Stable interictal focal activity inconsistent w/ focal start of seizure' , 7),            
            ('Other' ,  98),
            
            ] ) )

CodeRegistry.register_code(
    'EEG file type',
    Code( [ ('Nicolet BMSI' , 1),            
            ('European Data Format' , 0),          
            ('Neuroscan ASCII' , 2),
            ('Neuroscan CNT' , 3),
            ('Float array' , 4),
            ('W18' , 5),
            ('Other' ,  98),
            ('Unknown' , 99),
            ] ) )

CodeRegistry.register_code(
    'Multifile type',
    Code( [('Unknown' , 99),
           ('MRI Pre-Op' , 0),
           ('MRI Post-Op' , 1),
           ('CT Pre-Op' , 2),
           ('CT Post-Op' , 3),
           ('PET' , 4),
           ('Other' ,  98),
            
            ] ) )

# These are files that supplement data in another file on the
# database, like a bad electrodes file associated with an EEG
CodeRegistry.register_code(
    'Associated File',
    Code( [  ('Unknown' , 99),
             ('EEG MPG' , 0),
             ('EEG BNI' , 1),
             ('EEG bad channels' , 2),
             ('EEG amplifier config' , 3),
             ('EEG grid data' , 4),
             ('EEG EOI' , 5),
             ('EEG Filt' , 6),
             ('CT zip' , 9),
             ('MRI zip' , 10),
             ('Annotation data', 13),

             ('Cohstat XYZ' , 7),
             ('Cohstat DAT' , 11),

             ('Loc3dJr CSV' , 8),
             ('Loc3dJr Info' , 12),
             ('Other' ,  98),
             
             ] ) )

CodeRegistry.register_code(
    'Seizure classification',
    Code( [ ('Unknown' , 99),
            ('Simple partial' , 1),
            ('Complex partial' , 2), 
            ('Partial w/ secondary generalization' , 3),
            ('Generalized abscence' , 4),
            ('Generalized myoclonic' , 5),
            ('Generalized atonic' , 6),
            ('Other' ,  98),
            
            ] ) )

CodeRegistry.register_code(
    'Behavioral State',
    Code( [ ('Unknown' , 99),
            ('Awake - alert' , 1),
            ('Drowsy' , 2), 
            ('Asleep' , 3),
            ('Other' ,  98),

            ] ) )

CodeRegistry.register_code(
    'Image classification',
    Code( [ ('Unknown' , 99),
            ('Photo Pre-Op' , 1),
            ('Photo Intra-Op' , 2), 
            ('Photo Post-Op' , 3),
            ('Electrode Grid Scan' , 4),
            ('Skull film' , 5),
            ('MRI' , 6),
            ('CAT' , 7),
            ('Other' ,  98),
            
            ] ) )

CodeRegistry.register_code(
    'Annotation code',
    Code([('Unknown', 99),
          ('Other', 98)]))
        
def register_stock_icons():
    try:
        import pygtk
#        pygtk.require('2.0')
        import gtk
    except: return
    items = [
        ('jdh-hide', '_Hide', 0, 0, None),
        ('jdh-auto', '_Auto', 0, 0, None),
             ]

    # We're too lazy to make our own icons, so we use regular stock icons.
    aliases = [
        ('jdh-hide', gtk.STOCK_CANCEL),
        ('jdh-auto', gtk.STOCK_EXECUTE),
               ]

    gtk.stock_add(items)

    factory = gtk.IconFactory()
    factory.add_default()

    for new_stock, alias in aliases:
        icon_set = gtk.icon_factory_lookup_default(alias)
        factory.add(new_stock, icon_set)
    
register_stock_icons()            

