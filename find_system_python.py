import os  
import subprocess  
paths = [  
    r'C:\Python313', r'C:\Python312', r'C:\Python311', r'C:\Python310',  
    r'C:\Program Files\Python313', r'C:\Program Files\Python312', r'C:\Program Files\Python311', r'C:\Program Files\Python310',  
]  
for p in paths:  
    exe = os.path.join(p, 'python.exe')  
    if os.path.exists(exe):  
        print('FOUND:', exe)  
        r = subprocess.run([exe, '-c', 'import sys; print(sys.version)'], capture_output=True, text=True)  
        print('  version:', r.stdout.strip())  
