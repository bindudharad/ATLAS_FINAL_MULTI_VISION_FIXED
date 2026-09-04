with open('atlas/vision/capture.py', 'r') as f:  
    lines = f.readlines()  
  
# Build the fixed file  
new_lines = []  
for line in lines:  
    if 'def grab_rect' in line and '- not in line:  
        # Skip the broken grab_rect and its docstring and body  
        continue  
    elif line.strip() == '# Use BitBlt directly to avoid mss side effects':  
        continue  
    elif line.strip() == 'return self._grab_bitblt(left, top, width, height)':  
        continue  
    else:  
        new_lines.append(line)  
  
# Now find _grab_mss and insert grab_rect before it  
for i, line in enumerate(new_lines):  
    if line.strip().startswith('def _grab_mss'):  
        grab_rect = [  
            '    def grab_rect(self, left: int, top: int, width: int, height: int) - 
            '        \\\"\\\"\\\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\\\"\\\"\\\"\\n',  
            '        # Use BitBlt directly to avoid mss side effects\\n',  
            '        return self._grab_bitblt(left, top, width, height)\\n',  
            '\\n'  
        ]  
        new_lines = new_lines[:i] + grab_rect + new_lines[i:]  
        break  
  
with open('atlas/vision/capture.py', 'w') as f:  
    f.writelines(new_lines)  
print('Fully fixed!') 
