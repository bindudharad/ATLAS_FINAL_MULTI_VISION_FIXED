with open('atlas/vision/capture.py', 'rb') as f:  
    content = f.read()  
idx = content.find(b'def grab_rect')  
for i in range(idx, min(idx+200, len(content))):  
    c = content[i]  
