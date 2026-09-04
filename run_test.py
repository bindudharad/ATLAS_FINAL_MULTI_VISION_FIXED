import subprocess, sys  
r = subprocess.run([sys.executable, '-m', 'pytest', 'tests/test_source_observer.py', '-v', '--no-header'], capture_output=True, text=True, timeout=120, cwd=r'C:\Users\Bindudhara D\Downloads\ATLAS_FINAL_MULTI_VISION_FIXED\DataEntry - Copy')  
print('stdout:', r.stdout)  
print('stderr:', r.stderr)  
print('returncode:', r.returncode)  
