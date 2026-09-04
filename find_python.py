import os  
import subprocess  
# Check if there's a system Python with packages  
paths_to_check = [  
    r'C:\Python313', r'C:\Python312', r'C:\Python311', r'C:\Python310',  
    r'C:\Program Files\Python312', r'C:\Program Files\Python311', r'C:\Program Files\Python310',  
    r'C:\Users\Bindudhara D\AppData\Local\Programs\Python\Python313',  
    r'C:\Users\Bindudhara D\AppData\Local\Programs\Python\Python312',  
    r'C:\Users\Bindudhara D\AppData\Local\Programs\Python\Python311',  
    r'C:\Users\Bindudhara D\AppData\Local\Programs\Python\Python310',  
]  
for p in paths_to_check:  
    exe = os.path.join(p, 'python.exe')  
    if os.path.exists(exe):  
        print('FOUND:', exe)  
        r = subprocess.run([exe, '-c', 'import sys; print(sys.version)'], capture_output=True, text=True)  
        print('  version:', r.stdout.strip())  
        r2 = subprocess.run([exe, '-c', 'import numpy, mss, PIL, psutil, win32gui; print(\"OK\")'], capture_output=True, text=True)  
        if r2.returncode == 0:  
            print('  ALL DEPS OK')  
        else:  
            print('  missing deps:', r2.stderr.strip()[:100])  
