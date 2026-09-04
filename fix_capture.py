with open('atlas/vision/capture.py', 'r') as f:  
    content = f.read()  
  
# Find the start of the broken grab_rect  
start = content.find('def grab_rect')  
# Find the next method after it  
end = content.find('def _grab_mss', start)  
broken = content[start:end]  
  
# Find self._fallback_until = 0.0 which is the last line of __init__  
init_end = content.rfind('self._fallback_until = 0.0', 0, start)  
  
# The section to replace is from init_end to end  
to_replace = content[init_end:end]  
print('To replace:', repr(to_replace))  
  
# Now create the fixed version  
fixed = '''self._fallback_until = 0.0\n\n    def grab_rect(self, left: int, top: int, width: int, height: int) -        \\\"\\\"\\\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\\\"\\\"\\\"\n        # Use BitBlt directly to avoid mss side effects\n        return self._grab_bitblt(left, top, width, height)\n\n    def _grab_mss'''  
  
new_content = content[:init_end] + fixed + content[end:]  
  
with open('atlas/vision/capture.py', 'w') as f:  
    f.write(new_content)  
print('Fixed!')  
