import os  
for root, dirs, files in os.walk(r'C:\Program Files\Python313'):  
    for f in files:  
        if f.endswith('.exe'): print(os.path.join(root, f))  
