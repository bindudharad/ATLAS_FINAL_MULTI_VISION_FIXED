with open('tests/test_verification.py', 'r') as f:
    content = f.read()

old = '    def scroll_bar(self, direction, amount=3):\n        self.calls.append((\
scroll_bar\, None))\n        return ControlOutcome(ok=True)\n    def paste(self, value, field_id=None):'
new = '    def scroll_bar(self, direction, amount=3):\n        self.calls.append((\scroll_bar\, None))\n        return ControlOutcome(ok=True)\n    def scroll_dropdown(self, direction, amount=3):\n        self.calls.append((\scroll_dropdown\, None))\n        return ControlOutcome(ok=True)\n    def paste(self, value, field_id=None):'

if old in content:
    content = content.replace(old, new)
    with open('tests/test_verification.py', 'w') as f:
        f.write(content)
    print('Fixed!')
else:
    print('Not found')
