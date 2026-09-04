with open('atlas/vision/capture.py', 'r') as f:  
    content = f.read()  
  
# The file contains literal backslash-quote sequences  
# Fix: replace \\\\\" with \"  
content = content.replace(chr(92) + chr(34), chr(34))  
  
with open('atlas/vision/capture.py', 'w') as f:  
    f.write(content)  
print('Fixed!')  
