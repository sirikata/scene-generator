#!/usr/bin/env python

import os
import sys
import json
import math
import numpy
import random
import collada
import shelve
from mapgen2 import MapGenXml
from mapgen2 import Z_SCALE
from optparse import OptionParser
from meshtool.filters.print_filters.print_bounds import v3dist
from panda3d.core import Vec3, Quat
from clint.textui import progress
from collada.util import normalize_v3

import poisson_disk
import cache
import open3dhub
import scene

TERRAIN_PATH = '/jterrace/terrain.dae/0'
ROAD_PATH = '/kittyvision/street.dae/0'

def v3mid(pt1, pt2):
    return numpy.array([(pt1[0] + pt2[0]) / 2.0,
                        (pt1[1] + pt2[1]) / 2.0,
                        (pt1[2] + pt2[2]) / 2.0],
                       dtype=numpy.float32)

def get_tag_type(tag):
    print 'Finding tag "%s"...' % tag,
    L = cache.get_tag(tag)
    print 'received %d' % len(L)
    return L

def get_models():
    model_types = {
        'houses': get_tag_type('house'),
        'trees': get_tag_type('tree'),
        'plants': get_tag_type('plant'),
        #'lawn': get_tag_type('lawn'),
        'flying': get_tag_type('flying'),
        'boats': get_tag_type('boat'),
        'winter': get_tag_type('winter'),
        #'street': get_tag_type('street'),
        #'underwater': get_tag_type('underwater'),
        'vehicles': get_tag_type('vehicle'),
        'buildings': get_tag_type('building'),
        #'roads': get_tag_type('road'),
    }
    
    trees = set(m['full_path'] for m in model_types['trees'])
    model_types['shrubs'] = [m for m in model_types['plants'] if m['full_path'] not in trees]
    
    houses = set(m['full_path'] for m in model_types['houses'])
    model_types['commercial_buildings'] = [m for m in model_types['buildings'] if m['full_path'] not in houses]
    
    return model_types

def normal_vector(a, b, c):
    direction = numpy.cross(b - a, c - a)
    normalize_v3(direction[None, :])
    return direction

def generate_roads(models, terrain, map, json_out):
    numroads = 0
    for center in progress.bar(map.centers.values(), label='Generating roads... '):
        road_edges = [e for e in center.edges if e.is_road and e.corner0 is not None and e.corner1 is not None]
        if len(road_edges) != 2:
            continue
        
        e1, e2 = road_edges
        e1_0 = numpy.array([e1.corner0.x, e1.corner0.y, e1.corner0.elevation * Z_SCALE], dtype=numpy.float32)
        e1_1 = numpy.array([e1.corner1.x, e1.corner1.y, e1.corner1.elevation * Z_SCALE], dtype=numpy.float32)
        e2_0 = numpy.array([e2.corner0.x, e2.corner0.y, e2.corner0.elevation * Z_SCALE], dtype=numpy.float32)
        e2_1 = numpy.array([e2.corner1.x, e2.corner1.y, e2.corner1.elevation * Z_SCALE], dtype=numpy.float32)
        
        region_center = numpy.array([center.x, center.y, center.elevation * Z_SCALE])
        
        for end1, edge1, edge2 in [(region_center, e1_0, e1_1), (region_center, e2_0, e2_1)]:
            end2 = v3mid(edge1, edge2)
            
            midpt = v3mid(end1, end2)
            midpt = scene.mapgen_coords_to_sirikata(midpt, terrain)
            
            kata_pt1 = scene.mapgen_coords_to_sirikata(end1, terrain)
            kata_pt2 = scene.mapgen_coords_to_sirikata(end2, terrain)
            
            scale = v3dist(kata_pt1, kata_pt2) / 2
            
            m = scene.SceneModel(ROAD_PATH,
                           x=float(midpt[0]),
                           y=float(midpt[1]),
                           z=float(midpt[2]),
                           scale=scale,
                           model_type='road')
            
            kataboundmin, kataboundmax = scene.sirikata_bounds(m.boundsInfo)
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
            
            orig_up = q.getUp()
            orig_up.normalize()
            
            edge1_kata = scene.mapgen_coords_to_sirikata(edge1, terrain)
            edge2_kata = scene.mapgen_coords_to_sirikata(edge2, terrain)
            new_up = normal_vector(kata_pt1, edge1_kata, edge2_kata)
            new_up = Vec3(new_up[0], new_up[1], new_up[2])
            rotate_about = orig_up.cross(new_up)
            rotate_about.normalize()
            angle_between = orig_up.angleDeg(new_up)
            r = Quat()
            r.setFromAxisAngle(angle_between, rotate_about)
            r.normalize()
            q *= r
            q.normalize()
            
            m.orient_x = q.getI()
            m.orient_y = q.getJ()
            m.orient_z = q.getK()
            m.orient_w = q.getR()
            
            numroads += 1
            json_out.append(m.to_json())
    
    print 'Generated (%d) road objects' % numroads

