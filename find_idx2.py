import sys  
with open('atlas/core/safety.py', 'rb') as f:  
    content = f.read()  
idx = content.find(b'str) -')  
print('Found at:', idx)  
if idx  print('Context:', content[idx:idx+20])  
