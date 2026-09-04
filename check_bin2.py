with open('atlas/vision/capture.py', 'rb') as f:  
    data = f.read()  
idx = data.find(b'split')  
print(data[idx:idx+50])  
