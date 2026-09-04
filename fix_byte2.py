with open('atlas/vision/capture.py', 'rb') as f:  
    content = f.read()  
  
idx = content.find(b'height: int) -')  
print('Found at:', idx)  
if idx  
    start = content.rfind(b'def grab_rect', 0, idx)  
    print('Method starts at:', start)  
    if start  
