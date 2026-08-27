import json
with open('debug/mpf/field_map.json', 'r') as f:
    data = json.load(f)

for l in data.get('right_fields', []):
    nm = l.get('name') or ''
    aid = l.get('automation_id','')
    parent = l.get('parent', {})
    pname = parent.get('name', '')
    if nm:
        print(aid + ': ' + nm + ' | parent: ' + pname)
