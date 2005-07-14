#!/usr/bin/env python
import pygtk
pygtk.require('2.0')
import gtk
import vtk
from plane_widgets import PlaneWidgetsWithObservers

from matplotlib.cbook import flatten
from matplotlib.numerix.mlab import amin, amax
from matplotlib.numerix import array

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

#gtk.idle_add(idle)


#from pbrainlib.pyshell import Shell_Gui
#shell=Shell_Gui(with_window=1, namespace={'pwo':pwo})

"""
pd = pwo.dlgSurf.paramd
props = pd['electrodes']
connect = props.connect
deci = props.deci
mc = props.marchingCubes
poly = connect.GetOutput()
cella = poly.GetPolys()
>>> import vtk
>>> writer = vtk.vtkDataSetWriter()
>>> writer.SetInput(poly)
>>> writer.SetFileName('poly.dat')
>>> writer.SetFileTypeToASCII()
>>> writer.Write()
>>> 
"""

def get_surf_props(name):
    """
    return the marching cubes, connectivity, and decimate fileter for
    name
    Eg 
    mc, conn, deci = get_surf_props('electrodes')
    """
    props = pwo.dlgSurf.paramd[name]
    conn = props.connect
    mc = props.marchingCubes
    deci = props.deci
    return mc, conn, deci 

    
def write_vtkdata(conn, fname):
    'write the poly data from the connectivity filter to fname'
    writer = vtk.vtkDataSetWriter()
    writer.SetInput(conn.GetOutput())
    writer.SetFileName(fname)
    writer.SetFileTypeToASCII()
    writer.Write()

def write_stldata(filter, fname):
    'write the poly data from the filter to fname'
    writer = vtk.vtkSTLWriter()
    writer.SetFileTypeToBinary()
    writer.SetInput(filter.GetOutput())
    writer.SetFileName(fname)
    writer.Write()



def conn_to_msh(surfname, fname):
    """
    Dump connectivity filter identified by surfname to fname
    
    """
    mc, conn, deci = get_surf_props(surfname)
    poly = conn.GetOutput()
    numTetra, pointd, faced = build_mesh_structs(poly)
    fh = file(fname, 'w', False)
    write_msh(fh, numTetra, pointd, faced)

def dec_to_msh(surfname, fname):
    """
    Dump decimate filter identified by surfname to fname
    
    """
    mc, conn, deci = get_surf_props(surfname)
    poly = deci.GetOutput()
    numTetra, pointd, faced = build_mesh_structs(poly)
    fh = file(fname, 'w', False)
    write_msh(fh, numTetra, pointd, faced)

    
