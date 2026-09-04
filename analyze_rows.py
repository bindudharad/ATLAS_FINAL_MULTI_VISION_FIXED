import json
from collections import defaultdict

with open('debug/mpf/ocr_output.json', 'r') as f:
    data = json.load(f)

rows = defaultdict(list)
for line in data['lines']:
    y = line['bbox']['y']
    key = round(y / 20) * 20
    rows[key].append(line)

for y, items in sorted(rows.items()):
    if len(items) > 1:
        items.sort(key=lambda x: x['bbox']['x'])
        print(f'Row y~{y}:')
        for item in items:
            print(f'  x={item[\
bbox\][\x\]:4d} text=\
item[\"text\"]
\ conf={item[\confidence\]:.2f}')
        print()
