import json
with open('debug/mpf/field_map.json', 'r') as f:
    data = json.load(f)

# Check the mappings - they should be source -> target
for m in data.get('mappings', []):
    print(m)
