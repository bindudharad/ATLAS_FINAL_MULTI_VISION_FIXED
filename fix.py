with open('atlas/vision/capture.py', 'r') as f:  
    content = f.read()  
  
lines = content.split('\n')  
new_lines = lines[:73] + lines[77:]  
  
output = '\n'.join(new_lines)  
output = output.replace(  
    '    def _grab_mss(self, left: int, top: int, width: int, height: int) - 
    '    def grab_rect(self, left: int, top: int, width: int, height: int) -        \\\"\\\"\\\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\\\"\\\"\\\"\n        # Use BitBlt directly to avoid mss side effects\n        return self._grab_bitblt(left, top, width, height)\n\n    def _grab_mss(self, left: int, top: int, width: int, height: int) - 
)  
  
with open('atlas/vision/capture.py', 'w') as f:  
    f.write(output)  
print('Fixed!') 
