with open('atlas/vision/capture.py', 'r') as f:  
    lines = f.readlines()  
for i, line in enumerate(lines):  
    if 'grab_rect' in line or '_fallback_until' in line:  
        print(f'Line {i+1}: {repr(line)}')  
