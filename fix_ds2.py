with open('atlas/vision/capture.py', 'r') as f:  
    content = f.read()  
  
old = '    def grab_rect(self, left: int, top: int, width: int, height: int) -        \\\"\\\"\\\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\\\"\\\"\\\"'  
new = '    def grab_rect(self, left: int, top: int, width: int, height: int) -        \\\"\\\"\\\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\\\"\\\"\\\"'  
content = content.replace(old, new)  
with open('atlas/vision/capture.py', 'w') as f:  
    f.write(content)  
print('Fixed!') 
