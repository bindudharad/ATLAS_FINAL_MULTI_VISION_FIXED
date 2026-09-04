with open('atlas/vision/capture.py', 'rb') as f:  
    data = f.read()  
# Replace the whole .split(\"\\\\\")[-1]  
data = data.replace(b'.split(\"\\\\\\\\\")[-1]', b'.split(chr(92))[-1]')  
with open('atlas/vision/capture.py', 'wb') as f:  
    f.write(data)  
print('Fixed!')  
