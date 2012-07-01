#!/usr/bin/env python

import os.path
from mapgen2 import MapGenXml, X_SCALE, Y_SCALE, Z_SCALE, COLORS, hex2rgb
from optparse import OptionParser
import networkx as nx
import math
import random
from clint.textui import progress
from PIL import Image, ImageDraw
from StringIO import StringIO
from meshtool.filters.simplify_filters.graph_utils import super_cycle
from meshtool.filters.simplify_filters.sander_simplify import v3dist, transformblit, v2dist
from meshtool.filters.optimize_filters.generate_normals import generateNormals

TEXTURE_WIDTH = 4096.0
TEXTURE_HEIGHT = 4096.0

CURDIR = os.path.dirname(os.path.abspath(__file__))
TEXTURE_DIR = os.path.join(CURDIR, 'textures')

TEXTURE_MAP = {
    'OCEAN': 'ocean.jpg',
    #'COAST': 0x33335a,
    #'LAKESHORE': 0x225588,
    'LAKE': 'lake.jpg',
    #'RIVER': 0x225588,
    'MARSH': 'marsh.jpg',
    #'ICE': 0x99ffff,
    'BEACH': 'beach.jpg',
    #'ROAD1': 0x442211,
    #'ROAD2': 0x553322,
    #'ROAD3': 0x664433,
    #'BRIDGE': 0x686860,
    #'LAVA': 0xcc3333,
    'SNOW': 'snow.jpg',
    'TUNDRA': 'tundra.jpg',
    'BARE': 'bare.jpg',
    #'SCORCHED': 0x555555,
    'TAIGA': 'taiga.jpg',
    'SHRUBLAND': 'shrubland.jpg',
    'TEMPERATE_DESERT': 'temperate_desert.jpg',
    'TEMPERATE_RAIN_FOREST': 'temperate_rain_forest.jpg',
    'TEMPERATE_DECIDUOUS_FOREST': 'temperate_deciduous_forest.jpg',
    'GRASSLAND': 'grassland.jpg',
    'SUBTROPICAL_DESERT': 'subtropical_desert.jpg',
    'TROPICAL_RAIN_FOREST': 'tropical_rain_forest.jpg',
    'TROPICAL_SEASONAL_FOREST': 'tropical_seasonal_forest.jpg',
}

