import base64  
with open('capture_b64.txt', 'r') as f:  
    encoded = f.read()  
content = base64.b64decode(encoded).decode('utf-8')  
idx = content.find('def grab_rect')  
# Get exact old block  
end_idx = content.find('    def _grab_mss', idx)  
if end_idx == -1: end_idx = idx + 300  
old = content[idx:end_idx]  
print('OLD BLOCK:')  
print(repr(old))  
