with open('tests/test_verification.py', 'r') as f:
    lines = f.readlines()

new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    # Fix the escaped quotes
    line = line.replace('(scroll_dropdown\\\\\\\\, None)', '(\
scroll_dropdown\, None)')
    line = line.replace('(\\\\\scroll_dropdown\\\\\, None)', '(\scroll_dropdown\, None)')
    new_lines.append(line)
    i += 1

with open('tests/test_verification.py', 'w') as f:
    f.writelines(new_lines)
print('Fixed!')
