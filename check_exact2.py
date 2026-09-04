import os  
p = r'C:\Users\Bindudhara D\AppData\Local\Programs\Python'  
print('exists:', os.path.exists(p))  
if os.path.exists(p): print(os.listdir(p))  
