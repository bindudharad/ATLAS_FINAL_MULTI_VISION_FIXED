import sys  
import os  
for f in ['atlas/workflow/scroller.py', 'tests/test_scroller.py', 'atlas/core/safety.py']:  
    with open(f, 'rb') as fp:  
        content = fp.read()  
    if content.startswith(b'\\xef\\xbb\\xbf'):  
        content = content[3:]  
        with open(f, 'wb') as fp:  
            fp.write(content)  
        print(f'Fixed BOM: {f}')  
    else:  
        print(f'No BOM: {f}')  
