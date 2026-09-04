import base64  
with open('capture_b64.txt', 'r') as f:  
    encoded = f.read()  
content = base64.b64decode(encoded).decode('utf-8')  
lines = content.splitlines(keepends=True)  
# Fix line 73: fix indentation and signature  
lines[73] = '    def grab_rect(self, left: int, top: int, width: int, height: int) - 
# Insert docstring at line 74  
lines.insert(74, '        \"\"\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\"\"\"\r\n')  
# Remove duplicate comment  
new_content = ''.join(lines)  
new_content = new_content.replace('        # Use BitBlt directly to avoid mss side effects\r\n\r\n        # Use BitBlt directly to avoid mss side effects', '        # Use BitBlt directly to avoid mss side effects')  
new_encoded = base64.b64encode(new_content.encode('utf-8')).decode('utf-8')  
with open('capture_b64.txt', 'w') as f:  
    f.write(new_encoded)  
print('Fixed')  
