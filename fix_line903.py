with open('C:/Users/Bindudhara D/Downloads/ATLAS_FINAL_MULTI_VISION_FIXED/DataEntry - Copy/atlas/mapping/uia_map.py', 'r') as f:
    lines = f.readlines()

# Fix line 902 (index 901 in 0-based)
if '                # Filter by section' in lines[902]:
    lines[902] = '        # Filter by section: use parent group name to determine section\n'
    print('Fixed line 903')
else:
    print('Line 903:', repr(lines[902]))

with open('C:/Users/Bindudhara D/Downloads/ATLAS_FINAL_MULTI_VISION_FIXED/DataEntry - Copy/atlas/mapping/uia_map.py', 'w') as f:
    f.writelines(lines)
print('Done')
