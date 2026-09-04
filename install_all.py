import subprocess, sys  
deps = ['numpy', 'mss', 'pillow', 'psutil', 'pywin32', 'python-dotenv', 'loguru', 'pydantic', 'requests', 'playwright']  
for dep in deps:  
    print(f'Installing {dep}...')  
    r = subprocess.run([sys.executable, '-m', 'pip', 'install', dep, '--break-system-packages'], capture_output=True, text=True, timeout=120)  
    if r.returncode == 0:  
        print(f'  {dep}: OK')  
    else:  
        print(f'  {dep}: FAILED')  
        print(f'  stderr: {r.stderr[:200]}')  
