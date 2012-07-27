import numpy

import cache
import open3dhub

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

class SceneModel(object):
    def __init__(self, path, x, y, z, scale, model_type,
                 orient_x=0, orient_y=0, orient_z=0, orient_w=1):
        self.path = path
        
        self.x = x
        self.y = y
        self.z = z
        
        self.scale = scale
        self.model_type = model_type
        
        self.orient_x = orient_x
        self.orient_y = orient_y
        self.orient_z = orient_z
        self.orient_w = orient_w
        
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
        if self._metadata is None:
            self._metadata = cache.get_metadata(self.path)
        return self._metadata

    metadata = property(_get_metadata)
    
    def _get_bounds_info(self):
        if self._boundsInfo is None:
            self._boundsInfo = cache.get_bounds(self.path)
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
            'type': self.model_type,
        }

    def __str__(self):
        return '<SceneModel %s <%.7g,%.7g,%.7g> %.7g>' % \
                    (self.path, self.x, self.y, self.z, self.scale)
    def __repr__(self):
        return str(self)

    @staticmethod
    def from_json(j):
        m = SceneModel(j['path'],
                       j['x'],
                       -1.0 * j['z'],
                       j['y'],
                       j['scale'],
                       j['type'],
                       orient_x=j['orient_x'],
                       orient_y=-1.0 * j['orient_z'],
                       orient_z=j['orient_y'],
                       orient_w=j['orient_w'])
        
        return m
