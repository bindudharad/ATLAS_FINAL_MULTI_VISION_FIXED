with open('capture_text.txt', 'r', encoding='utf-8') as f:  
    content = f.read()  
# Fix 1: grab_rect method signature  
content = content.replace(  
'    def grab_rect(self, left: int, top: int, width: int, height: int) -        \\\"\\\"\\\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\\\"\\\"\\\"',  
'    def grab_rect(self, left: int, top: int, width: int, height: int) -        \\\"\\\"\\\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\\\"\\\"\\\"')  
# Fix 2: Remove duplicate comment line  
content = content.replace(  
'        # Use BitBlt directly to avoid mss side effects\\n\\n        # Use BitBlt directly to avoid mss side effects',  
'        # Use BitBlt directly to avoid mss side effects')  
with open('atlas/vision/capture.py', 'w', encoding='utf-8') as f:  
    f.write(content)  
print('Fixed')  
