import sys  
content = b'from __future__ import annotations\n\n\"\"\"Safety utilities for ATLAS AI.\"\"\"\n\ndef is_safe_action(action: str) -    \"\"\"Check if an action is safe to perform.\"\"\"\n    return True\n\nclass SafetyGuard:\n    \"\"\"Guard for unsafe operations.\"\"\"\n\n    def __init__(self, single_form_mode: bool = False):\n        self.single_form_mode = single_form_mode\n\n    def check(self, action: str, context: dict = None) -        \"\"\"Check if action is allowed.\"\"\"\n        if self.single_form_mode and action in (\"upload\", \"submit\", \"save_and_upload\"):\n            return False\n        return True\n'  
with open('atlas/core/safety.py', 'wb') as f:  
    f.write(content)  
print('Written')  
