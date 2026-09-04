import base64  
with open('capture_b64.txt', 'r') as f:  
    encoded = f.read()  
content = base64.b64decode(encoded)  
idx = content.find(b'def grab_rect')  
print('Index:', idx)  
for i in range(idx, idx+100):  
    b = content[i]  
