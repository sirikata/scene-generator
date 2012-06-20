#!/usr/bin/env python

import os
from mapgen2 import MapGenXml
from optparse import OptionParser

def main():
    parser = OptionParser(usage="Usage: generate-scene.py -o scene.json map.xml",
                          description="Generates a JSON scene based on mapgen2 XML output, using meshes from open3dhub")
    parser.add_option("-o", "--outfile", dest="outfile",
                      help="write JSON scene to FILE", metavar="OUTFILE")
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
    #dae = tocollada(map.centers, map.corners, map.edges)
    #dae.write(options.outfile)

if __name__ == '__main__':
    main()
