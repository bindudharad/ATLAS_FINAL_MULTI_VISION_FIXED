import subprocess, sys, os  
exe = r'C:\Program Files\Python313\python.exe'  
print('exists:', os.path.exists(exe))  
if os.path.exists(exe):  
    r = subprocess.run([exe, '-c', 'import sys; print(sys.version); import numpy; print(numpy.__version__ if \"numpy\" in sys.modules else \"not installed\")'], capture_output=True, text=True, timeout=30)  
    print('stdout:', r.stdout)  
    print('stderr:', r.stderr)  
    print('returncode:', r.returncode)  
