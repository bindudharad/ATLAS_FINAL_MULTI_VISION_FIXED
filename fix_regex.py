import re  
with open('atlas/vision/capture.py', 'r') as f:  
    content = f.read()  
  
pattern = r'        self\._fallback_until = 0\.0\n\n        def grab_rect\(self, left: int, top: int, width: int, height: int\) -        \\\"\\\"\\\"Grab a rectangle and return an RGB numpy array using BitBlt \(avoids mss window maximization side effect\)\.\\\"\\\"\\\"\n        # Use BitBlt directly to avoid mss side effects\n        return self\._grab_bitblt\(left, top, width, height\)\n    def _grab_mss\(self, left: int, top: int, width: int, height: int\) - 
  
replacement = '''        self._fallback_until = 0.0  
  
    def grab_rect(self, left: int, top: int, width: int, height: int) - 
        \\\"\\\"\\\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\\\"\\\"\\\"  
        # Use BitBlt directly to avoid mss side effects  
        return self._grab_bitblt(left, top, width, height)  
  
    def _grab_mss(self, left: int, top: int, width: int, height: int) - 
  
new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)  
  
with open('atlas/vision/capture.py', 'w') as f:  
    f.write(new_content)  
print('Fixed!') 
