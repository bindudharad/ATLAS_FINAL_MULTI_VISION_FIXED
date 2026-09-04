from pathlib import Path 
c = Path('atlas/vision/capture.py').read_text(encoding='utf-8') 
i = c.find(\"grab_rect\")  
print(f\"Index: {i}\")  
print(repr(c[i:i+200])) 
