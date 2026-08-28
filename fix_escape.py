import re
with open('tests/test_verification.py', 'r') as f:
    content = f.read()

# Fix the escaped quotes
content = content.replace('(\\\
scroll_dropdown\\\, None)', '(\scroll_dropdown\, None)')
content = content.replace('self.calls.append((scroll_dropdown\\\\, None))', 'self.calls.append((\scroll_dropdown\, None))')

with open('tests/test_verification.py', 'w') as f:
    f.write(content)
print('Fixed escaping!')
