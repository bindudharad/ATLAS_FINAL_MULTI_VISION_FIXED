with open('C:/Users/Bindudhara D/Downloads/ATLAS_FINAL_MULTI_VISION_FIXED/DataEntry - Copy/atlas/mapping/member_fields.py', 'r') as f:
    lines = f.readlines()

lines[39] = '    \
member
basic
information\,\n'
lines[40] = '    \religious
and
astro
information\,\n'
lines.insert(41, '    \physical
and
habits
information\,\n')
lines.insert(42, '    \family
information\,\n')
lines.insert(43, '    \education
and
career
information\,\n')

with open('C:/Users/Bindudhara D/Downloads/ATLAS_FINAL_MULTI_VISION_FIXED/DataEntry - Copy/atlas/mapping/member_fields.py', 'w') as f:
    f.writelines(lines)
print('Fixed MEMBER_SECTION_HEADERS')
