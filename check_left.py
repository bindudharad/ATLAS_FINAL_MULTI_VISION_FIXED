import json
with open('debug/mpf/field_map.json', 'r') as f:
    data = json.load(f)

# Check which left labels are in source_pool (genuine source labels)
# The _source_label_nodes function should filter out values and wide headers
for l in data.get('left_labels', []):
    nm = l.get('name') or ''
    aid = l.get('automation_id','')
    rc = l.get('rect',{})
    w = rc.get('width')
    print(f'{aid}: {nm} | width: {w}')
