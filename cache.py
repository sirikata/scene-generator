import shelve
from meshtool.filters.print_filters.print_bounds import getBoundsInfo
import open3dhub

CACHE = '.cache'
SHELF = shelve.open(CACHE)

def get_tag(tag):
    tagkey = "TAG_" + str(tag)
    if tagkey not in SHELF:
        SHELF[tagkey] = open3dhub.get_search_list('tags:"%s"' % tag)
    return SHELF[tagkey]

def get_bounds(path):
    pathkey = 'BOUNDS_' + str(path)
    if pathkey not in SHELF:
        metadata, mesh = open3dhub.path_to_mesh(path, cache=True)
        SHELF[pathkey] = getBoundsInfo(mesh)
    
    return SHELF[pathkey]

def get_metadata(path):
    key = 'METADATA_' + str(path)
    if key not in SHELF:
        metadata, mesh = open3dhub.path_to_mesh(path, cache=True)
        SHELF[key] = metadata
    
    return SHELF[key]
