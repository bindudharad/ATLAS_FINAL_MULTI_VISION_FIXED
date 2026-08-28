with open('tests/test_uia_flow.py', 'r') as f:
    content = f.read()

# Find the exact text block
start = content.find('text = [')
# Find the next occurrence after the test function
test_start = content.find('def test_field_map_build_excludes_form_labels_from_left_labels')
start = content.find('text = [', test_start)
end = content.find('\n    ]\n    backend =', start)

if start != -1 and end != -1:
    print('Found from', start, 'to', end)
    new_block = '''text = [
        # Source-panel labels live under a pure-text group (\
Record
summary\)
        UiaNode(name=\Member
Name\, control_type=\Text\, rect=BBox(585, 186, 80, 22),
                parent={\name\: \Record
summary\, \control_type\: \Group\}),
        UiaNode(name=\Application
No\, control_type=\Text\, rect=BBox(585, 230, 140, 22),
                parent={\name\: \Record
summary\, \control_type\: \Group\}),
        # Right-form labels share parent with editable fields
        UiaNode(name=\Gender
Marital
Status\, control_type=\Text\, rect=BBox(841, 382, 160, 22),
                parent={\name\: \Member
Basic
Information\, \control_type\: \Group\}),
        UiaNode(name=\Religious
and
Astro
Information\, control_type=\Text\, rect=BBox(841, 666, 200, 22),
                parent={\name\: \Religious
and
Astro
Information\, \control_type\: \Group\}),'''
    
    content = content[:start] + new_block + content[end:]
    with open('tests/test_uia_flow.py', 'w') as f:
        f.write(content)
    print('Fixed!')
else:
    print('Not found', start, end)
