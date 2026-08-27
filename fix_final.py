with open('C:/Users/Bindudhara D/Downloads/ATLAS_FINAL_MULTI_VISION_FIXED/DataEntry - Copy/atlas/mapping/uia_map.py', 'r') as f:
    content = f.read()

idx = content.find('node_section = section_of(node.name)')
if idx >= 0:
    comment_idx = content.rfind('# Filter by section', 0, idx)
    if comment_idx == -1:
        comment_idx = idx - 50
    end_idx = content.find('result.append(node)', idx)
    if end_idx >= 0:
        end_idx += len('result.append(node)')
        old_segment = content[comment_idx:end_idx]
        print('OLD SEGMENT found, length:', len(old_segment))
        
        new_segment = '        # Filter by section: use parent group name to determine section\n        parent_name = _node_parent_name(node)\n        parent_section = section_of(parent_name)\n        if parent_section == \
ignored\:\n            continue  # Skip Project Details, Shift Details, etc.\n        if parent_section is None and parent_name:\n            # Parent exists but not recognized - likely a UI chrome group\n            continue\n        result.append(node)'
        
        new_content = content[:comment_idx] + new_segment + content[end_idx:]
        with open('C:/Users/Bindudhara D/Downloads/ATLAS_FINAL_MULTI_VISION_FIXED/DataEntry - Copy/atlas/mapping/uia_map.py', 'w') as f:
            f.write(new_content)
        print('Replaced successfully')
    else:
        print('Could not find end')
else:
    print('Not found')
