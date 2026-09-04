import base64  
with open('capture_b64.txt', 'r') as f:  
    encoded = f.read()  
content = base64.b64decode(encoded).decode('utf-8')  
lines = content.splitlines(keepends=True)  
for i, line in enumerate(lines):  
    if 'def grab_rect' in line:  
        print(f'Line {i}: {repr(line)}')  
        break  
