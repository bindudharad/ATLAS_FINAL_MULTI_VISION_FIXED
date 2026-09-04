import sys  
with open('tests/test_scroller.py', 'r') as f:  
    lines = f.readlines()  
for i, line in enumerate(lines[:10]):  
    print(f'{i+1}: {repr(line)}')  
