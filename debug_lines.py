with open('atlas/vision/capture.py', 'r') as f:  
    lines = f.readlines()  
for i, line in enumerate(lines[70:95]):  
    print(f'{i+70}: {repr(line.rstrip())}') 
