#!/usr/bin/env python

import os
import sys
import json
import math
import numpy
import random
from mapgen2 import MapGenXml
from mapgen2 import Z_SCALE
from optparse import OptionParser
from meshtool.filters.print_filters.print_bounds import getBoundsInfo, v3dist
from panda3d.core import Vec3, Quat

import open3dhub

TERRAIN_PATH = '/jterrace/mapgen_terrain_1.dae/0'
ROAD_PATH = '/kittyvision/street.dae/0'

def v3mid(pt1, pt2):
    return numpy.array([(pt1[0] + pt2[0]) / 2.0,
                        (pt1[1] + pt2[1]) / 2.0,
                        (pt1[2] + pt2[2]) / 2.0],
                       dtype=numpy.float32)

def get_tag_type(tag):
    print 'Finding tag "%s"...' % tag,
    L = open3dhub.get_search_list('tags:"%s"' % tag)
    print 'received %d' % len(L)
    return L

def get_models():
    model_types = {
        'houses': get_tag_type('house'),
        'trees': get_tag_type('tree'),
        'lawn': get_tag_type('lawn'),
        'flying': get_tag_type('flying'),
        'street': get_tag_type('street'),
        'underwater': get_tag_type('underwater'),
        'winter': get_tag_type('winter'),
        'vehicle': get_tag_type('vehicle'),
        'building': get_tag_type('building'),
        'roads': get_tag_type('road'),
    }
    return model_types

def sirikata_bounds(boundsInfo):
    minpt, maxpt = boundsInfo['bounds']
    minpt, maxpt = numpy.copy(minpt), numpy.copy(maxpt)
    
    center = boundsInfo['center']
    center_distance = boundsInfo['center_farthest_distance']
    
    # center the bounding box
    minpt -= center
    maxpt -= center
    
    # bounding box is scaled by 1 / (distance from center to farthest point)
    minpt /= center_distance
    maxpt /= center_distance
    
    return (minpt, maxpt)

def height_offset(boundsInfo):
    minpt, maxpt = sirikata_bounds(boundsInfo)
    height_range = (maxpt[2] - minpt[2])
    return height_range / 2.0

class SceneModel(object):
    def __init__(self, path, x, y, z, scale):
        self.path = path
        
        self.x = x
        self.y = y
        self.z = z
        
        self.scale = scale
        
        self.orient_x = 0
        self.orient_y = 0
        self.orient_z = 0
        self.orient_w = 1
        
        self._metadata = None
        self._mesh = None
        self._boundsInfo = None
        
    def _load_mesh(self):
        if self._mesh is None:
            self._metadata, self._mesh = open3dhub.path_to_mesh(self.path, cache=True)
        
    def _get_mesh(self):
        self._load_mesh()
        return self._mesh
    
    mesh = property(_get_mesh)
    
    def _get_metadata(self):
        self._load_mesh()
        return self._metadata

    metadata = property(_get_metadata)
    
    def _get_bounds_info(self):
        if self._boundsInfo is None:
            self._boundsInfo = getBoundsInfo(self.mesh)
        return self._boundsInfo
    
    boundsInfo = property(_get_bounds_info)
    
    center = property(lambda s: s.boundsInfo['center'])
    
    v3 = property(lambda s: numpy.array([s.x, s.y, s.z], dtype=numpy.float32))
    
    sirikata_uri = property(lambda s: 'meerkat:///' +
                                        s.metadata['basepath'] + '/' +
                                        'optimized' + '/' +
                                        s.metadata['version'] + '/' + 
                                        s.metadata['basename'])
    def to_json(self):
        z = self.z + height_offset(self.boundsInfo) * self.scale
        
        # below swaps from z-up to y-up
        return {
            'path': self.path,
            'sirikata_uri': self.sirikata_uri,
            'x': self.x,
            'y': z,
            'z': -1.0 * self.y,
            'orient_x': self.orient_x,
            'orient_y': self.orient_z,
            'orient_z': -1.0 * self.orient_y,
            'orient_w': self.orient_w,
            'scale': self.scale,
        }

def mapgen_coords_to_sirikata(loc, terrain):
    # mapgen starts at 0,0,0 as the corner, but terrain gets centered at 0,0,0
    loc = loc - terrain.center
    # scale the coordinates to the scaled coordinates of the terrain mesh
    loc /= terrain.boundsInfo['center_farthest_distance']
    # then scale back by the terrain's scale
    loc *= terrain.scale
    # adjust the height by how much the terrain is offset
    loc[2] += height_offset(terrain.boundsInfo) * terrain.scale
    return loc

