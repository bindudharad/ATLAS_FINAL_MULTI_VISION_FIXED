import os  
for root, dirs, files in os.walk(r'C:\Program Files\Python313'):  
    for f in files:  
        print(os.path.join(root, f))  
