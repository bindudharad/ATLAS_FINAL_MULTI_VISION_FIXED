import os  
import subprocess  
paths = [  
    r'C:\Users\Bindudhara D\AppData\Local\Programs\Python\Launcher',  
    r'C:\Users\Bindudhara D\AppData\Local\Python',  
    r'C:\Users\Bindudhara D\AppData\Local\Programs\Python\Python310',  
]  
for p in paths:  
    if os.path.exists(p):  
        print('DIR:', p)  
        for root, dirs, files in os.walk(p):  
            for f in files:  
                if f.endswith('.exe'):  
                    print('  EXE:', os.path.join(root, f))  
