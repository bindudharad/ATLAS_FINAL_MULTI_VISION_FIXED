import sys  
import subprocess  
subprocess.run([sys.executable, '-m', 'pip', 'install', 'numpy', 'mss', 'pillow', 'psutil', 'pywin32', '--break-system-packages'], check=False)  
