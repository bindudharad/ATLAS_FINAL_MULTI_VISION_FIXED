with open('atlas/vision/capture.py', 'rb') as f:  
    content = f.read()  
idx = content.find(b'def grab_rect')  
print('Found at:', idx)  
print('Context:')  
print(content[idx-10:idx+150]) 
