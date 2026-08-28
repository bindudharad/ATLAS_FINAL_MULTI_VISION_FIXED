with open('atlas/mapping/member_fields.py', 'r') as f:
    content = f.read()

old = '#: Section headers whose lines ARE member data.\nMEMBER_SECTION_HEADERS = frozenset({\n    \
member
basic
information\,\n    \religious
and
astro
information\,\n    \physical
and
habits
information\,\n    \family
information\,\n    \education
and
career
information\,\n})'

new = '#: Section headers whose lines ARE member data.\nMEMBER_SECTION_HEADERS = frozenset({\n    \member
basic
information\,\n    \religious
and
astro
information\,\n    \physical
and
habits
information\,\n    \family
information\,\n    \education
and
career
information\,\n    \record
summary\,  # Source panel parent group name for member data labels\n})'

if old in content:
    content = content.replace(old, new)
    with open('atlas/mapping/member_fields.py', 'w') as f:
        f.write(content)
    print('Fixed!')
else:
    print('Not found')
