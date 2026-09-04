import re

with open("atlas/mapping/uia_map.py", "r", encoding="utf-8") as f:
    content = f.read()

idx = content.find("ocr_texts = [getattr(line, \"text\", \"\") for line in ocr_lines if getattr(line, \"text\", \"\")]")
if idx < 0:
    print("NOT FOUND")
else:
    end_idx = content.find("consumed:", idx)
    if end_idx < 0:
        print("END NOT FOUND")
    else:
