import subprocess, sys  
r = subprocess.run([sys.executable, '-m', 'ensurepip', '--upgrade'], capture_output=True, text=True, timeout=60)  
print('returncode:', r.returncode)  
print('stdout:', r.stdout[:500])  
print('stderr:', r.stderr[:500])  
