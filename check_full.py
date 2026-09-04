with open('atlas/vision/capture.py', 'rb') as f:  
    data = f.read()  
print(len(data))  
# Find the actual line  
idx = data.find(b'executable')  
if idx  
    print(data[idx:idx+80])  
