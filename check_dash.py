with open('atlas/vision/capture.py', 'rb') as f:  
    content = f.read()  
old = b'    def grab_rect(self, left: int, top: int, width: int, height: int) -        \\\"\\\"\\\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\\\"\\\"\\\"'  
print('Old in content:', old in content)  
old_crlf = old + b'\r\n'  
print('Old with CRLF in content:', old_crlf in content)  
idx = content.find(b'height: int) -')  
print('Found dash at:', idx)  
if idx  
    print(repr(content[idx:idx+100])) 
