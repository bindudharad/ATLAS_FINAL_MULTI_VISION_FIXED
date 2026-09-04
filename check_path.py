import os  
for p in os.environ.get('PATH', '').split(';'):  
    if 'python' in p.lower():  
        print(p)  
