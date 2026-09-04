import sys  
sys.path.insert(0, r'C:\Users\Bindudhara D\Downloads\ATLAS_FINAL_MULTI_VISION_FIXED\DataEntry - Copy')  
# Just check if the syntax is correct for the key modules  
import ast  
modules = ['atlas/vision/capture.py', 'atlas/vision/manager.py', 'atlas/observe/source_observer.py', 'atlas/mapping/uia_map.py']  
for m in modules:  
    try:  
        with open(m, 'r') as f:  
            ast.parse(f.read())  
        print(f'{m}: SYNTAX OK')  
    except SyntaxError as e:  
        print(f'{m}: SYNTAX ERROR - {e}')  
