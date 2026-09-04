import base64  
with open('capture_backup2.py', 'rb') as f:  
    content = f.read()  
encoded = base64.b64encode(content).decode()  
with open('capture_b64.txt', 'w') as f:  
    f.write(encoded)  
print('Encoded length:', len(encoded))  
