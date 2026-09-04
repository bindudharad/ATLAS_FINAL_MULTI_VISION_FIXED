import base64  
with open('capture_b64.txt', 'r') as f:  
    encoded = f.read()  
content = base64.b64decode(encoded).decode('utf-8')  
with open('capture_text.txt', 'w', encoding='utf-8') as f:  
    f.write(content)  
print('Done')  
