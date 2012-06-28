#!/usr/bin/env python

import os
from mapgen2 import MapGenXml, X_SCALE, Y_SCALE, Z_SCALE, COLORS, hex2rgb
from optparse import OptionParser
    
def visualize(centers, corners, edges):
    from meshtool.filters.panda_filters.pandacore import getVertexData, attachLights, ensureCameraAt
    from meshtool.filters.panda_filters.pandacontrols import KeyboardMovement, MouseDrag, MouseScaleZoom, MouseCamera
    from panda3d.core import GeomPoints, GeomTriangles, Geom, GeomNode, GeomVertexFormat, GeomVertexData, GeomVertexWriter, LineSegs, VBase3
    from direct.showbase.ShowBase import ShowBase
    
    format = GeomVertexFormat.getV3c4()
    vdata = GeomVertexData('pts', format, Geom.UHDynamic)
    vertex = GeomVertexWriter(vdata, 'vertex')
    color = GeomVertexWriter(vdata, 'color')
    
    vertex_index = 0
    center_vertex_indices = {}
    corner_vertex_indices = {}
    for key, center in centers.iteritems():
        vertex.addData3f(center.x * X_SCALE, center.y * Y_SCALE, center.elevation * Z_SCALE)
        curcolor = hex2rgb(COLORS[center.biome])
        color.addData4f(curcolor[0], curcolor[1], curcolor[2], 1)
        center_vertex_indices[key] = vertex_index
        vertex_index += 1
        
        for corner in center.corners:
            vertex.addData3f(corner.x * X_SCALE, corner.y * Y_SCALE, corner.elevation * Z_SCALE)
            color.addData4f(curcolor[0], curcolor[1], curcolor[2], 1)
            corner_vertex_indices[corner.id] = vertex_index
            vertex_index += 1
    
    tris = GeomTriangles(Geom.UHDynamic)
    
    for edge in edges.itervalues():
        corner0 = edge.corner0
        corner1 = edge.corner1
        center0 = edge.center0
        center1 = edge.center1
        if corner0 is None or corner1 is None:
            continue
        
        tris.addVertices(corner_vertex_indices[corner1.id],
                         corner_vertex_indices[corner0.id],
                         center_vertex_indices[center0.id])
        
        tris.addVertices(center_vertex_indices[center1.id],
                         corner_vertex_indices[corner0.id],
                         corner_vertex_indices[corner1.id])
        
    
    tris.closePrimitive()

    pgeom = Geom(vdata)
    pgeom.addPrimitive(tris)

    node = GeomNode("primitive")
    node.addGeom(pgeom)

    p3dApp = ShowBase()
    attachLights(render)
    geomPath = render.attachNewNode(node)
    #geomPath.setRenderModeThickness(6.0)
    
    #geomPath.setRenderModeWireframe()
    
    ensureCameraAt(geomPath, base.cam)
    
    boundingSphere = geomPath.getBounds()
    base.cam.setPos(boundingSphere.getCenter() + boundingSphere.getRadius())

    base.cam.lookAt(boundingSphere.getCenter())
    
    geomPath.setScale(VBase3(50,50,50))
    
    KeyboardMovement()
    #MouseDrag(geomPath)
    MouseCamera()
    MouseScaleZoom(geomPath)
    #render.setShaderAuto()
    p3dApp.run()

def main():
    parser = OptionParser(usage="Usage: renderxml.py map.xml",
                          description="Renders a mapgen2 XML file using Panda3D")
    (options, args) = parser.parse_args()
    
    if len(args) != 1:
        parser.print_help()
        parser.exit(1, "Wrong number of arguments.\n")
    
    if not os.path.isfile(args[0]):
        parser.print_help()
        parser.exit(1, "Input file '%s' is not a valid file.\n" % args[0])
        
    fname = args[0]
    map = MapGenXml(fname)
    
    map.print_info()
    visualize(map.centers, map.corners, map.edges)

if __name__ == '__main__':
    main()
