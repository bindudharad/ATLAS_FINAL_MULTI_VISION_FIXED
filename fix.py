with open('atlas/mapping/member_fields.py', 'r') as f:
    content = f.read()

old_part = "    \"education and career information\",\n})"
new_part = "    \"education and career information\",\n    \"record summary\",  # Source panel parent group name for member data labels\n})"

content = content.replace(old_part, new_part)

with open('atlas/mapping/member_fields.py', 'w') as f:
    f.write(content)
print('Done')
