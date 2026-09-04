with open('atlas/vision/capture.py', 'rb') as f:  
    raw = f.read()  
idx = raw.find(b'def grab_rect')  
print('Found at:', idx)  
print(repr(raw[idx:idx+250]))  
