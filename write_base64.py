import base64  
fixed_b64 = open('atlas/vision/capture.py', 'rb').read()  
encoded = base64.b64encode(fixed_b64).decode()  
with open('capture_b64.txt', 'w') as f: f.write(encoded)  
print('Encoded to capture_b64.txt') 
