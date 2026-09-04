with open('atlas/vision/capture.py', 'rb') as f:  
    data = f.read()  
# Replace b'split(\"\\\\\\\\\")' with b'split(chr(92))'  
data = data.replace(b'split(\"\\\\\\\\\")', b'split(chr(92))')  
with open('atlas/vision/capture.py', 'wb') as f:  
    f.write(data)  
print('Fixed!')  
