with open('atlas/vision/capture.py', 'r') as f:  
    lines = f.readlines()  
  
new_lines = []  
for line in lines:  
    if line.strip().startswith('def grab_rect'):  
        new_lines.append('    def grab_rect(self, left: int, top: int, width: int, height: int) - 
        new_lines.append('        \\\"\\\"\\\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\\\"\\\"\\\"\\n')  
        new_lines.append('        # Use BitBlt directly to avoid mss side effects\\n')  
        new_lines.append('        return self._grab_bitblt(left, top, width, height)\\n')  
        new_lines.append('\\n')  
    else:  
        new_lines.append(line)  
  
with open('atlas/vision/capture.py', 'w') as f:  
    f.writelines(new_lines)  
print('Rewritten!') 
