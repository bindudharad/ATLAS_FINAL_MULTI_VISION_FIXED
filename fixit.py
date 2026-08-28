with open('tests/test_uia_flow.py', 'r') as f:
    lines = f.readlines()

in_test = False
new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    if 'def test_field_map_build_excludes_form_labels_from_left_labels' in line:
        in_test = True
    if in_test and 'text = [' in line:
        new_lines.append(line)
        new_lines.append('        # Source-panel labels live under a pure-text group (\
Record
summary\)\n')
        new_lines.append('        UiaNode(name=\
Member
Name\, control_type=\Text\, rect=BBox(585, 186, 80, 22),\n')
        new_lines.append('                parent={\
name\: \Record
summary\, \control_type\: \Group\}),\n')
        new_lines.append('        UiaNode(name=\
Application
No\, control_type=\Text\, rect=BBox(585, 230, 140, 22),\n')
        new_lines.append('                parent={\
name\: \Record
summary\, \control_type\: \Group\}),\n')
        new_lines.append('        # Right-form labels share parent with editable fields\n')
        new_lines.append('        UiaNode(name=\
Gender
Marital
Status\, control_type=\Text\, rect=BBox(841, 382, 160, 22),\n')
        new_lines.append('                parent={\
name\: \Member
Basic
Information\, \control_type\: \Group\}),\n')
        new_lines.append('        UiaNode(name=\
Religious
and
Astro
Information\, control_type=\Text\, rect=BBox(841, 666, 200, 22),\n')
        new_lines.append('                parent={\
name\: \Religious
and
Astro
Information\, \control_type\: \Group\}),\n')
        i += 1
        while i < len(lines):
            if lines[i].strip() == ']' and lines[i].startswith('    '):
                new_lines.append(lines[i])
                i += 1
                break
            i += 1
        new_lines.extend(lines[i:])
        with open('tests/test_uia_flow.py', 'w') as f:
            f.writelines(new_lines)
        print('Fixed!')
        exit()
    new_lines.append(line)
    i += 1
print('Test function not found')
