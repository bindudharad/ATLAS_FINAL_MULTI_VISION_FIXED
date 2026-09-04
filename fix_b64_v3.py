import base64  
with open('capture_b64.txt', 'r') as f:  
    encoded = f.read()  
content = base64.b64decode(encoded).decode('utf-8')  
idx = content.find('def grab_rect(self, left: int, top: int, width: int, height: int)')  
with open('find_output.txt', 'w') as out:  
    out.write('Found at: ' + str(idx) + '\n')  
    if idx != -1:  
        out.write(repr(content[idx:idx+150])) 
