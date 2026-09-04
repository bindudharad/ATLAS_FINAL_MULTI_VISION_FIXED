import subprocess, sys  
r = subprocess.run(['powershell', '-Command', 'python -c \"import sys; print(sys.version); import numpy; print(numpy.__version__)\"'], capture_output=True, text=True, timeout=30)  
print('stdout:', r.stdout)  
print('stderr:', r.stderr)  
print('returncode:', r.returncode)  