def generate_flying(models, terrain, map, json_out):
    terrain_bounds = scene.sirikata_bounds(terrain.boundsInfo)
    minpt, maxpt = terrain_bounds
    minpt *= terrain.scale
    maxpt *= terrain.scale
    height_max = (maxpt[2] - minpt[2]) * 1.20
    
    flying_models = models['flying']
    centers = map.centers.values()
    random.shuffle(centers)
    centers = centers[:len(flying_models)]
    for center, flying_model in progress.bar(zip(centers, flying_models), label='Generating flying objects... '):
        center_pt = numpy.array([center.x, center.y, center.elevation * Z_SCALE], dtype=numpy.float32)
        center_pt = scene.mapgen_coords_to_sirikata(center_pt, terrain)

        rand_height = random.uniform(center_pt[2], height_max) * 1.10
        
        m = scene.SceneModel(flying_model['full_path'],
                       x=float(center_pt[0]),
                       y=float(center_pt[1]),
                       z=rand_height,
                       scale=random.uniform(1.0, 8.0),
                       model_type='flying')
        json_out.append(m.to_json())
    print 'Generated (%d) flying objects' % len(flying_models)

def generate_boats(models, terrain, map, json_out):
    boats = models['boats']
    oceans = [c for c in map.centers.values() if c.biome == 'OCEAN']
    lakes = [c for c in map.centers.values() if c.biome == 'LAKE']
    random.shuffle(lakes)
    random.shuffle(oceans)
    
    lakes = lakes[:len(boats)]
    oceans = oceans[:len(boats)*2]
    centers = oceans + lakes
    boats = boats + boats + boats
    
    for center, boat_model in progress.bar(zip(centers, boats), label='Generating boats...'):
        center_pt = numpy.array([center.x, center.y, center.elevation * Z_SCALE], dtype=numpy.float32)
        center_pt = scene.mapgen_coords_to_sirikata(center_pt, terrain)
        scale = random.uniform(5.0, 15.0)
        
        m = scene.SceneModel(boat_model['full_path'],
                       x=float(center_pt[0]),
                       y=float(center_pt[1]),
                       z=float(center_pt[2]) - scale * 2 * 0.05,
                       scale=scale,
                       model_type='boat')
        
        json_out.append(m.to_json())
    
    print 'Generated (%d) boat objects' % len(boats)

def generate_winter(models, terrain, map, json_out):
    winter = models['winter']
    snow = [c for c in map.centers.values() if c.biome == 'SNOW']
    random.shuffle(snow)
    
    winter = winter + winter
    snow = snow[:len(winter)]
    
    for center, winter_model in progress.bar(zip(snow, winter), label='Generating winter objects...'):
        center_pt = numpy.array([center.x, center.y, center.elevation * Z_SCALE], dtype=numpy.float32)
        center_pt = scene.mapgen_coords_to_sirikata(center_pt, terrain)
        scale = random.uniform(3.0, 10.0)
        
        m = scene.SceneModel(winter_model['full_path'],
                       x=float(center_pt[0]),
                       y=float(center_pt[1]),
                       z=float(center_pt[2]),
                       scale=scale,
                       model_type='winter')
        
        json_out.append(m.to_json())
    
    print 'Generated (%d) winter objects' % len(winter)

def generate_vehicles(models, terrain, map, json_out):
    vehicles = models['vehicles']
    vehicles = vehicles + vehicles
    roads = [j for j in json_out if j['type'] == 'road']
    random.shuffle(roads)
    roads = roads[:len(vehicles)]
    
    for road, vehicle_model in progress.bar(zip(roads, vehicles), label='Generating vehicles...'):
        road_pt = numpy.array([road['x'], -1 * road['z'], road['y']], dtype=numpy.float32)
        
        scale = random.uniform(1.0, 3.0)
        
        m = scene.SceneModel(vehicle_model['full_path'],
                       x=float(road_pt[0]),
                       y=float(road_pt[1]),
                       z=float(road_pt[2]),
                       scale=scale,
                       model_type='vehicle',
                       orient_x=road['orient_x'],
                       orient_y=-1 * road['orient_z'],
                       orient_z=road['orient_y'],
                       orient_w=road['orient_w'])
        
        json_out.append(m.to_json())
        
    print 'Generated (%d) vehicles' % len(vehicles)

