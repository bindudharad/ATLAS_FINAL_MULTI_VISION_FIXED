with open('atlas/vision/capture.py', 'rb') as f:  
    data = f.read()  
lines = data.decode('utf-8').splitlines()  
for i in range(325, 335):  
    print(i+1, repr(lines[i]))  
