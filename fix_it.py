with
open
atlas/mapping/member_fields.py
r
as
f:
    content = f.read()

content = content.replace(
    '    \
education
and
career
information\,\n})',
    '    \
education
and
career
information\,\n    \record
summary\,  # Source panel parent group name for member data labels\n})'
)

with open('atlas/mapping/member_fields.py', 'w') as f:
    f.write(content)
print('Done')
