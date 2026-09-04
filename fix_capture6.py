with open('atlas/vision/capture.py', 'r') as f:  
    content = f.read()  
  
# Fix the split backslash - it's split(\"\\\\\") which in the file is split(chr(92))  
content = content.replace('split(\"\\\\\\\\\")', 'split(chr(92))')  
  
with open('atlas/vision/capture.py', 'w') as f:  
    f.write(content)  
print('Fixed!')  
