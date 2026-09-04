import base64  
with open('capture_b64.txt', 'r') as f:  
    encoded = f.read()  
content = base64.b64decode(encoded).decode('utf-8')  
# Fix indentation  
content = content.replace('            def grab_rect', '    def grab_rect')  
content = content.replace('        \\\"\\\"\\\"Grab a rectangle', '        \\\"\\\"\\\"Grab a rectangle')  
new_encoded = base64.b64encode(content.encode('utf-8')).decode('utf-8')  
with open('capture_b64.txt', 'w') as f:  
    f.write(new_encoded)  
print('Fixed indentation')  
