import base64  
with open('capture_b64.txt', 'r') as f:  
    encoded = f.read()  
content = base64.b64decode(encoded).decode('utf-8')  
idx = content.find('def grab_rect')  
print(repr(content[idx:idx+200]))  
