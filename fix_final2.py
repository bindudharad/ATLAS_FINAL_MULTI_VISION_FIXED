with open('atlas/vision/capture.py', 'r') as f:  
    content = f.read()  
  
buggy = '''        self._fallback_until = 0.0  
  
        def grab_rect(self, left: int, top: int, width: int, height: int) - 
        \\\"\\\"\\\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\\\"\\\"\\\"  
        # Use BitBlt directly to avoid mss side effects  
        return self._grab_bitblt(left, top, width, height)  
    def _grab_mss(self, left: int, top: int, width: int, height: int) - 
  
fixed = '''        self._fallback_until = 0.0  
  
    def grab_rect(self, left: int, top: int, width: int, height: int) - 
        \\\"\\\"\\\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\\\"\\\"\\\"  
        # Use BitBlt directly to avoid mss side effects  
        return self._grab_bitblt(left, top, width, height)  
  
    def _grab_mss(self, left: int, top: int, width: int, height: int) - 
  
if buggy in content:  
    content = content.replace(buggy, fixed)  
    with open('atlas/vision/capture.py', 'w') as f:  
        f.write(content)  
    print('Fixed!')  
else:  
    print('Pattern not found') 
