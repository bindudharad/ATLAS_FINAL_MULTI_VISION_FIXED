import sys  
with open('atlas/core/safety.py', 'rb') as f:  
    content = f.read()  
content = content.replace(b'action: str) -', b'action: str) - 
with open('atlas/core/safety.py', 'wb') as f:  
    f.write(content)  
print('Fixed')  
