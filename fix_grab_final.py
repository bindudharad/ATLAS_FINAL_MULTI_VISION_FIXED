with open('atlas/vision/capture.py', 'r') as f:  
    content = f.read()  
content = content.replace('    def grab_rect(self, left: int, top: int, width: int, height: int) -        \\\"\\\"\\\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\\\"\\\"\\\"', '    def grab_rect(self, left: int, top: int, width: int, height: int) -        \\\"\\\"\\\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\\\"\\\"\\\"')  
content = content.replace('        # Use BitBlt directly to avoid mss side effects\\n\\n        # Use BitBlt directly to avoid mss side effects', '        # Use BitBlt directly to avoid mss side effects')  
with open('atlas/vision/capture.py', 'w') as f:  
    f.write(content)  
print('Fixed')  
