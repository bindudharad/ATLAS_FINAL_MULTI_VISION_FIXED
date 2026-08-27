with open('C:/Users/Bindudhara D/Downloads/ATLAS_FINAL_MULTI_VISION_FIXED/DataEntry - Copy/atlas/mapping/uia_map.py', 'r') as f:
    content = f.read()

old_text = '        # Filter by section: only member-section labels are valid source fields\n        node_section = section_of(node.name)\n        if node_section == \
ignored\:\n            continue  # Skip Project Details, Shift Details, etc.\n        if node_section is None:\n            continue  # Skip unrecognized sections\n        result.append(node)'

new_text = '        # Filter by section: use parent group name to determine section\n        parent_name = _node_parent_name(node)\n        parent_section = section_of(parent_name)\n        if parent_section == \ignored\:\n            continue  # Skip Project Details, Shift Details, etc.\n        if parent_section is None and parent_name:\n            # Parent exists but not recognized - likely a UI chrome group\n            continue\n        result.append(node)'

if old_text in content:
    content = content.replace(old_text, new_text)
    print('Replaced successfully')
else:
    print('Old text not found')
    idx = content.find('node_section = section_of(node.name)')
    if idx >= 0:
        print('Found at index', idx)
        print(repr(content[idx:idx+200]))

with open('C:/Users/Bindudhara D/Downloads/ATLAS_FINAL_MULTI_VISION_FIXED/DataEntry - Copy/atlas/mapping/uia_map.py', 'w') as f:
    f.write(content)
