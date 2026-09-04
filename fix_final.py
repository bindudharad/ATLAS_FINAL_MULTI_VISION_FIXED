with open('atlas/vision/capture.py', 'r') as f:  
    content = f.read()  
content = content.replace('.split(\"\\\\\")', '.split(chr(92))')  
with open('atlas/vision/capture.py', 'w') as f:  
    f.write(content)  
print('Fixed!')  
