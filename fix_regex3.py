with open('atlas/vision/capture.py', 'r') as f:  
    content = f.read()  
  
import re  
  
match = re.search(r'(class ScreenGrabber:.*?)(\nclass WindowGeometry:)', content, re.DOTALL)  
if match:  
    print(match.group(1)) 
