with open('atlas/vision/capture.py', 'rb') as f:  
    data = f.read()  
idx = data.find(b'split')  
while True:  
    next_idx = data.find(b'split', idx + 1)  
    if next_idx == -1:  
        break  
    idx = next_idx  
print(list(data[idx:idx+40]))  
