import base64  
with open('capture_b64.txt', 'r') as f:  
    encoded = f.read()  
content = base64.b64decode(encoded).decode('utf-8')  
idx = content.find('def grab_rect')  
end_idx = content.find('    def _grab_mss', idx)  
if end_idx == -1: end_idx = idx + 300  
old = content[idx:end_idx]  
# Now do the replacement using exact match  
new = '    def grab_rect(self, left: int, top: int, width: int, height: int) -        \"\"\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\"\"\"\n        # Use BitBlt directly to avoid mss side effects\n        return self._grab_bitblt(left, top, width, height)\n\n'  
content = content[:idx] + new + content[end_idx:]  
new_encoded = base64.b64encode(content.encode('utf-8')).decode('utf-8')  
with open('capture_b64.txt', 'w') as f:  
    f.write(new_encoded)  
print('Fixed')  
