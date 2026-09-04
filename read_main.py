import sys  
with open('main.py', 'r') as f:  
    lines = f.readlines()  
for i, line in enumerate(lines[:50]):  
    print(f'{i+1}: {line.rstrip()}')  
