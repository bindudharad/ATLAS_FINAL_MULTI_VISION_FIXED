with open('tests/test_uia_flow.py', 'r') as f:
    content = f.read()

replacements = [
    ('UiaNode(name=\
gender\, control_type=\ComboBox\, rect=BBox(841, 382, 54, 26),',
     'UiaNode(name=\gender\, control_type=\ComboBox\, rect=BBox(961, 382, 54, 26),'),
    ('UiaNode(name=\nakshatra\, control_type=\ComboBox\, rect=BBox(841, 700, 132, 26),',
     'UiaNode(name=\nakshatra\, control_type=\ComboBox\, rect=BBox(961, 700, 132, 26),'),
    ('UiaNode(name=\Gender
Marital
Status\, control_type=\Text\, rect=BBox(841, 382, 160, 22),',
     'UiaNode(name=\Gender
Marital
Status\, control_type=\Text\, rect=BBox(961, 382, 160, 22),'),
    ('UiaNode(name=\Religious
and
Astro
Information\, control_type=\Text\, rect=BBox(841, 666, 200, 22),',
     'UiaNode(name=\Religious
and
Astro
Information\, control_type=\Text\, rect=BBox(961, 666, 200, 22),'),
]

for old, new in replacements:
    content = content.replace(old, new)

with open('tests/test_uia_flow.py', 'w') as f:
    f.write(content)
print('Fixed!')
