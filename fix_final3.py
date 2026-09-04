with open('atlas/vision/capture.py', 'r') as f:  
    lines = f.readlines()  
  
# Remove lines 73-76 (0-indexed) - the nested grab_rect  
new_lines = lines[:73] + lines[77:]  
  
# Now find where _grab_mss is and insert grab_rect before it  
for i, line in enumerate(new_lines):  
    if 'def _grab_mss' in line:  
        grab_rect = '''    def grab_rect(self, left: int, top: int, width: int, height: int) -        \\\"\\\"\\\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\\\"\\\"\\\"\n        # Use BitBlt directly to avoid mss side effects\n        return self._grab_bitblt(left, top, width, height)\n\n'''  
        new_lines = new_lines[:i] + [grab_rect] + new_lines[i:]  
        break  
  
with open('atlas/vision/capture.py', 'w') as f:  
    f.writelines(new_lines)  
print('Fixed!') 
