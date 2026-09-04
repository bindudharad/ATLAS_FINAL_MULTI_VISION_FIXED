import base64  
with open('capture_b64.txt', 'r') as f:  
    encoded = f.read()  
content = base64.b64decode(encoded).decode('utf-8')  
# The grab_rect method is malformed - find and replace the whole block  
old_block = '''        def grab_rect(self, left: int, top: int, width: int, height: int) -        \\\"\\\"\\\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\\\"\\\"\\\"\n\n\n        # Use BitBlt directly to avoid mss side effects\r\n        # Use BitBlt directly to avoid mss side effects\r\n        return self._grab_bitblt(left, top, width, height)'''  
new_block = '''    def grab_rect(self, left: int, top: int, width: int, height: int) -        \\\"\\\"\\\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\\\"\\\"\\\"\n        # Use BitBlt directly to avoid mss side effects\n        return self._grab_bitblt(left, top, width, height)'''  
content = content.replace(old_block, new_block)  
new_encoded = base64.b64encode(content.encode('utf-8')).decode('utf-8')  
with open('capture_b64.txt', 'w') as f:  
    f.write(new_encoded)  
print('Fixed')  
