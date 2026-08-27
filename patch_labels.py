import re

with open(r"C:\Users\Bindudhara D\Downloads\ATLAS_FINAL_MULTI_VISION_FIXED\DataEntry - Copy\atlas\mapping\uia_map.py", "r") as f:
    content = f.read()

# Find the end of _clean_label function
pos = content.find("def _clean_label(text: str) -> str:")
if pos > 0:
    i = pos
    while i < len(content) - 3:
        if content[i:i+2] == "\n\n":
            insert_pos = i + 2
            break
        i += 1
    else:
        insert_pos = len(content)

label_assoc_code = """

def _associate_right_field_labels(right_fields, text_nodes):
    \"\"\"Associate each right field with its nearest left label text node.
    
    For each right field (editable control), find the closest text node
    to its LEFT that shares similar Y position (same row).
    Returns a dict mapping control automation_id -> label text.
    \"\"\"
    label_map = {}
    for field in right_fields:
        if field.rect is None:
            continue
        fy = field.rect.center[1]
        fx = field.rect.left
        best_label = None
        best_dist = float("inf")
        for text in text_nodes:
            if text.rect is None:
                continue
            # Must be to the left of the field
            if text.rect.right >= fx:
                continue
            # Same row (vertical tolerance)
            ty = text.rect.center[1]
            if abs(ty - fy) > 20:  # 20px vertical tolerance
                continue
            # Horizontal distance (prefer closest)
            dist = fx - text.rect.right
            if 0 < dist < best_dist:
                # Skip if this looks like a value (not a label)
                if is_likely_value(text.name):
                    continue
                best_label = _clean_label(text.name)
                best_dist = dist
        if best_label:
            label_map[field.automation_id] = best_label
    return label_map
"""

content = content[:insert_pos] + label_assoc_code + content[insert_pos:]

with open(r"C:\Users\Bindudhara D\Downloads\ATLAS_FINAL_MULTI_VISION_FIXED\DataEntry - Copy\atlas\mapping\uia_map.py", "w") as f:
    f.write(content)
print("Added _associate_right_field_labels")
