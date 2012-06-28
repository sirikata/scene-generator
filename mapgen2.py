"""Routines for handling mapgen2 XML files"""

import sys
from xml.etree import ElementTree as etree

X_SCALE = 1.0
Y_SCALE = 1.0
Z_SCALE = 100.0

COLORS = {
    # Features
    'OCEAN': 0x44447a,
    'COAST': 0x33335a,
    'LAKESHORE': 0x225588,
    'LAKE': 0x336699,
    'RIVER': 0x225588,
    'MARSH': 0x2f6666,
    'ICE': 0x99ffff,
    'BEACH': 0xa09077,
    'ROAD1': 0x442211,
    'ROAD2': 0x553322,
    'ROAD3': 0x664433,
    'BRIDGE': 0x686860,
    'LAVA': 0xcc3333,
    
    # Terrain
    'SNOW': 0xffffff,
    'TUNDRA': 0xbbbbaa,
    'BARE': 0x888888,
    'SCORCHED': 0x555555,
    'TAIGA': 0x99aa77,
    'SHRUBLAND': 0x889977,
    'TEMPERATE_DESERT': 0xc9d29b,
    'TEMPERATE_RAIN_FOREST': 0x448855,
    'TEMPERATE_DECIDUOUS_FOREST': 0x679459,
    'GRASSLAND': 0x88aa55,
    'SUBTROPICAL_DESERT': 0xd2b98b,
    'TROPICAL_RAIN_FOREST': 0x337755,
    'TROPICAL_SEASONAL_FOREST': 0x559944
}

def hex2rgb(i):
    b = i & 255
    g = (i >> 8) & 255
    r = (i >> 16) & 255
    return (r / 255.0, g / 255.0, b / 255.0)

class MapObject(object):
    def __init__(self, elem):
        self.elem = elem
        
        for prop in self.PROPS:
            setattr(self, prop, elem.get(prop))
            
        for prop in self.NUMERICS:
            setattr(self, prop, float(getattr(self, prop)))
            
        for prop in self.BOOLEANS:
            setattr(self, prop, True if getattr(self, prop) == 'true' else False)

class Center(MapObject):
    PROPS = ['biome', 'elevation', 'coast', 'water', 'moisture', 'y', 'x', 'ocean', 'border', 'id']
    NUMERICS = ['x', 'y', 'elevation', 'moisture']
    BOOLEANS = ['water', 'coast', 'ocean', 'border']
            
    def add_pointers(self, corners, edges):
        self.corners = []
        for corner_elem in self.elem.findall('corner'):
            corner_id = corner_elem.get('id')
            self.corners.append(corners[corner_id])
            
        self.edges = []
        for edge_elem in self.elem.findall('edge'):
            edge_id = edge_elem.get('id')
            self.edges.append(edges[edge_id])
    
    def __str__(self):
        return "<Center id=%s (%.7g, %.7g, %.7g)>" % (self.id, self.x, self.y, self.elevation)
    def __repr__(self):
        return str(self)

class Corner(MapObject):
    PROPS = ['water', 'elevation', 'coast', 'downslope', 'moisture', 'ocean', 'y', 'x', 'river', 'border', 'id']
    NUMERICS = ['x', 'y', 'elevation', 'moisture', 'downslope', 'river']
    BOOLEANS = ['water', 'coast', 'ocean', 'border']
            
    def __str__(self):
        return "<Corner id=%s (%.7g, %.7g, %.7g)>" % (self.id, self.x, self.y, self.elevation)
    def __repr__(self):
        return str(self)
    
class Edge(object):
    def __init__(self, elem, corners, centers):
        self.elem = elem
        self.is_road = False
        self.road_contour = -1
        
        corner0 = elem.get('corner0')
        corner1 = elem.get('corner1')
        self.corner0 = corners.get(corner0)
        self.corner1 = corners.get(corner1)
        
        center0 = elem.get('center0')
        center1 = elem.get('center1')
        self.center0 = centers.get(center0)
        self.center1 = centers.get(center1)
        
        self.x = elem.get('x')
        self.y = elem.get('y')
        self.x = float(self.x) if self.x is not None else None
        self.y = float(self.y) if self.y is not None else None
        
        self.id = elem.get('id')

class MapGenXml(object):
    def __init__(self, fname):
        e = etree.parse(fname)
        
        generator = e.find("generator")
        self.generated_url = generator.get('url')
        self.time_generated = generator.get('timestamp')
        
        center_elems = e.find("centers")
        self.centers = {}
        for center_elem in center_elems:
            center = Center(center_elem)
            self.centers[center.id] = center
        
        corner_elems = e.find("corners")
        self.corners = {}
        for corner_elem in corner_elems:
            corner = Corner(corner_elem)
            self.corners[corner.id] = corner
            
        edge_elems = e.find("edges")
        self.edges = {}
        for edge_elem in edge_elems:
            edge = Edge(edge_elem, self.corners, self.centers)
            self.edges[edge.id] = edge
            
        road_elems = e.find("roads")
        for road_elem in road_elems:
            edge_id = road_elem.get('edge')
            edge = self.edges[edge_id]
            edge.road_contour = road_elem.get('contour')
            edge.is_road = True
            
        for center in self.centers.itervalues():
            center.add_pointers(self.corners, self.edges)

    def __str__(self):
        return '<MapGenXml with %d centers, %d corners, and %d edges>' % (len(self.centers), len(self.corners), len(self.edges))
    def __repr__(self):
        return str(self)

    def print_info(self):
        sys.stdout.write("Generated map file created on '%s' via URL '%s'.\n" % (self.time_generated, self.generated_url))
        sys.stdout.write("Found %d centers.\n" % len(self.centers))
        sys.stdout.write("Found %d corners.\n" % len(self.corners))
        sys.stdout.write("Found %d edges.\n" % len(self.edges))
        sys.stdout.write("Found %d edges that are roads.\n" % len([e for e in self.edges.itervalues() if e.is_road]))
        