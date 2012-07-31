import json
import posixpath
from StringIO import StringIO
import gzip
import tempfile
import math
import os
import requests
import pickle
import time
import urlparse

import numpy
import collada
from meshtool.filters.panda_filters import pandacore
from meshtool.filters.panda_filters import pdae_utils
from meshtool.filters.simplify_filters import add_back_pm
from panda3d.core import GeomNode, NodePath, Mat4

BASE_URL = 'http://open3dhub.com'
# 'http://singular.stanford.edu'
BROWSE_URL = BASE_URL + '/api/browse'
DOWNLOAD_URL = BASE_URL + '/download'
DNS_URL = BASE_URL + '/dns'
MODELINFO_URL = BASE_URL + '/api/modelinfo/%(path)s'
SEARCH_URL = BASE_URL + '/api/search?q=%(q)s&start=%(start)d&rows=%(rows)d'

PANDA3D = False

PROGRESSIVE_CHUNK_SIZE = 2 * 1024 * 1024 # 2 MB

# blacklist some models that are TOO BIG and make cassandra die because thrift doesn't support streaming
BLACKLIST = set(['/kittyvision/tree/straight.dae/0',
                 '/kittyvision/tree/willow.dae/0',
                 '/kittyvision/tree/leaning.dae/0',
                 '/kittyvision/tree/leafy.dae/0',
                 '/kittyvision/tree/jaccaranda.dae/0',
                 '/kittyvision/tree/densemaple.dae/0',
                 '/kittyvision/tree/mango.dae/0'])

CURDIR = os.path.dirname(__file__)
TEMPDIR = os.path.join(CURDIR, '.temp_models')

REQUESTS_SESSION = requests.session()

class PathInfo(object):
    """Helper class for dealing with CDN paths"""
    def __init__(self, filename):
        self.filename = filename
        self.normpath = posixpath.normpath(filename)
        """Normalized original path"""
        
        split = self.normpath.split("/")
        try:
            self.version = str(int(split[-1]))
            """Version number of the path"""
        except ValueError:
            self.version = None
    
        if self.version is None:
            self.basename = split[-1]
            """The filename of the path"""
            self.basepath = self.normpath
            """The base of the path, without the version number"""
        else:
            self.basename = split[-2]
            self.basepath = '/'.join(split[:-1])
            
    @staticmethod
    def fromurl(url):
        parsed = urlparse.urlparse(url)
        return PathInfo(parsed.path)
            
    def __str__(self):
        return "<PathInfo filename='%s', normpath='%s', basepath='%s', basename='%s', version='%s'>" % \
                (self.filename, self.normpath, self.basepath, self.basename, self.version)
    
    def __repr__(self):
        return str(self)

def urlfetch(url, httprange=None):
    """Fetches the given URL and returns data from it.
    Will take care of gzip if enabled on server."""
    
    headers = {}
    if httprange is not None:
        offset, length = httprange
        headers['Range'] = 'bytes=%d-%d' % (offset, offset+length-1)
    
    resp = REQUESTS_SESSION.get(url, headers=headers)
    
    return resp.content
    
def json_fetch(url):
    return json.loads(urlfetch(url))

def hashfetch(dlhash, httprange=None):
    """Fetches the given hash and returns data from it."""
    return urlfetch(DOWNLOAD_URL + '/' + dlhash, httprange)

def get_subfile_hash(subfile_path):
    subfile_url = DNS_URL + subfile_path
    subfile_json = json.loads(urlfetch(subfile_url))
    subfile_hash = subfile_json['Hash']
    return subfile_hash

def get_search_list(q):
    start = 0
    
    all_items = []
    while start is not None:
        to_search = SEARCH_URL % {'q': q,
                                  'start': start,
                                  'rows': 100}
        response = json_fetch(to_search)
        
        for item in response['content_items']:
            if item['full_path'] in BLACKLIST:
                continue
            all_items.append(item)
        
        try:
            start = int(response['next_start'])
        except (ValueError, TypeError):
            start = None
    
    return all_items

def get_list(limit=20):
    """Returns a list of dictionaries containing model JSON"""
    
    next_start = ''
    all_items = []
    unique_models = set()

    while len(all_items) < limit and next_start != None:
        print 'got', len(all_items), 'so far'
        
        models_js = json.loads(urlfetch(BROWSE_URL + '/' + next_start))
        next_start = models_js['next_start']
        
        models_js = models_js['content_items']
        
        for model_js in models_js:
            
            progressive = model_js['metadata']['types'].get('progressive')
            if progressive is not None and 'mipmaps' in progressive:
                for mipmap_name, mipmap_data in progressive['mipmaps'].iteritems():
                    old_byte_ranges = mipmap_data['byte_ranges']
                    new_byte_ranges = []
                    offset = 0
                    for byte_data in old_byte_ranges:
                        offset += 512
                        new_byte_data = dict(byte_data)
                        if offset != new_byte_data['offset']:
                            new_byte_data['offset'] = offset
                        file_len = new_byte_data['length']
                        file_len = 512 * ((file_len + 512 - 1) / 512)
                        offset += file_len
                        new_byte_ranges.append(new_byte_data)
                    model_js['metadata']['types']['progressive']['mipmaps'][mipmap_name]['byte_ranges'] = new_byte_ranges
            
            if model_js['full_path'] in unique_models:
                print 'OMG< FOUND A DUPLICATE', model_js['full_path']
            else:
                unique_models.add(model_js['full_path'])
                all_items.append(model_js)
        
    if len(all_items) > limit:
        all_items = all_items[0:limit]
        
    return all_items

