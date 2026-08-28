with
open
tests/test_verification.py
r
as
f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if 'def scroll_dropdown(self, direction, amount=3):' in line:
        new_lines.append('    def scroll_dropdown(self, direction, amount=3):\n')
    elif 'self.calls.append((\
scroll_dropdown\, None))' in line and i > 0 and 'scroll_dropdown' in lines[i-1]:
        new_lines.append('        self.calls.append((\
scroll_dropdown\, None))\n')
    elif 'return ControlOutcome(ok=True)' in line and i > 1 and 'scroll_dropdown' in lines[i-2]:
        new_lines.append('        return ControlOutcome(ok=True)\n')
    else:
        new_lines.append(line)

with open('tests/test_verification.py', 'w') as f:
    f.writelines(new_lines)
print('Fixed!')
