with open('atlas/vision/capture.py', 'rb') as f:  
    data = f.read()  
# Fix 1: grab_rect signature  
data = data.replace(b'def grab_rect(self, left: int, top: int, width: int, height: int) -        \"\"\"', b'def grab_rect(self, left: int, top: int, width: int, height: int) -> np.ndarray:\r\n        \"\"\"')  
# Fix 2: duplicate _grab_mss  
data = data.replace(b'def _grab_mssdef _grab_mss', b'def _grab_mss')  
with open('atlas/vision/capture.py', 'wb') as f:  
    f.write(data)  
print('Fixed!')  
