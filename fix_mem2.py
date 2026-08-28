with open('atlas/mapping/member_fields.py', 'r') as f:
    lines = f.readlines()

new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    new_lines.append(line)
    if 'MEMBER_SECTION_HEADERS = frozenset({' in line:
        j = i + 1
        while j < len(lines) and '})' not in lines[j]:
            j += 1
        if j < len(lines):
            new_lines.insert(len(new_lines), '    \
record
summary\,  # Source panel parent group name for member data labels\n')
    i += 1

with open('atlas/mapping/member_fields.py', 'w') as f:
    f.writelines(new_lines)
print('Done')
