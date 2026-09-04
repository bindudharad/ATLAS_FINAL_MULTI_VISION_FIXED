import os  
for k, v in os.environ.items():  
    if 'python' in k.lower() or 'path' in k.lower():  
        print(k, ':', v[:200])  
