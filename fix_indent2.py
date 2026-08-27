with open('C:/Users/Bindudhara D/Downloads/ATLAS_FINAL_MULTI_VISION_FIXED/DataEntry - Copy/atlas/mapping/uia_map.py', 'r') as f:
    content = f.read()

old = '        if node.rect.width > 120:\n            continue\n                # Filter by section: use parent group name to determine section\n        parent_name = _node_parent_name(node)\n        parent_section = section_of(parent_name)\n        if parent_section == \
ignored\:\n            continue  # Skip Project Details, Shift Details, etc.\n        if parent_section is None and parent_name:\n            # Parent exists but not recognized - likely a UI chrome group\n            continue\n        result.append(node)'

new = '        if node.rect.width > 120:\n            continue\n        # Filter by section: use parent group name to determine section\n        parent_name = _node_parent_name(node)\n        parent_section = section_of(parent_name)\n        if parent_section == \ignored\:\n            continue  # Skip Project Details, Shift Details, etc.\n        if parent_section is None and parent_name:\n            # Parent exists but not recognized - likely a UI chrome group\n            continue\n        result.append(node)'

if old in content:
    content = content.replace(old, new)
    print('Fixed indentation')
else:
    print('Old text not found')
    idx = content.find('Filter by section')
    if idx >= 0:
        print('Found at:', idx)
        print(repr(content[idx:idx+300]))

with open('C:/Users/Bindudhara D/Downloads/ATLAS_FINAL_MULTI_VISION_FIXED/DataEntry - Copy/atlas/mapping/uia_map.py', 'w') as f:
    f.write(content)
