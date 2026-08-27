
import re

# Read the file
with open("C:/Users/Bindudhara D/Downloads/ATLAS_FINAL_MULTI_VISION_FIXED/DataEntry - Copy/atlas/mapping/uia_map.py", "r") as f:
    content = f.read()

old_func = """def _source_label_nodes(left_labels: list[UiaNode]) -> list[UiaNode]:
    \"\"\"Return genuine source-panel label nodes, excluding VALUES and headers.

    The source panel renders every record field as a label text node whose
    value is a sibling text node on the same row (same parent group, small
    gap). Those right-side siblings - numeric IDs, codes, dates, names and the
    like - are VALUES, not labels, and must never become mapping candidates.
    Wide nodes are section headers (e.g. \"Member Basic Information\") and are
    excluded too.
    \"\"\"
    candidates = [n for n in left_labels or [] if n.rect is not None]
    if not candidates:
        return []
    rows = _group_same_row(candidates)
    value_ids: set[int] = set()
    for row in rows:
        row = _drop_outlier_parents(row)
        row.sort(key=lambda n: n.rect.left)
        for i in range(len(row) - 1):
            left_node, right_node = row[i], row[i + 1]
            if id(left_node) in value_ids:
                continue
            if left_node.rect.width > 120:
                continue
            gap = right_node.rect.left - left_node.rect.right
            if gap <= 170 and _same_parent_group(left_node, right_node):
                value_ids.add(id(right_node))
    result: list[UiaNode] = []
    for node in left_labels or []:
        if node.rect is None:
            continue
        if id(node) in value_ids:
            continue
        if node.rect.width > 120:
            continue
        result.append(node)
    return result"""

new_func = """def _source_label_nodes(left_labels: list[UiaNode]) -> list[UiaNode]:
    \"\"\"Return genuine source-panel label nodes, excluding VALUES and headers.

    The source panel renders every record field as a label text node whose
    value is a sibling text node on the same row (same parent group, small
    gap). Those right-side siblings - numeric IDs, codes, dates, names and the
    like - are VALUES, not labels, and must never become mapping candidates.
    Wide nodes are section headers (e.g. \"Member Basic Information\") and are
    excluded too.
    
    CRITICAL: Only labels from MEMBER sections are valid source fields.
    Labels from \"Project Details\", \"Shift Details\", and other ignored sections
    must be excluded even if they geometrically look like label-value pairs.
    \"\"\"
    candidates = [n for n in left_labels or [] if n.rect is not None]
    if not candidates:
        return []
    rows = _group_same_row(candidates)
    value_ids: set[int] = set()
    for row in rows:
        row = _drop_outlier_parents(row)
        row.sort(key=lambda n: n.rect.left)
        for i in range(len(row) - 1):
            left_node, right_node = row[i], row[i + 1]
            if id(left_node) in value_ids:
                continue
            if left_node.rect.width > 120:
                continue
            gap = right_node.rect.left - left_node.rect.right
            if gap <= 170 and _same_parent_group(left_node, right_node):
                value_ids.add(id(right_node))
    result: list[UiaNode] = []
    for node in left_labels or []:
        if node.rect is None:
            continue
        if id(node) in value_ids:
            continue
        if node.rect.width > 120:
            continue
        # Filter by section: only member-section labels are valid source fields
        node_section = section_of(node.name)
        if node_section == \"ignored\":
            continue  # Skip Project Details, Shift Details, etc.
        if node_section is None:
            continue  # Skip unrecognized sections
        result.append(node)
    return result"""

if old_func in content:
    content = content.replace(old_func, new_func)
    print("Fixed _source_label_nodes")
else:
    print("OLD FUNC NOT FOUND - searching...")
    match = re.search(r"def _source_label_nodes\\(.*?\\n    return result", content, re.DOTALL)
    if match:
        print("Found with regex")
        content = content[:match.start()] + new_func + content[match.end():]
        print("Replaced via regex")
    else:
        print("Still not found")

with open("C:/Users/Bindudhara D/Downloads/ATLAS_FINAL_MULTI_VISION_FIXED/DataEntry - Copy/atlas/mapping/uia_map.py", "w") as f:
    f.write(content)

