import sys  
for f in ['atlas/workflow/scroller.py', 'tests/test_scroller.py', 'atlas/core/safety.py']:  
    with open(f, 'rb') as fp:  
        content = fp.read()  
    if content.startswith(bytes([0xef, 0xbb, 0xbf])):  
        content = content[3:]  
        with open(f, 'wb') as fp:  
            fp.write(content)  
        print('Fixed BOM:', f)  
    else:  
        print('No BOM:', f)  
