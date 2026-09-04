content = open('atlas/vision/capture.py', 'r', encoding='utf-8').read()  
bad = 'def grab_rect(self, left: int, top: int, width: int, height: int) -        \\\\\\\\\\\\\"\\\\\\\\\\\\\"\\\\\\\\\\\\\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\\\\\\\\\\\\\"\\\\\\\\\\\\\"\\\\\\\\\\\\\"'  
good = 'def grab_rect(self, left: int, top: int, width: int, height: int) -        \\\"\\\"\\\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\\\"\\\"\\\"'  
print('Bad found:', bad in content)  
new_content = content.replace(bad, good)  
open('atlas/vision/capture.py', 'w', encoding='utf-8').write(new_content)  
print('Fixed') 
