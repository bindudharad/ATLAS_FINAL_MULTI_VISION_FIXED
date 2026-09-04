with open('atlas/vision/capture.py', 'rb') as f:  
    content = f.read()  
bad = b'def grab_rect(self, left: int, top: int, width: int, height: int) -        \"\"\"' >> fix_bytes_final.py && echo good = b'def grab_rect(self, left: int, top: int, width: int, height: int) -> np.ndarray:\n        \"\"\"'  
if bad in content:  
    content = content.replace(bad, good)  
    with open('atlas/vision/capture.py', 'wb') as f:  
        f.write(content)  
    print('Fixed')  
else:  
    print('Not found') 
