import re

with open(r"C:\Users\Bindudhara D\Downloads\ATLAS_FINAL_MULTI_VISION_FIXED\DataEntry - Copy\atlas\mapping\uia_map.py", "r") as f:
    content = f.read()

# After right_fields are created and text_nodes are available, associate labels
# Find the line: "right_fields = [self._attach_declared(n, hwnd) for n in right_fields]"
# and add label association after it

old_code = """        right_fields = [self._attach_declared(n, hwnd) for n in right_fields]

        # NOTE: no scrolling happens here, on purpose."""

new_code = """        right_fields = [self._attach_declared(n, hwnd) for n in right_fields]

        # CRITICAL FIX: Associate right fields with their left-side labels
        # The UIA "name" of ComboBoxes/Edits is the CURRENT VALUE, not the label!
        # We must find the label text node to the LEFT of each control.
        if nodes is not None:
            text_nodes_for_labels = self._backend.text_nodes(hwnd, nodes=nodes)
        else:
            text_nodes_for_labels = self._backend.text_nodes(hwnd)
        field_labels = _associate_right_field_labels(right_fields, text_nodes_for_labels)
        # Store the label on each node for later use
        for field in right_fields:
            if field.automation_id in field_labels:
                field.name = field_labels[field.automation_id]

        # NOTE: no scrolling happens here, on purpose."""

content = content.replace(old_code, new_code)

with open(r"C:\Users\Bindudhara D\Downloads\ATLAS_FINAL_MULTI_VISION_FIXED\DataEntry - Copy\atlas\mapping\uia_map.py", "w") as f:
    f.write(content)
print("Integrated label association")
