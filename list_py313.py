import os  
p = r'C:\Program Files\Python313'  
print('Dir contents:', os.listdir(p))  
for root, dirs, files in os.walk(p):  
    for f in files:  
        print(os.path.join(root, f))  
