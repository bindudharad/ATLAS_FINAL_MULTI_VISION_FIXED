import sys  
for f in ['atlas/workflow/scroller.py', 'tests/test_scroller.py', 'atlas/core/safety.py']:  
    with open(f, 'rb') as fp:  
        content = fp.read(10)  
        print(f'{f}: {list(content[:10])}')  
