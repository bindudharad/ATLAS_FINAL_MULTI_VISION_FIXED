with open('atlas/vision/capture.py', 'rb') as f:  
    content = f.read()  
  
idx = content.find(b'height: int) -')  
if idx  
    # Replace from 'def grab_rect' to the end of docstring  
    start = content.rfind(b'def grab_rect', 0, idx)  
    if start  
        # Find the end of the docstring (triple quotes)  
