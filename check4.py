with open('atlas/vision/capture.py', 'r') as f:  
    content = f.read()  
print('grab_rect count:', content.count('def grab_rect'))  
print('First grab_rect:', content.find('def grab_rect'))  
print(repr(content[2200:2400])) 
