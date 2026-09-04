with open('atlas/vision/capture.py', 'r') as f:  
    lines = f.readlines()  
for i, line in enumerate(lines):  
    if 'def grab_rect' in line:  
        print(f'Line {i}: {repr(line)}')  
        break  