def main():
    parser = OptionParser(usage="Usage: generate-scene.py -o scene.json map.xml",
                          description="Generates a JSON scene based on mapgen2 XML output, using meshes from open3dhub")
    parser.add_option("-o", "--outname", dest="outname",
                      help="write JSON scene to {outname}.json and Emerson script to {outname}.em", metavar="OUTNAME")
    (options, args) = parser.parse_args()
    
    if len(args) != 1:
        parser.print_help()
        parser.exit(1, "Wrong number of arguments.\n")
    
    if not os.path.isfile(args[0]):
        parser.print_help()
        parser.exit(1, "Input file '%s' is not a valid file.\n" % args[0])
    
    if options.outname is None:
        parser.print_help()
        parser.exit(1, "Must specify an output name.\n")
        
    fname = args[0]
    map = MapGenXml(fname)
    
    
    terrain = SceneModel(TERRAIN_PATH, x=0, y=0, z=0, scale=1000)
    json_out = []
    print 'Generated (1) terrain object'
    json_out.append(terrain.to_json())
    
    #models = get_models()
    
    numroads = 0
    for center in map.centers.itervalues():
        road_edges = [e for e in center.edges if e.is_road and e.corner0 is not None and e.corner1 is not None]
        if len(road_edges) != 2:
            continue
        
        e1, e2 = road_edges
        e1_0 = numpy.array([e1.corner0.x, e1.corner0.y, e1.corner0.elevation * Z_SCALE], dtype=numpy.float32)
        e1_1 = numpy.array([e1.corner1.x, e1.corner1.y, e1.corner1.elevation * Z_SCALE], dtype=numpy.float32)
        e1_mid = v3mid(e1_0, e1_1)
        e2_0 = numpy.array([e2.corner0.x, e2.corner0.y, e2.corner0.elevation * Z_SCALE], dtype=numpy.float32)
        e2_1 = numpy.array([e2.corner1.x, e2.corner1.y, e2.corner1.elevation * Z_SCALE], dtype=numpy.float32)
        e2_mid = v3mid(e2_0, e2_1)
        
        midpt = v3mid(e1_mid, e2_mid)
        midpt = mapgen_coords_to_sirikata(midpt, terrain)
        
        kata_pt1 = mapgen_coords_to_sirikata(e1_mid, terrain)
        kata_pt2 = mapgen_coords_to_sirikata(e2_mid, terrain)
        
        scale = v3dist(kata_pt1, kata_pt2) / 2
        
        m = SceneModel(ROAD_PATH,
                       x=float(midpt[0]),
                       y=float(midpt[1]),
                       z=float(midpt[2]) + 5,
                       scale=scale)
        
        kataboundmin, kataboundmax = sirikata_bounds(m.boundsInfo)
        scenemin = kataboundmin * scale + midpt
        scenemax = kataboundmax * scale + midpt
        xmid = (scenemax[0] - scenemin[0]) / 2.0 + scenemin[0]
        road_edge1 = numpy.array([xmid, scenemin[1], scenemin[2]], dtype=numpy.float32)
        road_edge2 = numpy.array([xmid, scenemax[1], scenemin[2]], dtype=numpy.float32)
        
        midv3 = Vec3(midpt[0], midpt[1], midpt[2])
        src = Vec3(road_edge2[0], road_edge2[1], road_edge2[2])
        src -= midv3
        src_copy = Vec3(src)
        target = Vec3(kata_pt1[0], kata_pt1[1], kata_pt1[2])
        target -= midv3
        cross = src.cross(target)
        w = math.sqrt(src.lengthSquared() * target.lengthSquared()) + src.dot(target)
        q = Quat(w, cross)
        q.normalize()
        
        m.orient_x = q.getI()
        m.orient_y = q.getJ()
        m.orient_z = q.getK()
        m.orient_w = q.getR()
        
        numroads += 1
        json_out.append(m.to_json())
    
    print 'Generated (%d) road objects' % numroads
    
    #c1 = next(map.centers.itervalues())
    #center_loc = numpy.array([c1.x, c1.y, c1.elevation], dtype=numpy.float32)
    #center_loc = mapgen_coords_to_sirikata(center_loc, terrain)
    
    #building_path = models['building'][0]['full_path']
    #building = SceneModel(building_path, x=float(center_loc[0]), y=float(center_loc[1]), z=float(center_loc[2]), scale=50)
    
    json_str = json.dumps(json_out, indent=2)
    
    json_name = options.outname + '.json'
    with open(json_name, 'w') as f:
        f.write(json_str)
    
    em_name = options.outname + '.em'
    with open(em_name, 'w') as f:
        f.write('var OBJECTS = ')
        f.write(json_str)
        f.write(';\n')
    
    #dae = tocollada(map.centers, map.corners, map.edges)
    #dae.write(options.outfile)

if __name__ == '__main__':
    main()
