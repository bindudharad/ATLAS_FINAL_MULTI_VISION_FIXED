with open('atlas/vision/capture.py', 'r') as f:  
    content = f.read()  
  
import re  
  
# Find ScreenGrabber class  
pattern = r'(class ScreenGrabber:.*?)(\nclass WindowGeometry:)'  
match = re.search(pattern, content, re.DOTALL)  
if match:  
    print('Found ScreenGrabber class')  
    print(match.group(1)[:500])  
else:  
    print('Not found') 
