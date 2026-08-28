import re
with open("tests/test_uia_flow.py", "r") as f:
    content = f.read()

old_text = "    text = [\\n        UiaNode(name=\\"Member Name\\", control_type=\\"Text\\", rect=BBox(585, 186, 80, 22),\\n                parent={\\"name\\": \\"Member Basic Information\\", \\"control_type\\": \\"Group\\"}),\\n        UiaNode(name=\\"Application No\\", control_type=\\"Text\\", rect=BBox(585, 230, 140, 22),\\n                parent={\\"name\\": \\"Member Basic Information\\", \\"control_type\\": \\"Group\\"}),\\n        UiaNode(name=\\"Gender Marital Status\\", control_type=\\"Text\\", rect=BBox(841, 382, 160, 22),\\n                parent={\\"name\\": \\"Member Basic Information\\", \\"control_type\\": \\"Group\\"}),\\n        UiaNode(name=\\"Religious and Astro Information\\", control_type=\\"Text\\", rect=BBox(841, 666, 200, 22),\\n                parent={\\"name\\": \\"Religious and Astro Information\\", \\"control_type\\": \\"Group\\"}),"

new_text = "    text = [\\n        # Source-panel labels live under a pure-text group (\\"Record summary\\")\\n        UiaNode(name=\\"Member Name\\", control_type=\\"Text\\", rect=BBox(585, 186, 80, 22),\\n                parent={\\"name\\": \\"Record summary\\", \\"control_type\\": \\"Group\\"}),\\n        UiaNode(name=\\"Application No\\", control_type=\\"Text\\", rect=BBox(585, 230, 140, 22),\\n                parent={\\"name\\": \\"Record summary\\", \\"control_type\\": \\"Group\\"}),\\n        # Right-form labels share parent with editable fields\\n        UiaNode(name=\\"Gender Marital Status\\", control_type=\\"Text\\", rect=BBox(841, 382, 160, 22),\\n                parent={\\"name\\": \\"Member Basic Information\\", \\"control_type\\": \\"Group\\"}),\\n        UiaNode(name=\\"Religious and Astro Information\\", control_type=\\"Text\\", rect=BBox(841, 666, 200, 22),\\n                parent={\\"name\\": \\"Religious and Astro Information\\", \\"control_type\\": \\"Group\\"}),"

if old_text in content:
    content = content.replace(old_text, new_text)
    with open("tests/test_uia_flow.py", "w") as f:
        f.write(content)
    print("Fixed!")
else:
    print("Not found")
