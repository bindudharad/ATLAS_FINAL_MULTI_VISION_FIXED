with open('atlas/vision/capture.py', 'rb') as f:  
    raw = f.read()  
bad = b'def grab_rect(self, left: int, top: int, width: int, height: int) -'  
good = b'def grab_rect(self, left: int, top: int, width: int, height: int) - 
if bad in raw:  
    raw = raw.replace(bad, good)  
    with open('atlas/vision/capture.py', 'wb') as f:  
        f.write(raw)  
    print('Fixed')  
else:  
    print('Pattern not found') 
