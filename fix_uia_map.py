import re

with open("uia_map_full.py", "r") as f:
    content = f.read()

# Fix 1: _associate_right_field_labels - allow labels at same x position (right panel)
old_func = """def _associate_right_field_labels(right_fields, text_nodes):
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
    return label_map"""

new_func = """def _associate_right_field_labels(right_fields, text_nodes):
    \"\"\"Associate each right field with its nearest left label text node.
    
    For each right field (editable control), find the closest text node
    to its LEFT (or same x position on right panel) that shares similar 
    Y position (same row). Returns a dict mapping control automation_id -> label text.
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
            # Must be to the left of or aligned with the field (right panel labels share x)
            # Allow text.rect.right <= fx + 10 to accommodate right-panel labels at same x
            if text.rect.right > fx + 10:
                continue
            # Same row (vertical tolerance)
            ty = text.rect.center[1]
            if abs(ty - fy) > 20:  # 20px vertical tolerance
                continue
            # Horizontal distance (prefer closest - can be 0 for right-panel labels)
            dist = fx - text.rect.right
            if dist < 0:
                dist = 0
            if dist < best_dist:
                # Skip if this looks like a value (not a label)
                if is_likely_value(text.name):
                    continue
                best_label = _clean_label(text.name)
                best_dist = dist
        if best_label:
            label_map[field.automation_id] = best_label
    return label_map"""

if old_func in content:
    content = content.replace(old_func, new_func)
    print("Fixed _associate_right_field_labels")
else:
    print("OLD FUNC NOT FOUND")
    # Debug: find the actual function
    idx = content.find("def _associate_right_field_labels")
    if idx >= 0:
        print(content[idx:idx+500])
        
with open("uia_map_full.py", "w") as f:
    f.write(content)
