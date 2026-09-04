import os  
import subprocess  
paths = [  
    r'C:\Users\Bindudhara D\AppData\Local\Programs\Python\Python313',  
    r'C:\Users\Bindudhara D\AppData\Local\Programs\Python\Python312',  
    r'C:\Users\Bindudhara D\AppData\Local\Programs\Python\Python311',  
    r'C:\Users\Bindudhara D\AppData\Local\Programs\Python\Python310',  
]  
for p in paths:  
    exe = os.path.join(p, 'python.exe')  
    if os.path.exists(exe):  
        print('FOUND:', exe)  
        r = subprocess.run([exe, '-c', 'import sys; print(sys.version)'], capture_output=True, text=True)  
        print('  version:', r.stdout.strip())  
