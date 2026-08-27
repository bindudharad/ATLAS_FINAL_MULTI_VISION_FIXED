import json
from atlas.mapping.member_fields import section_of

with open('debug/mpf/field_map.json', 'r') as f:
    data = json.load(f)

print('Checking parent names:')
for l in data.get('left_labels', []):
    nm = l.get('name') or ''
    aid = l.get('automation_id','')
    parent = l.get('parent', {})
    pname = parent.get('name', '')
    sec = section_of(pname)
    print(f'  {aid}: {nm} | parent: \
pname
\ -> section: {sec}')
