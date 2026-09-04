with open('atlas/vision/capture.py', 'r') as f:  
    content = f.read()  
idx = content.find('def grab_rect')  
print('Found at:', idx)  
print(repr(content[idx:idx+200])) 
