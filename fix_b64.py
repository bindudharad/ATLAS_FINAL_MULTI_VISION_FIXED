import base64  
with open('capture_b64.txt', 'r') as f:  
    encoded = f.read()  
content = base64.b64decode(encoded).decode('utf-8')  
# Fix the grab_rect method in the base64 content  
content = content.replace('    def grab_rect(self, left: int, top: int, width: int, height: int) -        \\\"\\\"\\\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\\\"\\\"\\\"', '    def grab_rect(self, left: int, top: int, width: int, height: int) -        \\\"\\\"\\\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\\\"\\\"\\\"')  
content = content.replace('        # Use BitBlt directly to avoid mss side effects\\n\\n        # Use BitBlt directly to avoid mss side effects', '        # Use BitBlt directly to avoid mss side effects')  
new_encoded = base64.b64encode(content.encode('utf-8')).decode('utf-8')  
with open('capture_b64.txt', 'w') as f:  
    f.write(new_encoded)  
print('Fixed base64')  
