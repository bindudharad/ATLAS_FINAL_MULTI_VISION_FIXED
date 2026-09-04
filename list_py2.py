import os  
for f in os.listdir(r'C:\Program Files\Python313\Lib\site-packages'):  
    if 'numpy' in f.lower(): print(f)  
