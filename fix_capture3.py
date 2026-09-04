with open('atlas/vision/capture.py', 'r') as f:  
    content = f.read()  
  
# Fix escaped quotes in docstring  
content = content.replace('\\\\\\\\\"\\\\\\\\\"\\\\\\\\\"Grab', '\\\"\\\"\\\"Grab')  
content = content.replace('side effect).\\\\\\\\\"\\\\\\\\\"\\\\\\\\\"', 'side effect).\\\"\\\"\\\"')  
  
with open('atlas/vision/capture.py', 'w') as f:  
    f.write(content)  
print('Fixed!')  
