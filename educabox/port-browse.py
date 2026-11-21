"""Export the SmartTube Android browse section descriptors for the Linux port."""
import json
import re
import sys
from pathlib import Path

source, destination = map(Path, sys.argv[1:])
sections = {}
pattern = (
    r'new BrowseSection\(MediaGroup\.TYPE_(\w+), getContext\(\)\.getString'
    r'\(R\.string\.(\w+)\), BrowseSection\.TYPE_(ROW|GRID), R\.drawable\.(\w+)'
)
for section, title, layout, icon in re.findall(pattern, source.read_text()):
    sections[section] = {'title': title, 'layout': layout, 'icon': icon}
supported = ('HOME', 'TRENDING', 'MUSIC', 'GAMING', 'SPORTS', 'NEWS', 'SUBSCRIPTIONS', 'HISTORY')
destination.write_text(json.dumps({name: sections[name] for name in supported}, indent=2))
