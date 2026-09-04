content = open('atlas/vision/capture.py', 'r', encoding='utf-8').read()  
start = content.find('def grab_rect(self, left: int, top: int, width: int, height: int)')  
print('Start:', start)  
print('Context after start:', repr(content[start:start+200])) 
