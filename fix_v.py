with open('tests/test_verification.py', 'r') as f:
    lines = f.readlines()

new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    new_lines.append(line)
    if 'calls.append((\
scroll_bar\, None))' in line:
        j = i + 1
        while j < len(lines) and not lines[j].startswith('    def '):
            j += 1
        if j < len(lines) and 'def paste' in lines[j]:
            new_lines.append('    def scroll_dropdown(self, direction, amount=3):\n')
            new_lines.append('        self.calls.append((\
scroll_dropdown\, None))\n')
            new_lines.append('        return ControlOutcome(ok=True)\n')
    i += 1

with open('tests/test_verification.py', 'w') as f:
    f.writelines(new_lines)
print('Done')
