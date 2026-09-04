import pkgutil  
pkgs = [mod.name for mod in pkgutil.iter_modules()]  
print([n for n in pkgs if n in ['numpy', 'mss', 'PIL', 'psutil', 'win32gui', 'win32api', 'win32', 'win32con']])  
