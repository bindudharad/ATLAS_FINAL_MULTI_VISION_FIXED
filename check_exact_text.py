content = open('atlas/vision/capture.py', 'r', encoding='utf-8').read() 
idx = content.find('def grab_rect')  
print(repr(content[idx:idx+150])) 
