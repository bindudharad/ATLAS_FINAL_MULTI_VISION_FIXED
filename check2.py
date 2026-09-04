with open('atlas/vision/capture.py', 'r') as f:  
    content = f.read()  
idx = content.find('def grab_rect')  
print(repr(content[idx:idx+150])) 
