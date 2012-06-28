#!/usr/bin/env python

import os
import json
from optparse import OptionParser

def main():
    parser = OptionParser(usage="Usage: renderscene.py scene.json",
                          description="Renders a JSON scene file")
    (options, args) = parser.parse_args()
    
    if len(args) != 1:
        parser.print_help()
        parser.exit(1, "Wrong number of arguments.\n")
    
    if not os.path.isfile(args[0]):
        parser.print_help()
        parser.exit(1, "Input file '%s' is not a valid file.\n" % args[0])
        
    fname = args[0]
    json_data = json.load(open(fname))
    print json_data

if __name__ == '__main__':
    main()
