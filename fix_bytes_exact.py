with open('atlas/vision/capture.py', 'rb') as f:  
    content = f.read()  
bad = b'def grab_rect(self, left: int, top: int, width: int, height: int) -        \\\\\\\\\\\\\"\\\\\\\\\\\\\"\\\\\\\\\\\\\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\\\\\\\\\\\\\"\\\\\\\\\\\\\"\\\\\\\\\\\\\"\\r\\n'  
good = b'def grab_rect(self, left: int, top: int, width: int, height: int) -        \\\"\\\"\\\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\\\"\\\"\\\"\\r\\n'  
print('Bad found:', bad in content)  
new_content = content.replace(bad, good)  
with open('atlas/vision/capture.py', 'wb') as f:  
    f.write(new_content)  
print('Fixed') 
