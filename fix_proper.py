with open('atlas/vision/capture.py', 'rb') as f:  
    data = f.read()  
# Find the exact broken section  
start = data.find(b'def grab_rect')  
end = data.find(b'def _grab_mss', start)  
broken = data[start:end]  
print('Broken:', broken)  
  
# Find init end  
init_end = data.rfind(b'self._fallback_until = 0.0', 0, start)  
# The section to replace is from init_end to end  
to_replace = data[init_end:end]  
print('To replace:', to_replace)  
  
# Build fixed section  
fixed = b'self._fallback_until = 0.0\r\n\r\n    def grab_rect(self, left: int, top: int, width: int, height: int) -        \"\"\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\"\"\"\r\n        # Use BitBlt directly to avoid mss side effects\r\n        return self._grab_bitblt(left, top, width, height)\r\n\r\n    def _grab_mss'  
  
new_data = data[:init_end] + fixed + data[end:]  
with open('atlas/vision/capture.py', 'wb') as f:  
    f.write(new_data)  
print('Fixed!')  
