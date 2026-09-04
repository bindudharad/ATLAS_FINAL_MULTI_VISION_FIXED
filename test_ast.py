import ast, os  
p = os.path.join('atlas', 'vision', 'capture.py')  
with open(p, 'r') as f:  
    content = f.read()  
try:  
    ast.parse(content)  
    print('SYNTAX OK')  
except SyntaxError as e:  
    print('SYNTAX ERROR:', e)  