def plane_from_points(v1, v2, v3):
    """Computes the best fit plane through a set of points.
    
    Returns
      (n, d) where n in the normal of the plane, d is the scalar offset
    """
    
    vec1 = v1 - v2
    vec2 = v1 - v3
    norm = numpy.cross(vec1, vec2)
    d = numpy.dot(norm, v3)
    return (norm, d)

def iterate_poisson_samples(centers, map, name, radius, num_samples):
    for center in progress.bar(centers, label='Generating %s...' % name):
        
        tris = []
        for edge in center.edges:
            corner0 = edge.corner0
            corner1 = edge.corner1
            center0 = edge.center0
            center1 = edge.center1
            if corner0 is None or corner1 is None:
                continue
            
            if center.id == center0.id:
                v1 = map.corners[corner1.id]
                v2 = map.corners[corner0.id]
                v3 = map.centers[center0.id]
            elif center.id == center1.id:
                v1 = map.centers[center1.id]
                v2 = map.corners[corner0.id]
                v3 = map.corners[corner1.id]
            else:
                continue
            
            tris.append((v1, v2, v3))
            
        for tri in tris:
            minx = min([v.x for v in tri])
            miny = min([v.y for v in tri])
            maxx = max([v.x for v in tri])
            maxy = max([v.y for v in tri])
            width = int(maxx - minx)
            height = int(maxy - miny)
            
            samples = poisson_disk.sample_poisson_uniform(width, height, radius, num_samples)
            samples = [(x+minx, y+miny) for x,y in samples]

            random.shuffle(samples)
            samples = samples[:num_samples]
            
            pts = numpy.array([(v.x, v.y, v.elevation * Z_SCALE) for v in tri], dtype=numpy.float32)
            n, d = plane_from_points(*pts)
            a, b, c = n
            for x,y in samples:
                # ax + by + cz = d
                # z = (d - ax - by)/c
                z = (d - a*x - b*y) / c
                
                yield (x, y, z)

def generate_forest(centers, models, terrain, map, json_out, name, radius, num_samples):
    trees = models['trees']
    
    # for testing
    # trees = [t for t in trees if 'jterrace/palm.dae' in t['full_path']]
    # assert len(trees) == 1

    num_gen = 0 
    for x, y, z in iterate_poisson_samples(centers, map, name, radius, num_samples):
        pt = numpy.array([x,y,z], dtype=numpy.float32)
        pt = scene.mapgen_coords_to_sirikata(pt, terrain)
        
        scale = random.uniform(3.0, 10.0)
        
        m = scene.SceneModel(random.choice(trees)['full_path'],
                       x=float(pt[0]),
                       y=float(pt[1]),
                       z=float(pt[2]),
                       scale=scale,
                       model_type='tree')
        
        json_out.append(m.to_json())
        num_gen += 1
                
    print 'Generated (%d) %s' % (num_gen, name)

def generate_dense_forest(centers, models, terrain, map, json_out):
    generate_forest(centers, models, terrain, map, json_out, 'Dense Forest', 2, 6)

def generate_sparse_forest(centers, models, terrain, map, json_out):
    generate_forest(centers, models, terrain, map, json_out, 'Sparse Forest', 10, 1)

def overlaps(bounds1, bounds2):
    MAX = 1
    MIN = 0
    X = 0
    Y = 1
    Z = 2
    
    if bounds1[MAX][X] < bounds2[MIN][X]:
        return False
    if bounds1[MAX][Y] < bounds2[MIN][Y]:
        return False
    if bounds1[MAX][Z] < bounds2[MIN][Z]:
        return False
    
    if bounds1[MIN][X] > bounds2[MAX][X]:
        return False
    if bounds1[MIN][Y] > bounds2[MAX][Y]:
        return False
    if bounds1[MIN][Z] > bounds2[MAX][Z]:
        return False
    
    return True

def remove_overlapping(models):
    keep_models = []
    for i in progress.bar(range(len(models)), label='Removing Overlapping...'):
        m1 = models.pop()
        overlapping = False
        
        for m2 in models:
            
            minpt1, maxpt1 = scene.sirikata_bounds(m1.boundsInfo)
            minpt1 *= m1.scale
            minpt1 += numpy.array([m1.x, m1.y, m1.z], dtype=numpy.float32)
            maxpt1 *= m1.scale
            maxpt1 += numpy.array([m1.x, m1.y, m1.z], dtype=numpy.float32)
            
            minpt2, maxpt2 = scene.sirikata_bounds(m2.boundsInfo)
            minpt2 *= m2.scale
            minpt2 += numpy.array([m2.x, m2.y, m2.z], dtype=numpy.float32)
            maxpt2 *= m2.scale
            maxpt2 += numpy.array([m2.x, m2.y, m2.z], dtype=numpy.float32)
            
            overlapping = overlapping or overlaps((minpt1, maxpt1), (minpt2, maxpt2))
            
        if not overlapping:
            keep_models.append(m1)
            
    return keep_models

