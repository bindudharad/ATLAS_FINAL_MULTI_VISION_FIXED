import base64  
with open('capture_b64.txt', 'r') as f:  
    encoded = f.read()  
content = base64.b64decode(encoded)  
with open('atlas/vision/capture.py', 'wb') as f:  
    f.write(content)  
print('Restored')  