def tocollada(centers, corners, edges):
    import collada
    import numpy
    
    teximgs = {}
    for key, fname in progress.bar(TEXTURE_MAP.items(), label='Loading source textures '):
        if key not in teximgs:
            i = Image.open(os.path.join(TEXTURE_DIR, fname))
            i.load()
            teximgs[key] = i
            
    #ocean = teximgs['OCEAN']
    #scale = max(TEXTURE_WIDTH / ocean.size[0], TEXTURE_HEIGHT / ocean.size[1])
    #newsize = (int(math.ceil(ocean.size[0] * scale)), int(math.ceil(ocean.size[1] * scale)))
    #ocean = ocean.resize(newsize, Image.BICUBIC)
    #texim = ocean.crop((0, 0, int(TEXTURE_WIDTH), int(TEXTURE_HEIGHT)))
    
    mesh = collada.Collada()
    
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
    
    vertex_arr = numpy.array(vertex, dtype=numpy.float32)
    
    vertexgraph = nx.Graph()
    bordergraph = nx.Graph()
    for key, center in centers.iteritems():
        centervert = center_vertex_indices[key]
        
        for edge in center.edges:
            corner0 = edge.corner0
            corner1 = edge.corner1
            center0 = edge.center0
            center1 = edge.center1
            if corner0 is None or corner1 is None:
                continue
            
            corner0vert = corner_vertex_indices[corner0.id]
            corner1vert = corner_vertex_indices[corner1.id]
            vertexgraph.add_edge(corner0vert, corner1vert)
            vertexgraph.add_edge(corner0vert, centervert)
            vertexgraph.add_edge(corner1vert, centervert)
            
            if corner0.border and corner1.border:
                bordergraph.add_edge(corner0vert, corner1vert)
            if corner0.border and center.border:
                bordergraph.add_edge(corner0vert, centervert)
            if corner1.border and center.border:
                bordergraph.add_edge(corner1vert, centervert)
                
    
    bigcycle = list(super_cycle(bordergraph))
    boundary_path = []
    for i in range(len(bigcycle)-1):
        boundary_path.append((bigcycle[i], bigcycle[i+1]))
    boundary_path.append((bigcycle[len(bigcycle)-1], bigcycle[0]))

    total_dist = 0
    for (v1, v2) in boundary_path:
        total_dist += v3dist(vertex_arr[v1], vertex_arr[v2])
    
    vert2uv = {}
    curangle = 0
    for edge in progress.bar(boundary_path, label='Parameterizing border vertices '):
        angle = v3dist(vertex_arr[edge[0]], vertex_arr[edge[1]]) / total_dist
        curangle += angle * 2 * math.pi
        x, y = (math.sin(curangle) + 1) / 2.0, (math.cos(curangle) + 1.0) / 2.0
        vert2uv[edge[0]] = (x,y)
    
    border_verts = set(bordergraph.nodes())
    interior_verts = list(set(vertexgraph.nodes()) - border_verts)
    
    vert2idx = {}
    for i, v in enumerate(interior_verts):
        vert2idx[v] = i
    
    A = numpy.zeros(shape=(len(interior_verts), len(interior_verts)), dtype=numpy.float32)
    Bu = numpy.zeros(len(interior_verts), dtype=numpy.float32)
    Bv = numpy.zeros(len(interior_verts), dtype=numpy.float32)
    sumu = numpy.zeros(len(interior_verts), dtype=numpy.float32)
    
    for edge in progress.bar(vertexgraph.edges(), label='Parameterizing interior vertices '):
        v1, v2 = edge
        if v1 in border_verts and v2 in border_verts:
            continue
        
        edgelen = v3dist(vertex_arr[v1], vertex_arr[v2])
        if v1 in border_verts:
            Bu[vert2idx[v2]] += edgelen * vert2uv[v1][0]
            Bv[vert2idx[v2]] += edgelen * vert2uv[v1][1]
            sumu[vert2idx[v2]] += edgelen
        elif v2 in border_verts:
            Bu[vert2idx[v1]] += edgelen * vert2uv[v2][0]
            Bv[vert2idx[v1]] += edgelen * vert2uv[v2][1]
            sumu[vert2idx[v1]] += edgelen
        else:
            A[vert2idx[v1]][vert2idx[v2]] = -1 * edgelen
            A[vert2idx[v2]][vert2idx[v1]] = -1 * edgelen
            sumu[vert2idx[v1]] += edgelen
            sumu[vert2idx[v2]] += edgelen
    
    Bu.shape = (len(Bu), 1)
    Bv.shape = (len(Bv), 1)
    sumu.shape = (len(sumu), 1)
    
    A /= sumu
    Bu /= sumu
    Bv /= sumu
    try: numpy.fill_diagonal(A, 1)
    except AttributeError:
        for i in xrange(len(A)):
            A[i][i] = 1
    
    print 'Solving linear equation...'
    interior_us = numpy.linalg.solve(A, Bu)
    interior_vs = numpy.linalg.solve(A, Bv)
    print 'Done'
    for (i, (u, v)) in enumerate(zip(interior_us, interior_vs)):
        vert2uv[interior_verts[i]] = (u[0], v[0])
    
    indices = []
    uv_arr = []
    uv_offset = 0
    texim = Image.new("RGBA", (int(TEXTURE_WIDTH), int(TEXTURE_HEIGHT)), (0, 0, 0, 0))
    
    # two passes
    # pass 1: paint triangles normally
    # pass 2: paint triangles with an alpha mask over existing
    # Blending disabled: doesn't work very well
    for passnum in range(1):
        for key, center in progress.bar(centers.items(), label='Creating triangles and blitting pass %d ' % passnum):
                
            for edge in center.edges:
                corner0 = edge.corner0
                corner1 = edge.corner1
                center0 = edge.center0
                center1 = edge.center1
                if corner0 is None or corner1 is None:
                    continue
                
                if key == center0.id:
                    v1 = corner_vertex_indices[corner1.id]
                    v2 = corner_vertex_indices[corner0.id]
                    v3 = center_vertex_indices[center0.id]
                elif key == center1.id:
                    v1 = center_vertex_indices[center1.id]
                    v2 = corner_vertex_indices[corner0.id]
                    v3 = corner_vertex_indices[corner1.id]
                else:
                    continue
                
                y11, y12 = vert2uv[v1]
                y21, y22 = vert2uv[v2]
                y31, y32 = vert2uv[v3]
                uv_arr.extend([y11, 1.0 - y12, y21, 1.0 - y22, y31, 1.0 - y32])
                
                srcim = teximgs[center.biome]
                triranges = [((0.2, 0.4), (0.2, 0.4)),
                             ((0.6, 0.8), (0.2, 0.4)),
                             ((0.6, 0.8), (0.6, 0.8)),
                             ((0.2, 0.4), (0.6, 0.8))]
                pts3 = random.sample(triranges, 3)
                pts3 = [(random.uniform(*p[0]), random.uniform(*p[1]))
                        for p in pts3]
                random.shuffle(pts3)
                x11 = pts3[0][0] * srcim.size[0]
                x21 = pts3[1][0] * srcim.size[0]
                x31 = pts3[2][0] * srcim.size[0]
                x12 = pts3[0][1] * srcim.size[1]
                x22 = pts3[1][1] * srcim.size[1]
                x32 = pts3[2][1] * srcim.size[1]
                
                y11 *= TEXTURE_WIDTH
                y21 *= TEXTURE_WIDTH
                y31 *= TEXTURE_WIDTH
                y12 *= TEXTURE_HEIGHT
                y22 *= TEXTURE_HEIGHT
                y32 *= TEXTURE_HEIGHT
                
                alpha = 255
                
                if passnum == 1:
                    centery = (y12 + y22 + y32) / 3.0
                    centerx = (y11 + y21 + y31) / 3.0
                    y11 += (y11 - centerx) * 0.2
                    y12 += (y12 - centery) * 0.2
                    y21 += (y21 - centerx) * 0.2
                    y22 += (y22 - centery) * 0.2
                    y31 += (y31 - centerx) * 0.2
                    y32 += (y32 - centery) * 0.2
                    
                    centery = 0.3 * (x12 + x22 + x32)
                    centerx = 0.3 * (x11 + x21 + x31)
                    x11 += (x11 - centerx) * 0.2
                    x12 += (x12 - centery) * 0.2
                    x21 += (x21 - centerx) * 0.2
                    x22 += (x22 - centery) * 0.2
                    x31 += (x31 - centerx) * 0.2
                    x32 += (x32 - centery) * 0.2
                    
                    alpha = 128
                
                transformblit(((x11,x12), (x21,x22), (x31,x32)),
                              ((y11,y12), (y21,y22), (y31,y32)),
                              srcim,
                              texim,
                              alpha=alpha)
                
                newtri = [v1, uv_offset,
                          v2, uv_offset+1,
                          v3, uv_offset+2]
                uv_offset += 3
                indices.append(newtri)
    
    cimg = collada.material.CImage("cimg1", "./texture.jpg")
    mesh.images.append(cimg)
    surface = collada.material.Surface("surface1", cimg)
    sampler = collada.material.Sampler2D("sampler1", surface)
    smap = collada.material.Map(sampler, "TEX0")
    effect = collada.material.Effect("effect1", [surface, sampler], "blinn", diffuse=smap)
    mesh.effects.append(effect)
    material = collada.material.Material("material1", "material1", effect)
    mesh.materials.append(material)
    
    vert_src = collada.source.FloatSource("terrain-verts-array", vertex_arr, ('X', 'Y', 'Z'))
    uv_arr = numpy.array(uv_arr, dtype=numpy.float32)
    uv_src = collada.source.FloatSource("terrain-uv-array", uv_arr, ('U', 'V'))
    geom = collada.geometry.Geometry(mesh, "terrain-geometry", "terrain-geometry", [vert_src, uv_src])
    input_list = collada.source.InputList()
    input_list.addInput(0, 'VERTEX', "#terrain-verts-array")
    input_list.addInput(1, 'TEXCOORD', '#terrain-uv-array')
    
    indices = numpy.array(indices, dtype=numpy.int32)
    triset = geom.createTriangleSet(indices, input_list, "material1")
    geom.primitives.append(triset)
    matnode = collada.scene.MaterialNode("material1", material, inputs=[('TEX0', 'TEXCOORD', '0')])
    
    mesh.geometries.append(geom)
    geomnode = collada.scene.GeometryNode(geom, [matnode])
    node = collada.scene.Node("node0", children=[geomnode])
    scene = collada.scene.Scene("scene0", [node])
    mesh.scenes.append(scene)
    mesh.scene = scene
    mesh.assetInfo.upaxis = collada.asset.UP_AXIS.Z_UP
    
    return mesh, texim

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
    dae, texture = tocollada(map.centers, map.corners, map.edges)
    
    generateNormals(dae)
    dae.write(options.outfile)
    
    texpath = os.path.join(os.path.dirname(options.outfile), 'texture.jpg')
    texture.save(texpath, format="JPEG", quality=95, optimize=True)

if __name__ == '__main__':
    main()
