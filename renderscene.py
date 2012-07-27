#!/usr/bin/env python

import os
import sys
import json
from optparse import OptionParser

import numpy
import direct.showbase.ShowBase as ShowBase
import panda3d.core as p3d
import collada
import meshtool.filters.panda_filters.pandacore as pcore
import meshtool.filters.panda_filters.pandacontrols as controls
import meshtool.filters.print_filters.print_bounds as print_bounds

import cache
import scene

def centerAndScale(nodePath, boundsInfo):
    wrapNode = None

    parentNP = nodePath.getParent()
    nodePath.detachNode()
    nodePath.setName('wrapper-centering-collada')
    newRoot = parentNP.attachNewNode('newroot')
    scaleNode = newRoot.attachNewNode('scaler')
    nodePath.reparentTo(scaleNode)

    center = boundsInfo['center']
    center_distance = boundsInfo['center_farthest_distance']

    nodePath.setPos(-1 * center[0],
                    -1 * center[1],
                    -1 * center[2])

    scale = 1.0 / center_distance
    scaleNode.setScale(scale, scale, scale)
    
    return newRoot

class SceneRenderer(ShowBase.ShowBase):
    def __init__(self, models):
        ShowBase.ShowBase.__init__(self)
        
        self.models = models
        
        unique_meshes = set(m.mesh for m in models)
        mesh2nodepath = {}
        for mesh in unique_meshes:
            scene_members = pcore.getSceneMembers(mesh)
            
            rotateNode = p3d.GeomNode("rotater")
            rotatePath = p3d.NodePath(rotateNode)
            matrix = numpy.identity(4)
            if mesh.assetInfo.upaxis == collada.asset.UP_AXIS.X_UP:
                r = collada.scene.RotateTransform(0,1,0,90)
                matrix = r.matrix
            elif mesh.assetInfo.upaxis == collada.asset.UP_AXIS.Y_UP:
                r = collada.scene.RotateTransform(1,0,0,90)
                matrix = r.matrix
            rotatePath.setMat(p3d.Mat4(*matrix.T.flatten().tolist()))
            
            rbc = p3d.RigidBodyCombiner('combiner')
            rbcPath = rotatePath.attachNewNode(rbc)
            
            for geom, renderstate, mat4 in scene_members:
                node = p3d.GeomNode("primitive")
                node.addGeom(geom)
                if renderstate is not None:
                    node.setGeomState(0, renderstate)
                geomPath = rbcPath.attachNewNode(node)
                geomPath.setMat(mat4)
                
            rbc.collect()

            mesh2nodepath[mesh] = centerAndScale(rotatePath, print_bounds.getBoundsInfo(mesh))

        scenepath = render.attachNewNode("scene")
        for model in self.models:
            np = mesh2nodepath[model.mesh]
            instance = scenepath.attachNewNode("model")
            np.instanceTo(instance)
            instance.setPos(model.x, model.y, model.z)
            instance.setScale(model.scale, model.scale, model.scale)
            q = p3d.Quat()
            q.setI(model.orient_x)
            q.setJ(model.orient_y)
            q.setK(model.orient_z)
            q.setR(model.orient_w)
            instance.setQuat(q)

        base.camLens.setFar(sys.maxint)
        base.camLens.setNear(8.0)

        pcore.attachLights(render)

        render.setShaderAuto()
        render.setTransparency(p3d.TransparencyAttrib.MDual, 1)
        render.setAntialias(p3d.AntialiasAttrib.MAuto)

        controls.KeyboardMovement()
        controls.ButtonUtils(scenepath)
        controls.MouseDrag(scenepath)
        controls.MouseCamera()
        controls.MouseScaleZoom(scenepath)
        

def main():
    parser = OptionParser(usage="Usage: renderscene.py scene.json",
                          description="Renders a JSON scene file")
    (options, args) = parser.parse_args()
    
    if len(args) != 1:
        parser.print_help()
        parser.exit(1, "Wrong number of arguments.\n")
    
    if not os.path.isfile(args[0]):
        parser.print_help()
        parser.exit(1, "Input file '%s' is not a valid file.\n" % args[0])
        
    fname = args[0]
    json_data = json.load(open(fname))
    
    print 'Fetching models'
    models = [scene.SceneModel.from_json(j) for j in json_data]
    
    print 'Starting scene'
    r = SceneRenderer(models)
    r.run()

if __name__ == '__main__':
    main()
