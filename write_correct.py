correct = open('capture_text.txt', 'r', encoding='utf-8').read()  
correct = correct.replace('    def grab_rect(self, left: int, top: int, width: int, height: int) -        \\\"\\\"\\\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\\\"\\\"\\\"', '    def grab_rect(self, left: int, top: int, width: int, height: int) -        \\\"\\\"\\\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\\\"\\\"\\\"')  
correct = correct.replace('        # Use BitBlt directly to avoid mss side effects\\n\\n        # Use BitBlt directly to avoid mss side effects', '        # Use BitBlt directly to avoid mss side effects')  
correct = correct.replace('        def grab_rect', '    def grab_rect')  
with open('atlas/vision/capture.py', 'w', encoding='utf-8') as f:  
    f.write(correct)  
print('Fixed')  
