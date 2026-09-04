import subprocess, sys  
r = subprocess.run([r'C:\Users\Bindudhara D\Downloads\ATLAS_FINAL_MULTI_VISION_FIXED\DataEntry - Copy\venv\bin\python.exe', '-m', 'pytest', 'tests/test_source_observer.py', '-v', '--no-header'], capture_output=True, text=True, timeout=120)  
print('stdout:', r.stdout)  
print('stderr:', r.stderr)  
print('returncode:', r.returncode)  
