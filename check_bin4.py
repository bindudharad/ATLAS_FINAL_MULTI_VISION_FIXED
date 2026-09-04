with open('atlas/vision/capture.py', 'rb') as f:  
    data = f.read()  
idx = data.find(b'split(')  
if idx  
    print(data[idx:idx+30])  
else:  
    print('Not found')  
