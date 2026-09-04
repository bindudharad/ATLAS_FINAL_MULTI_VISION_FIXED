with open('atlas/vision/capture.py', 'r') as f:  
    content = f.read()  
  
# Fix 1: grab_rect signature  
content = content.replace('def grab_rect(self, left: int, top: int, width: int, height: int) -        \\\"\\\"\\\"Grab', 'def grab_rect(self, left: int, top: int, width: int, height: int) -> np.ndarray:\n        \\\"\\\"\\\"Grab')  
  
# Fix 2: duplicate _grab_mss  
content = content.replace('def _grab_mssdef _grab_mss', 'def _grab_mss')  
  
with open('atlas/vision/capture.py', 'w') as f:  
    f.write(content)  
print('Fixed!')  
