content = open('atlas/vision/capture.py', 'r', encoding='utf-8').read()  
start = content.find('def grab_rect(self, left: int, top: int, width: int, height: int)')  
end = content.find('\n        # Use BitBlt', start)  
new_method = '    def grab_rect(self, left: int, top: int, width: int, height: int) -        \"\"\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\"\"\"\n        # Use BitBlt directly to avoid mss side effects\n'  
content = content[:start] + new_method + content[end:]  
open('atlas/vision/capture.py', 'w', encoding='utf-8').write(content)  
print('Fixed') 
