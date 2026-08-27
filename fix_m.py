with open('C:/Users/Bindudhara D/Downloads/ATLAS_FINAL_MULTI_VISION_FIXED/DataEntry - Copy/atlas/mapping/member_fields.py', 'r') as f:
    content = f.read()

old = chr(34) + 'religious and astro information' + chr(34) + ',
    ' + chr(34) + 'physical and habits information' + chr(34) + ',
    ' + chr(34) + 'family information' + chr(34) + ',
    ' + chr(34) + 'education and career information' + chr(34) + ','
new = chr(34) + 'religious and astro information' + chr(34) + ',\n    ' + chr(34) + 'physical and habits information' + chr(34) + ',\n    ' + chr(34) + 'family information' + chr(34) + ',\n    ' + chr(34) + 'education and career information' + chr(34) + ','

content = content.replace(old, new)

with open('C:/Users/Bindudhara D/Downloads/ATLAS_FINAL_MULTI_VISION_FIXED/DataEntry - Copy/atlas/mapping/member_fields.py', 'w') as f:
    f.write(content)
print('Fixed')
