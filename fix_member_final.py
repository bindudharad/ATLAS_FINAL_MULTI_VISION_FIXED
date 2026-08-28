with open('atlas/mapping/member_fields.py', 'r') as f:
    content = f.read()

idx = content.find('MEMBER_SECTION_HEADERS = frozenset({')
if idx != -1:
    idx2 = content.find('})', idx)
    if idx2 != -1:
        new_content = content[:idx2] + '    \
record
summary\,  # Source panel parent group name for member data labels\n' + content[idx2:]
        with open('atlas/mapping/member_fields.py', 'w') as f:
            f.write(new_content)
        print('Fixed!')
    else:
        print('Could not find closing brace')
else:
    print('Could not find MEMBER_SECTION_HEADERS')
