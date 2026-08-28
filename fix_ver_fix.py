with
open
tests/test_verification.py
r
as
f:
    lines = f.readlines()

new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    new_lines.append(line)
    if 'def scroll_bar(self, direction, amount=3):' in line and i+2 < len(lines):
        new_lines.append('    def scroll_dropdown(self, direction, amount=3):\n')
        new_lines.append('        self.calls.append((\
scroll_dropdown\, None))\n')
        new_lines.append('        return ControlOutcome(ok=True)\n')
    i += 1

with open('tests/test_verification.py', 'w') as f:
    f.writelines(new_lines)
print('Fixed!')
