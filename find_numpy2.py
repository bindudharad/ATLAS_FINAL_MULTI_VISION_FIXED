import sys  
import os  
for path in sys.path:  
    if os.path.exists(path):  
        for root, dirs, files in os.walk(path):  
            if 'numpy' in dirs:  
                print('FOUND numpy dir at:', os.path.join(root, 'numpy'))  
