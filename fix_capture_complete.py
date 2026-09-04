import base64  
with open('capture_b64.txt', 'r') as f:  
    encoded = f.read()  
content = base64.b64decode(encoded).decode('utf-8')  
lines = content.splitlines(keepends=True)  
# Fix line 73 (0-indexed)  
lines[73] = '    def grab_rect(self, left: int, top: int, width: int, height: int) - 
# Insert docstring at line 74  
lines.insert(74, '        \"\"\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\"\"\"\n')  
# Remove duplicate comment  
new_content = ''.join(lines)  
new_content = new_content.replace('        # Use BitBlt directly to avoid mss side effects\n\n        # Use BitBlt directly to avoid mss side effects', '        # Use BitBlt directly to avoid mss side effects')  
with open('capture_fixed.txt', 'w', encoding='utf-8') as f:  
    f.write(new_content)  
print('Fixed') 
