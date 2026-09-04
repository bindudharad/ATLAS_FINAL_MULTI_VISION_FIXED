with open('atlas/vision/capture.py', 'r') as f:  
    lines = f.readlines()  
for i, line in enumerate(lines[70:90]):  
    print(f'Line {i+71}: {line.rstrip()}')  
