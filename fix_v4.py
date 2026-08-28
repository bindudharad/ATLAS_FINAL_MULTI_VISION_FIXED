with open('tests/test_verification.py', 'r') as f:
    content = f.read()

idx = content.find('def scroll_bar(self, direction, amount=3):')
if idx != -1:
    idx2 = content.find('\n    def paste', idx)
    if idx2 != -1:
        new_method = '\n    def scroll_dropdown(self, direction, amount=3):\n        self.calls.append((\
scroll_dropdown\, None))\n        return ControlOutcome(ok=True)\n'
        content = content[:idx2] + new_method + content[idx2:]
        with open('tests/test_verification.py', 'w') as f:
            f.write(content)
        print('Fixed!')
    else:
        print('Could not find def paste')
else:
    print('Could not find scroll_bar')
