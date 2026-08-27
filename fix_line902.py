with open('C:/Users/Bindudhara D/Downloads/ATLAS_FINAL_MULTI_VISION_FIXED/DataEntry - Copy/atlas/mapping/uia_map.py', 'r') as f:
    lines = f.readlines()

# Fix line 902 (index 901 in 0-based)
if '                # Filter by section' in lines[901]:
    lines[901] = '        # Filter by section: use parent group name to determine section\n'
    print('Fixed line 902')
else:
    print('Line 902:', repr(lines[901]))

with open('C:/Users/Bindudhara D/Downloads/ATLAS_FINAL_MULTI_VISION_FIXED/DataEntry - Copy/atlas/mapping/uia_map.py', 'w') as f:
    f.writelines(lines)
print('Done')
