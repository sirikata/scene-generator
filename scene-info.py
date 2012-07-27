#!/usr/bin/env python

import os
import sys
import json
import locale
import math
from optparse import OptionParser
from clint.textui import indent, puts, puts_err

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
    parser = OptionParser(usage="Usage: scene-info.py [--missing-to file.txt] scene.json",
                          description="Prints information about a JSON scene file.")
    parser.add_option("-m", "--missing-to", dest="missing_to",
                          help="Write a list of paths missing progressive info to file", metavar="MISSING_TO")
    (options, args) = parser.parse_args()
    
    if len(args) != 1:
        parser.print_help()
        parser.exit(1, "Wrong number of arguments.\n")
    
    if not os.path.isfile(args[0]):
        parser.print_help()
        parser.exit(1, "Input file '%s' is not a valid file.\n" % args[0])
    
    missing_to = None
    if options.missing_to is not None:
        missing_to = open(options.missing_to, 'w')
    
    fname = args[0]
    json_data = json.load(open(fname))
    
    total_triangles = 0
    total_draw_calls = 0
    total_ram_cache = {}
    
    total_base_tris = 0
    base_ram_cache = {}
    total_base_draw_calls = 0
    
    total_full_tris = 0
    full_ram_cache = {}
    total_full_draw_calls = 0
    
    missing_progressive = set()
    missing_metadata = set()
    too_big = set()
    
    
    for m in json_data:
        metadata = cache.get_metadata(m['path'])
        
        if 'progressive' not in metadata['metadata']['types']:
            missing_progressive.add(m['path'])
        else:
            progressive = metadata['metadata']['types']['progressive']
            if 'metadata' not in progressive:
                missing_metadata.add(m['path'])
            else:
                total_base_tris += min(progressive['metadata']['num_triangles'], 40000)
                total_full_tris += progressive['metadata']['num_triangles'] + progressive['progressive_stream_num_triangles']
                
                if progressive['metadata']['num_triangles'] > 40000:
                    too_big.add(m['path'])
                
                for mapname, mapinfo in progressive['mipmaps'].iteritems():
                    byte_ranges = mapinfo['byte_ranges']
                    for levelinfo in byte_ranges:
                        width, height = levelinfo['width'], levelinfo['height']
                        if width >= 128 or height >= 128:
                            ram_size = width * height * 4
                            break
                    base_ram_cache[m['path']] = ram_size
                    
                    if len(byte_ranges) > 0:
                        full_res = byte_ranges[-1]
                        width, height = full_res['width'], full_res['height']
                        full_ram_cache[m['path']] = width * height * 4
                
                total_base_draw_calls += progressive['metadata']['num_draw_calls']
                total_full_draw_calls += progressive['metadata']['num_draw_calls']
        
        optimized = metadata['metadata']['types']['optimized']
        total_triangles += optimized['metadata']['num_triangles']
        total_ram_cache[m['path']] = optimized['metadata']['texture_ram_usage']
        total_draw_calls += optimized['metadata']['num_draw_calls']
    
    total_ram = sum(total_ram_cache.values())
    total_base_ram = sum(base_ram_cache.values())
    total_full_ram = sum(full_ram_cache.values())
    
    for m in missing_progressive:
        if missing_to is not None:
            puts_err(m, stream=missing_to.write)
        else:
            puts_err('Warning: missing progressive version for: "%s"' % m)
    if missing_to is None and len(missing_progressive) > 0:
        puts()
    
    for m in too_big:
        metadata = cache.get_metadata(m)
        puts_err("Warning '%s' too big at %s triangles" % (m, pretty(metadata['metadata']['types']['progressive']['metadata']['num_triangles'])))
    if len(too_big) > 0:
        puts()
    
    for m in missing_metadata:
        puts_err("Warning '%s' missing metadata" % m)
    if len(missing_metadata) > 0:
        puts()
    
    puts('Number of models in the scene: %s' % pretty(len(json_data)))
    puts('Number of unique models in the scene: %s' % pretty(len(set(m['path'] for m in json_data))))
    puts()
    
    puts("Type 'optimized'")
    with indent(4):
        puts('Triangles: %s' % pretty(total_triangles))
        puts('Texture RAM: %s' % humanize_bytes(total_ram))
        puts('Draw Calls: %s' % pretty(total_draw_calls))
        
    puts()
    puts("Type 'progressive' base mesh")
    with indent(4):
        puts('Triangles: %s' % pretty(total_base_tris))
        puts('Texture RAM: %s' % humanize_bytes(total_base_ram))
        puts('Draw Calls: %s' % pretty(total_base_draw_calls))
        
    puts()
    puts("Type 'progressive' full quality")
    with indent(4):
        puts('Triangles: %s' % pretty(total_full_tris))
        puts('Texture RAM: %s' % humanize_bytes(total_full_ram))
        puts('Draw Calls: %s' % pretty(total_full_draw_calls))

if __name__ == '__main__':
    main()
