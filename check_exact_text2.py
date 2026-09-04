content = open('atlas/vision/capture.py', 'r', encoding='utf-8').read()  
idx = content.find('def grab_rect')  
print('Length of match:', len(content[idx:idx+120]))  
for i, ch in enumerate(content[idx:idx+120]):  
    print(f'{idx+i}: {ord(ch):3d} = {repr(ch)}') 
