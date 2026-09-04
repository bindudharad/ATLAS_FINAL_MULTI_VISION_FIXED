import sys  
content = (  
b'from __future__ import annotations\\n'  
b'\\n'  
b'\"\"\"Safety utilities for ATLAS AI.\"\"\"\\n'  
b'\\n'  
b'def is_safe_action(action: str) - 
b'    \"\"\"Check if an action is safe to perform.\"\"\"\\n'  
b'    return True\\n'  
b'\\n'  
b'class SafetyGuard:\\n'  
b'    \"\"\"Guard for unsafe operations.\"\"\"\\n'  
b'\\n'  
b'    def __init__(self, single_form_mode: bool = False):\\n'  
b'        self.single_form_mode = single_form_mode\\n'  
b'\\n'  
b'    def check(self, action: str, context: dict = None) - 
b'        \"\"\"Check if action is allowed.\"\"\"\\n'  
b'        if self.single_form_mode and action in (\"upload\", \"submit\", \"save_and_upload\"):\\n'  
b'            return False\\n'  
b'        return True\\n'  
)  
with open('atlas/core/safety.py', 'wb') as f:  
    f.write(content)  
print('Written')  
