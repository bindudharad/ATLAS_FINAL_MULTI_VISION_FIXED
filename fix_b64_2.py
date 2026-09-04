with open('atlas/vision/capture.py', 'r') as f:  
    content = f.read()  
  
old = '        self._fallback_until = 0.0\n\n        def grab_rect(self, left: int, top: int, width: int, height: int) -        \\\"\\\"\\\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\\\"\\\"\\\"\n        # Use BitBlt directly to avoid mss side effects\n        return self._grab_bitblt(left, top, width, height)\n    def _grab_mss(self, left: int, top: int, width: int, height: int) - 
  
new = '        self._fallback_until = 0.0\n\n    def grab_rect(self, left: int, top: int, width: int, height: int) -        \\\"\\\"\\\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\\\"\\\"\\\"\n        # Use BitBlt directly to avoid mss side effects\n        return self._grab_bitblt(left, top, width, height)\n\n    def _grab_mss(self, left: int, top: int, width: int, height: int) - 
  
if old in content:  
    content = content.replace(old, new)  
    with open('atlas/vision/capture.py', 'w') as f:  
        f.write(content)  
    print('Fixed!')  
else:  
    print('Pattern not found') 