def get_hash_sizes(items):

    hash_keys = ['zip', 'screenshot', 'hash', 'thumbnail',
                 'progressive_stream', 'panda3d_base_bam',
                 'panda3d_full_bam', 'panda3d_bam',
                 'subfile_hashes']
       
    unique_keys = set()
    for item in items:
        
        for type_name, type_data in item['metadata']['types'].iteritems():
        
            for hash_key in hash_keys:
                hash_key_val = type_data.get(hash_key)
                if hash_key_val is not None:
                    if isinstance(hash_key_val, basestring):
                        unique_keys.add(type_data[hash_key])
                    else:
                        unique_keys.update(type_data[hash_key])
                    
            #progressive mipmaps are nested
            if 'mipmaps' in type_data:
                for mipmap_data in type_data['mipmaps'].itervalues():
                    unique_keys.add(mipmap_data['hash'])
    
    cache_file = os.path.join(CURDIR, 'hash-size-cache.pickle')
    hash_cache = {}
    if os.path.isfile(cache_file):
        hash_cache = pickle.load(open(cache_file, 'rb'))
        
    hash_sizes = {}
    for hash in unique_keys:
        if hash in hash_cache:
            hash_sizes[hash] = hash_cache[hash]
        else:
            resp = REQUESTS_SESSION.get(DOWNLOAD_URL + '/' + hash)
            hash_sizes[hash] = {'size': len(resp.content),
                                'gzip_size': int(resp.headers['content-length'])}
            hash_cache[hash] = hash_sizes[hash]
    
    pickle.dump(hash_cache, open(cache_file, 'wb'))
    
    return hash_sizes

def load_mesh(mesh_data, subfiles):
    """Given a downloaded mesh, return a collada instance"""
    
    def inline_loader(filename):
        return subfiles[posixpath.basename(filename)]
    
    mesh = collada.Collada(StringIO(mesh_data), aux_file_loader=inline_loader)
    
    #this will force loading of the textures too
    for img in mesh.images:
        img.data
    
    return mesh

def get_single_metadata(path):
    pathinfo = PathInfo(path)
    metadata = json_fetch(MODELINFO_URL % {'path': pathinfo.normpath})
    return metadata

_mesh_cache = {}
def _make_aux_file_loader(metadata):

    typedata = metadata['metadata']['types']['optimized']
    subfile_map = {}
    for subfile in typedata['subfiles']:
        base_name = posixpath.basename(posixpath.split(subfile)[0])
        subfile_map[base_name] = subfile

    def aux_file_loader(fname):
        base = posixpath.basename(fname)
        if base not in subfile_map:
            return None
        path = subfile_map[base]
        subhash = get_subfile_hash(path)
        data = hashfetch(subhash)
        return data

    return aux_file_loader

def path_to_mesh(path, cache=False):
    if path not in _mesh_cache:
        metadata = get_single_metadata(path)
        typedata = metadata['metadata']['types']['optimized']
        mesh_hash = typedata['hash']
        mesh_data = hashfetch(mesh_hash)
        mesh = collada.Collada(StringIO(mesh_data), aux_file_loader=_make_aux_file_loader(metadata))
        if not cache:
            return (metadata, mesh)
        _mesh_cache[path] = (metadata, mesh)
    return _mesh_cache[path]

def load_into_bamfile(meshdata, subfiles, model):
    """Uses pycollada and panda3d to load meshdata and subfiles and
    write out to a bam file on disk"""

    if os.path.isfile(model.bam_file):
        print 'returning cached bam file'
        return model.bam_file

    mesh = load_mesh(meshdata, subfiles)
    model_name = model.model_json['full_path'].replace('/', '_')
    
    if model.model_type == 'progressive' and model.model_subtype == 'full':
        progressive_stream = model.model_json['metadata']['types']['progressive'].get('progressive_stream')
        if progressive_stream is not None:
            print 'LOADING PROGRESSIVE STREAM'
            data = model.prog_data
            try:
                mesh = add_back_pm.add_back_pm(mesh, StringIO(data), 100)
                print '-----'
                print 'SUCCESSFULLY ADDED BACK PM'
                print '-----'
            except:
                f = open(model.bam_file, 'w')
                f.close()
                raise

    print 'loading into bamfile', model_name, mesh
    scene_members = pandacore.getSceneMembers(mesh)
    print 'got scene members', model_name, mesh
    
    rotateNode = GeomNode("rotater")
    rotatePath = NodePath(rotateNode)
    matrix = numpy.identity(4)
    if mesh.assetInfo.upaxis == collada.asset.UP_AXIS.X_UP:
        r = collada.scene.RotateTransform(0,1,0,90)
        matrix = r.matrix
    elif mesh.assetInfo.upaxis == collada.asset.UP_AXIS.Y_UP:
        r = collada.scene.RotateTransform(1,0,0,90)
        matrix = r.matrix
    rotatePath.setMat(Mat4(*matrix.T.flatten().tolist()))

    for geom, renderstate, mat4 in scene_members:
        node = GeomNode("primitive")
        node.addGeom(geom)
        if renderstate is not None:
            node.setGeomState(0, renderstate)
        geomPath = rotatePath.attachNewNode(node)
        geomPath.setMat(mat4)
        
    print 'created np', model_name, mesh

    if model.model_type != 'optimized_unflattened' and model.model_type != 'progressive':
        print 'ABOUT TO FLATTEN'
        rotatePath.flattenStrong()
        print 'DONE FLATTENING'
        
    print 'flattened', model_name, mesh
    
    wrappedNode = pandacore.centerAndScale(rotatePath)
    wrappedNode.setName(model_name)

    wrappedNode.writeBamFile(model.bam_file)
    print 'saved', model_name, mesh
    wrappedNode = None
    
    return model.bam_file
