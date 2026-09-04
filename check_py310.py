import os, subprocess  
exe = r'C:\Users\Bindudhara D\AppData\Local\Programs\Python\Python310\python.exe'  
print('exists:', os.path.exists(exe))  
r = subprocess.run([exe, '-c', 'import sys; print(sys.version)'], capture_output=True, text=True)  
print('stdout:', r.stdout)  
print('stderr:', r.stderr)  
