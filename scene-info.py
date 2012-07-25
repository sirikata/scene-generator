#!/usr/bin/env python

import os
import sys
import json
import locale
import math
from optparse import OptionParser

import cache

locale.setlocale(locale.LC_ALL, '')

def pretty(x):
    return locale.format("%d", x, grouping=True)

def humanize_bytes(bytes, precision=1):
    abbrevs = (
        (1<<50L, 'PB'),
        (1<<40L, 'TB'),
        (1<<30L, 'GB'),
        (1<<20L, 'MB'),
        (1<<10L, 'KB'),
        (1, 'bytes')
    )
    if bytes == 1:
        return '1 byte'
    for factor, suffix in abbrevs:
        if math.fabs(bytes) >= factor:
            break
    return '%.*f %s' % (precision, bytes / factor, suffix)

def main():
    parser = OptionParser(usage="Usage: scene-info.py scene.json",
                          description="Prints information about a JSON scene file.")
    (options, args) = parser.parse_args()
    
    if len(args) != 1:
        parser.print_help()
        parser.exit(1, "Wrong number of arguments.\n")
    
    if not os.path.isfile(args[0]):
        parser.print_help()
        parser.exit(1, "Input file '%s' is not a valid file.\n" % args[0])
        
    fname = args[0]
    json_data = json.load(open(fname))
    
    total_triangles = 0
    total_ram = 0
    total_draw_calls = 0
    missing_progressive = set()
    
    for m in json_data:
        metadata = cache.get_metadata(m['path'])
        
        if 'progressive' not in metadata['metadata']['types']:
            missing_progressive.add(m['path'])
        
        optimized = metadata['metadata']['types']['optimized']
        total_triangles += optimized['metadata']['num_triangles']
        total_ram += optimized['metadata']['texture_ram_usage']
        total_draw_calls += optimized['metadata']['num_draw_calls']
    
    for m in missing_progressive:
        sys.stderr.write('Warning: missing progressive version for: "%s"\n' % m)
    
    print 'Number of models in the scene: %s' % pretty(len(json_data))
    print 'Triangles: %s' % pretty(total_triangles)
    print 'Texture RAM: %s' % humanize_bytes(total_ram)
    print 'Draw Calls: %s' % pretty(total_draw_calls)

if __name__ == '__main__':
    main()
