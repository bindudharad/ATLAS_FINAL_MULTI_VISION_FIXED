import base64  
with open('capture_b64.txt', 'r') as f:  
    encoded = f.read()  
content = base64.b64decode(encoded).decode('utf-8')  
# Find the exact malformed text  
idx = content.find('def grab_rect(self, left: int, top: int, width: int, height: int) -')  
if idx != -1:  
    end = content.find('\n', idx)  
    if end == -1: end = idx + 200  
    old = content[idx:end]  
    print('Old:', repr(old))  
    new = '    def grab_rect(self, left: int, top: int, width: int, height: int) -        \"\"\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\"\"\"\n'  
    content = content[:idx] + new + content[end:]  
    # Remove duplicate comment  
    content = content.replace('        # Use BitBlt directly to avoid mss side effects\n\n        # Use BitBlt directly to avoid mss side effects', '        # Use BitBlt directly to avoid mss side effects')  
    new_encoded = base64.b64encode(content.encode('utf-8')).decode('utf-8')  
    with open('capture_b64.txt', 'w') as f:  
        f.write(new_encoded)  
    print('Fixed signature')  
