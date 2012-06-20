#!/usr/bin/env python

import os.path
from mapgen2 import MapGenXml, X_SCALE, Y_SCALE, Z_SCALE, COLORS, hex2rgb
from optparse import OptionParser

def tocollada(centers, corners, edges):
    import collada
    import numpy
    
    mesh = collada.Collada()
    biome_materials = {}
    biome_triangles = {}
    for name, diffuse_value in COLORS.iteritems():
        effect = collada.material.Effect("effect-" + name, [], "phong", diffuse=hex2rgb(diffuse_value))
        mesh.effects.append(effect)
        mat = collada.material.Material("material-" + name, "material-" + name, effect)
        mesh.materials.append(mat)
        biome_materials[name] = mat
        biome_triangles[name] = []
    
    vertex = []
    vertex_index = 0
    center_vertex_indices = {}
    corner_vertex_indices = {}
    for key, center in centers.iteritems():
        vertex.append([center.x * X_SCALE, center.y * Y_SCALE, center.elevation * Z_SCALE])
        center_vertex_indices[key] = vertex_index
        vertex_index += 1
        
        for corner in center.corners:
            vertex.append([corner.x * X_SCALE, corner.y * Y_SCALE, corner.elevation * Z_SCALE])
            corner_vertex_indices[corner.id] = vertex_index
            vertex_index += 1
            
        for edge in center.edges:
            corner0 = edge.corner0
            corner1 = edge.corner1
            center0 = edge.center0
            center1 = edge.center1
            if corner0 is None or corner1 is None:
                continue
            
            if key == center0.id:
                newtri = [corner_vertex_indices[corner1.id],
                          corner_vertex_indices[corner0.id],
                          center_vertex_indices[center0.id]]
            
            elif key == center1.id:
                newtri = [center_vertex_indices[center1.id],
                          corner_vertex_indices[corner0.id],
                          corner_vertex_indices[corner1.id]]
                
            biome_triangles[center.biome].append(newtri)
       
    vertex_arr = numpy.array(vertex, dtype=numpy.float32)
    vert_src = collada.source.FloatSource("terrain-verts-array", vertex_arr, ('X', 'Y', 'Z'))
    geom = collada.geometry.Geometry(mesh, "terrain-geometry", "terrain-geometry", [vert_src])
    input_list = collada.source.InputList()
    input_list.addInput(0, 'VERTEX', "#terrain-verts-array")
    
    matnodes = []
    for biome_name in COLORS.iterkeys():
        biome_material = biome_materials[biome_name]
        biome_indices = numpy.array(biome_triangles[biome_name], dtype=numpy.int32)
        
        triset = geom.createTriangleSet(biome_indices, input_list, biome_material.id)
        geom.primitives.append(triset)
        
        matnode = collada.scene.MaterialNode(biome_material.id, biome_material, inputs=[])
        matnodes.append(matnode)
    
    mesh.geometries.append(geom)
    geomnode = collada.scene.GeometryNode(geom, matnodes)
    node = collada.scene.Node("node0", children=[geomnode])
    scene = collada.scene.Scene("scene0", [node])
    mesh.scenes.append(scene)
    mesh.scene = scene
    mesh.assetInfo.upaxis = collada.asset.UP_AXIS.Z_UP
    
    return mesh

def main():
    parser = OptionParser(usage="Usage: map2collada.py -o file.dae map.xml",
                          description="Converts mapgen2 XML file to COLLADA using pycollada")
    parser.add_option("-o", "--outfile", dest="outfile",
                      help="write DAE to FILE", metavar="OUTFILE")
    (options, args) = parser.parse_args()
    
    if len(args) != 1:
        parser.print_help()
        parser.exit(1, "Wrong number of arguments.\n")
    
    if not os.path.isfile(args[0]):
        parser.print_help()
        parser.exit(1, "Input file '%s' is not a valid file.\n" % args[0])
    
    if options.outfile is None:
        parser.print_help()
        parser.exit(1, "Must specify an output file.\n")
        
    fname = args[0]
    map = MapGenXml(fname)
    map.print_info()
    dae = tocollada(map.centers, map.corners, map.edges)
    dae.write(options.outfile)

if __name__ == '__main__':
    main()
