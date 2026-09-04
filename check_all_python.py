import subprocess  
import os  
paths = [r'C:\Program Files\Python313', r'C:\Program Files\Python312', r'C:\Program Files\Python311', r'C:\Program Files\Python310', r'C:\Python313', r'C:\Python312', r'C:\Python311', r'C:\Python310', r'C:\msys64\ucrt64\bin\python.exe']  
for p in paths:  
    if os.path.exists(p): print('FOUND:', p)  
    else: print('NOT FOUND:', p)  
