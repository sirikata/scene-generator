scene-generator
===============

Generates 3d scenes using mapgen2 biomes and open3dhub meshes

renderxml.py
============

```
Usage: renderxml.py map.xml

Renders a mapgen2 XML file using Panda3D

Options:
  -h, --help  show this help message and exit
```

map2collada.py
==============

```
Usage: map2collada.py -o file.dae map.xml

Converts mapgen2 XML file to COLLADA using pycollada

Options:
  -h, --help            show this help message and exit
  -o OUTFILE, --outfile=OUTFILE
                        write DAE to FILE
```

generate-scene.py
=================

```
Usage: generate-scene.py -o scene.json map.xml

Generates a JSON scene based on mapgen2 XML output, using meshes from
open3dhub

Options:
  -h, --help            show this help message and exit
  -o OUTFILE, --outfile=OUTFILE
                        write JSON scene to FILE
```
