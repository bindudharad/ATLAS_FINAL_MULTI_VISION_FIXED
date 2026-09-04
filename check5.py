with open('atlas/vision/capture.py', 'r') as f:  
    content = f.read()  
import re  
match = re.search(r'class ScreenGrabber:.*?(?=\nclass WindowGeometry:)', content, re.DOTALL)  
if match:  
    print('Match found, length:', len(match.group(0)))  
    print(match.group(0)[:200])  
else:  
    print('No match') 
