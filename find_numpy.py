import sys  
import os  
for path in sys.path:  
    if os.path.exists(path):  
        for root, dirs, files in os.walk(path):  
            if 'numpy' in dirs or any('numpy' in f for f in files):  
                print('FOUND numpy at:', root)  
