import base64  
fixed = base64.b64decode(open('capture_b64.txt').read())  
with open('atlas/vision/capture.py', 'wb') as f:  
    f.write(fixed)  
print('Fixed!') 