def generate_residential_zone(centers, models, terrain, map, json_out):
    houses = models['houses']
    
    # for testing
    # houses = [h for h in houses if 'kittyvision/house11.dae' in h['full_path']]
    # assert len(houses) == 1
    
    num_gen = 0
    models = []
    for x, y, z in iterate_poisson_samples(centers, map, 'Residential Buildings', 15, 1):
        pt = numpy.array([x,y,z], dtype=numpy.float32)
        pt = scene.mapgen_coords_to_sirikata(pt, terrain)
        
        scale = random.uniform(4.0, 8.0)
        
        m = scene.SceneModel(random.choice(houses)['full_path'],
                       x=float(pt[0]),
                       y=float(pt[1]),
                       z=float(pt[2]),
                       scale=scale,
                       model_type='house')
        models.append(m)
    
    models = remove_overlapping(models)
    for m in models:            
        json_out.append(m.to_json())
        num_gen += 1
                
    print 'Generated (%d) Residential Buildings' % num_gen

def generate_commercial_zone(centers, models, terrain, map, json_out):
    commercial = models['commercial_buildings']
    
    # for testing
    # commercial = [c for c in commercial if 'emily2e/models/cityimport.dae' in c['full_path']]
    # assert len(commercial) == 1
    
    num_gen = 0
    models = []
    for x, y, z in iterate_poisson_samples(centers, map, 'Commercial Buildings', 20, 2):
        pt = numpy.array([x,y,z], dtype=numpy.float32)
        pt = scene.mapgen_coords_to_sirikata(pt, terrain)
        
        scale = random.uniform(6.0, 10.0)
        
        m = scene.SceneModel(random.choice(commercial)['full_path'],
                       x=float(pt[0]),
                       y=float(pt[1]),
                       z=float(pt[2]),
                       scale=scale,
                       model_type='commercial')
        models.append(m)
    
    models = remove_overlapping(models)
    for m in models:            
        json_out.append(m.to_json())
        num_gen += 1
                
    print 'Generated (%d) Commercial Buildings' % num_gen

def generate_houses_and_trees(models, terrain, map, json_out):
    USABLE_BIOMES = {'SHRUBLAND', 'TEMPERATE_RAIN_FOREST', 'TEMPERATE_DECIDUOUS_FOREST',
     'GRASSLAND', 'TROPICAL_RAIN_FOREST','TROPICAL_SEASONAL_FOREST'}
    centers = []
    for c in map.centers.itervalues():
        if c.biome not in USABLE_BIOMES:
            continue
        road_edges = [e for e in c.edges if e.is_road and e.corner0 is not None and e.corner1 is not None]
        if len(road_edges) == 2:
            continue
        centers.append(c)
    
    random.shuffle(centers)
    
    start_offset = 0
    end_offset = 0
    
    start_offset = end_offset
    end_offset += int(len(centers) * 0.1)
    generate_sparse_forest(centers[start_offset:end_offset], models, terrain, map, json_out)
    
    start_offset = end_offset
    end_offset += int(len(centers) * 0.1)
    generate_dense_forest(centers[start_offset:end_offset], models, terrain, map, json_out)
    
    start_offset = end_offset
    end_offset += int(len(centers) * 0.1)
    generate_residential_zone(centers[start_offset:end_offset], models, terrain, map, json_out)
    
    start_offset = end_offset
    end_offset += int(len(centers) * 0.1)
    generate_commercial_zone(centers[start_offset:end_offset], models, terrain, map, json_out)
    
    
def main():
    parser = OptionParser(usage="Usage: generate-scene.py -o scene map.xml",
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
    models = get_models()
    
    terrain = scene.SceneModel(TERRAIN_PATH, x=0, y=0, z=0, scale=1000, model_type='terrain')
    json_out = []
    print 'Generated (1) terrain object'
    json_out.append(terrain.to_json())
    
    generate_houses_and_trees(models, terrain, map, json_out)
    generate_winter(models, terrain, map, json_out)
    generate_roads(models, terrain, map, json_out)
    generate_vehicles(models, terrain, map, json_out)
    generate_flying(models, terrain, map, json_out)
    generate_boats(models, terrain, map, json_out)
    
    json_str = json.dumps(json_out, indent=2)
    
    json_name = options.outname + '.json'
    with open(json_name, 'w') as f:
        f.write(json_str)
    
    em_name = options.outname + '.em'
    with open(em_name, 'w') as f:
        f.write('var OBJECTS = ')
        f.write(json_str)
        f.write(';\n')

if __name__ == '__main__':
    main()
