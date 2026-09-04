with open('atlas/vision/capture.py', 'r') as f:  
    content = f.read()  
  
# Fix the malformed docstring  
content = content.replace('    def grab_rect(self, left: int, top: int, width: int, height: int) -        \\\"\\\"\\\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\\\"\\\"\\\"', '    def grab_rect(self, left: int, top: int, width: int, height: int) -        \\\"\\\"\\\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\\\"\\\"\\\"')  
  
with open('atlas/vision/capture.py', 'w') as f:  
    f.write(content)  
print('Fixed docstring!') 
