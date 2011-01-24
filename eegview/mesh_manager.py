from __future__ import division
import sys, os, math
import vtk

from pbrainlib.gtkutils import error_msg, simple_msg, make_option_menu,\
     get_num_value, get_num_range, get_two_nums, str2int_or_err,\
     OpenSaveSaveAsHBox, ButtonAltLabel

import pickle

from scipy import array, zeros, ones, sort, absolute, sqrt, divide,\
     argsort, take, arange

class MeshManager:
    """
    CLASS: MeshManager
    DESCR: Handles rendering of VTK mesh (e.g. segmented cortex from ITK-Snap).
    """
    def __init__ (self, interactor, renderer, mesh_filename, reg_filename):

        self.interactor = interactor
        self.renderer = renderer

        reader = vtk.vtkStructuredPointsReader()
        reader.SetFileName(mesh_filename)

        cf = vtk.vtkContourFilter()
        cf.SetInput(reader.GetOutput())
        cf.SetValue(0, 1)
        deci = vtk.vtkDecimatePro()
        deci.SetInput(cf.GetOutput())
        deci.SetTargetReduction(.1)
        deci.PreserveTopologyOn()


        smoother = vtk.vtkSmoothPolyDataFilter()
        smoother.SetInput(deci.GetOutput())
        smoother.SetNumberOfIterations(100)

        normals = vtk.vtkPolyDataNormals()
        normals.SetInput(smoother.GetOutput())
        normals.FlipNormalsOn()
        normals.SetFeatureAngle(60.0)

        stripper = vtk.vtkStripper()
        stripper.SetInputConnection(normals.GetOutputPort())


        lut = vtk.vtkLookupTable()
        lut.SetHueRange(0, 0)
        lut.SetSaturationRange(0, 0)
        lut.SetValueRange(0.2, 0.55)
        
        contourMapper = vtk.vtkPolyDataMapper()
        #contourMapper.SetInput(normals.GetOutput())
        contourMapper.SetInput(stripper.GetOutput())
        contourMapper.SetLookupTable(lut)

        self.contours = vtk.vtkActor()
        self.contours.SetMapper(contourMapper)
        #self.contours.GetProperty().SetRepresentationToWireframe()
        self.contours.GetProperty().SetRepresentationToSurface()
        #self.contours.GetProperty().SetInterpolationToGouraud()
        #self.contours.GetProperty().SetOpacity(1.0)
        #self.contours.GetProperty().SetAmbient(0.1)
        self.contours.GetProperty().SetDiffuse(0.1)
        #self.contours.GetProperty().SetSpecular(0.1)
        #self.contours.GetProperty().SetSpecularPower(0.1)

        # now setmatrix() on the actor from the reg file !

        def array_to_vtkmatrix4x4(scipy_array):
            vtkmat = vtk.vtkMatrix4x4()
            for i in range(0,4):
                for j in range(0,4):
                    vtkmat.SetElement(i,j, scipy_array[i,j])
            return vtkmat

        mat = pickle.load(file(reg_filename, 'r'))


        vtkmat = array_to_vtkmatrix4x4(mat)

        self.contours.SetUserMatrix(vtkmat)
        self.contours.GetProperty().SetOpacity(.38) #maybe this should be adjustable?
        
        # XXX YAH somehow get a callback when actor is moved...
        
        self.renderer.AddActor(self.contours)
        
        
