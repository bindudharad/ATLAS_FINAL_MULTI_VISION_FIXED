with open('atlas/vision/capture.py', 'r') as f:  
    lines = f.readlines()  
lines[73] = '    def grab_rect(self, left: int, top: int, width: int, height: int) - 
lines.insert(74, '        \"\"\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\"\"\"\n')  
with open('atlas/vision/capture.py', 'w') as f:  
    f.writelines(lines)  
print('Fixed lines')  
