import base64  
with open('capture_b64.txt', 'r') as f:  
    encoded = f.read()  
content = base64.b64decode(encoded).decode('utf-8')  
lines = content.splitlines(keepends=True)  
# Find the grab_rect method  
for i, line in enumerate(lines):  
    if 'def grab_rect' in line and '- not in line:  
        # Fix 1: Change indentation from 8 spaces to 4 spaces  
        line = line.replace('        def grab_rect', '    def grab_rect')  
        # Fix 2: Fix the method signature  
        line = line.replace(' -        \\\"\\\"\\\"', ' -> np.ndarray:\\n        \\\"\\\"\\\"')  
        lines[i] = line  
        break  
# Fix the docstring line  
for i, line in enumerate(lines):  
