import re

with open('C:/Users/Bindudhara D/Downloads/ATLAS_FINAL_MULTI_VISION_FIXED/DataEntry - Copy/atlas/mapping/uia_map.py', 'r') as f:
    content = f.read()

old_text = '''        # Filter by section: only member-section labels are valid source fields
        node_section = section_of(node.name)
        if node_section == \
ignored\:
            continue  # Skip Project Details, Shift Details, etc.
        if node_section is None:
            continue  # Skip unrecognized sections
        result.append(node)'''

new_text = '''        # Filter by section: use parent group name to determine section
        parent_name = _node_parent_name(node)
        parent_section = section_of(parent_name)
        if parent_section == \ignored\:
            continue  # Skip Project Details, Shift Details, etc.
        if parent_section is None and parent_name:
            # Parent exists but not recognized - likely a UI chrome group
            continue
        result.append(node)'''

if old_text in content:
    content = content.replace(old_text, new_text)
    print('Replaced successfully')
else:
    print('Old text not found')

with open('C:/Users/Bindudhara D/Downloads/ATLAS_FINAL_MULTI_VISION_FIXED/DataEntry - Copy/atlas/mapping/uia_map.py', 'w') as f:
    f.write(content)
print('Done')
