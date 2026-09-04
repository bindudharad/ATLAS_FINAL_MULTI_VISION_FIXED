with open('atlas/vision/capture.py', 'rb') as f:  
    content = f.read()  
idx = content.find(b'def grab_rect')  
print('Index:', idx)  
print('Bytes:', repr(content[idx:idx+150]))  
