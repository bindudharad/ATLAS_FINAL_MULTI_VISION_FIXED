import base64  
with open('capture_b64.txt', 'r') as f:  
    encoded = f.read()  
content = base64.b64decode(encoded).decode('utf-8')  
lines = content.splitlines(keepends=True)  
for i, line in enumerate(lines[70:85]):  
    print(f'Line {i+70}: {repr(line)}')  
