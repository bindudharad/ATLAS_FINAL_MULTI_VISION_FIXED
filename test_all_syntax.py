import sys  
import ast  
import os  
project_root = r'C:\Users\Bindudhara D\Downloads\ATLAS_FINAL_MULTI_VISION_FIXED\DataEntry - Copy'  
errors = []  
for root, dirs, files in os.walk(os.path.join(project_root, 'atlas')):  
    for f in files:  
        if f.endswith('.py'):  
            p = os.path.join(root, f)  
            try:  
                with open(p, 'r') as fp:  
                    ast.parse(fp.read())  
            except SyntaxError as e:  
                errors.append((p, str(e)))  
for root, dirs, files in os.walk(os.path.join(project_root, 'tests')):  
    for f in files:  
        if f.endswith('.py'):  
            p = os.path.join(root, f)  
            try:  
                with open(p, 'r') as fp:  
                    ast.parse(fp.read())  
            except SyntaxError as e:  
                errors.append((p, str(e)))  
if errors:  
    for p, e in errors:  
        print(f'SYNTAX ERROR: {p} - {e}')  
else:  
    print('ALL PYTHON FILES: SYNTAX OK')  
