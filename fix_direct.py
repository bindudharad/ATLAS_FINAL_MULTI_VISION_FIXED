with open('atlas/vision/capture.py', 'r') as f:  
    content = f.read()  
idx = content.find('def grab_rect(self, left: int, top: int, width: int, height: int)')  
if idx  
    end_idx = content.find('    def _grab_mss', idx)  
    if end_idx == -1: end_idx = idx + 300  
    old = content[idx:end_idx]  
    print('OLD:', repr(old))  
    new = '    def grab_rect(self, left: int, top: int, width: int, height: int) -        \"\"\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\"\"\"\n        # Use BitBlt directly to avoid mss side effects\n        return self._grab_bitblt(left, top, width, height)\n\n'  
    content = content[:idx] + new + content[end_idx:]  
    with open('atlas/vision/capture.py', 'w') as f:  
        f.write(content)  
    print('Fixed!')  
else:  
    print('Not found')  
