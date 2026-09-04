import sys  
mods = ['numpy', 'mss', 'PIL', 'psutil', 'win32gui', 'win32api', 'win32con', 'dotenv', 'loguru', 'pydantic', 'requests', 'playwright']  
for mod in mods:  
    try:  
        __import__(mod)  
        print(f'{mod}: OK')  
    except ImportError as e:  
        print(f'{mod}: MISSING - {e}')  
