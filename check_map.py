import json
with open('debug/mpf/field_map.json', 'r') as f:
    data = json.load(f)

with_name = 0
for l in data.get('right_fields', []):
    nm = l.get('name') or ''
    if nm:
        with_name += 1
print('Right fields with name:', with_name, '/', len(data.get('right_fields', [])))

for l in data.get('left_labels', []):
    nm = l.get('name') or ''
    aid = l.get('automation_id','')
    print(aid + ': ' + nm)
