with open('atlas/vision/capture.py', 'rb') as f:  
    raw = f.read()  
idx = raw.find(b'def grab_rect')  
for i in range(idx, idx+120):  
    b = raw[i]  