def write_msh(fh, numTetra, pointd, faced):
    """
    pointd is a mapping from point ind to x,y,z faced is a mapping
    from (i,j,k) where i,j,k are point inds, to list of tetra ids that
    abut face

    mc, conn, deci = get_surf_props('electrodes')
    poly = conn.GetOutput()
    numTetra, pointd, faced = build_mesh_structs(poly)
    fh = file('tmp.msh', 'w', False)
    write_msh(fh, numTetra, pointd, faced)
    

    """

    def mshhex(num):
        return hex(num).upper()[2:]
    numVerts = len(pointd)
    numVertsHex = mshhex(numVerts)
    print >> fh,  """\
(0 "GAMBIT to Fluent File")

(0 "Dimension:")
(2 3)

(10 (0 1 %s 1 3))
(10 (1 1 %s 1 3)("""%(numVertsHex,numVertsHex)
    
    items = pointd.items()
    items.sort()
    for i,xyz in items:
        print >>fh, '   %1.10e   %1.10e    %1.10e'%xyz
    print >>fh, '))'
    
    numPolysAll = len(faced)
    # find the number of polys on the surf by counting how many values
    # in the faced have len(1)

    faceItems = faced.items()
    faceItems.sort()

    facesSurf = [face for face, seq in faceItems if len(seq)==1]
    facesInterior = [face for face, seq in faceItems if len(seq)==2]    

    numFacesInterior = len(facesInterior)
    numFacesSurf = len(facesSurf)
    numFacesAll = numFacesSurf + len(facesInterior)
    
    numFacesHexAll = mshhex(numFacesAll)
    numFacesHexSurf = mshhex(numFacesSurf)

    print >>fh, """\

(0 "Faces:")
(13(0 1 %s 0))
(13(3 1 %s  3 0)("""%(numFacesHexAll, numFacesHexSurf)
    


    
    for face in facesSurf:
        v0, = faced[face]
        i,j,k = face
        print >>fh, ' '.join([mshhex(val) for val in (3, i+1, j+1, k+1, v0+1, 0)])

    print >>fh, '))'

    # now we have to compute the min and max points in the interior
    
    intpoints = array([p for p in flatten(facesInterior)])
    pmin = amin(intpoints)+1
    pmax = amax(intpoints)+1    
    
    # numFaces ind1 ind2 ... indNumFaces vol1 vol2 print >> fh, '(13(5
    #%s %s 2 0)('%(mshhex(numFacesSurf+pmin),
    #mshhex(numFacesSurf+pmax))
    print >> fh, '(13(5  %s %s 2 0)('%(mshhex(numFacesSurf+1), mshhex(numFacesAll))    
    for face in facesInterior:
        v0, v1 = faced[face]
        i,j,k = face
        print >>fh, ' '.join([mshhex(val) for val in (3, i+1, j+1, k+1, v0+1, v1+1)])
    
    print >>fh, '))'

    print >> fh, """\

(0 "Cells:")
(12 (0 1 %s 0))
(12 (2 1 %s 1 2))

(0 "Zones:")
(45 (2 fluid fluid)())
(45 (3 wall wall)())
(45 (5 interior default-interior)())
    """%(mshhex(numTetra), mshhex(numTetra))


def build_mesh_structs(poly):
    """
    Do a vtkDelaunay3D triangulation on poly data, and return the
    numTetra, pointd, faced needed to build a mesh file

    The pointd is a seen dict of all point IDs, the faced is a dict
    mapping (i,j,k) vertex indices to a list of volume numbers
    

    Eg
    mc, conn, deci = get_surf_props('electrodes')
    poly = conn.GetOutput()
    numTetra, pointd, faced = build_mesh_structs(poly)
    """
    delny  = vtk.vtkDelaunay3D()
    delny.SetInput(poly)

    ugrid = delny.GetOutput()
    ugrid.Update()
    numTetra = ugrid.GetNumberOfCells()

    pointd = {} # a seen dict of point ids
    faced = {}  # a dict mapping i,j,k point ind -> list of volume nums

    poly.Update()
    points = poly.GetPoints()

    for itetra in range(numTetra):
        cell = ugrid.GetCell(itetra)
        tetfaces = []
        for iface in range(cell.GetNumberOfFaces()):
            face = cell.GetFace(iface)
            i0 = face.GetPointId(0)
            i1 = face.GetPointId(1)
            i2 = face.GetPointId(2)            
            pointd[i0] = points.GetPoint(i0)        
            pointd[i1] = points.GetPoint(i1)
            pointd[i2] = points.GetPoint(i2)
            # sort these so vertex order is irrelevant
            if i0==i1 or i0==i2 or i1==i2:
                raise ValueError('identical vertices')

            face = [i0, i1, i2]
            face.sort()
            face = tuple(face)
            faced.setdefault(face, []).append(itetra)

    points = pointd.keys()
    points.sort()

    orderd = dict([ (point, i) for i, point in enumerate(points)])

    newpointd = {}
    for point, xyz in pointd.items():
        newpointd[orderd[point]] = xyz


    newfaced = {}
    for verts, volumes in faced.items():
        i,j,k = verts
        im = orderd[i]
        jm = orderd[j]
        km = orderd[k]
        newfaced[(im, jm, km)] = volumes

    return numTetra, newpointd, newfaced

gtk.mainloop()


"""
mc, conn, deci = get_surf_props('electrodes')
poly = deci.GetOutput()
numTetra, pointd, faced = build_mesh_structs(poly)
fh = file('reorder.msh', 'w', False)
write_msh(fh, numTetra, pointd, faced)

faceItems = faced.items()
faceItems.sort()
facesInterior = [face for face, seq in faceItems if len(seq)==2]
facesInterior[0]
Out[10]: (0, 1, 5)


"""

