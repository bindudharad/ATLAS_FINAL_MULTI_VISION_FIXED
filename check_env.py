import os  
import subprocess  
candidates = [  
    r'C:\Program Files\Python313',  
    r'C:\Program Files\Python312',  
    r'C:\Program Files\Python311',  
    r'C:\Program Files\Python310',  
    r'C:\Python313',  
    r'C:\Python312',  
    r'C:\Python311',  
    r'C:\Python310',  
    r'C:\msys64\ucrt64\bin\python.exe',  
]  
for p in candidates:  
    exe = os.path.join(p, 'python.exe') if not p.endswith('.exe') else p  
    if os.path.exists(exe):  
        r = subprocess.run([exe, '-c', 'import numpy, mss, PIL, psutil, win32gui, win32api, win32con, dotenv, loguru, pydantic, requests, playwright; print(\"ALL OK\")'], capture_output=True, text=True)  
        if r.returncode == 0:  
            print('FOUND WITH ALL DEPS:', exe)  
        else:  
            print('FOUND BUT MISSING:', exe)  
            print('  ', r.stderr[:200])  
