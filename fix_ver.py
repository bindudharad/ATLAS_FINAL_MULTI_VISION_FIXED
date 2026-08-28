with open("tests/test_verification.py", "r") as f:
    content = f.read()

idx = content.find("def scroll_bar")
if idx != -1:
    end_idx = content.find("\n    def paste", idx)
    if end_idx != -1:
        new_method = "    def scroll_dropdown(self, direction, amount=3):\n        self.calls.append((\"scroll_dropdown\", None))\n        return ControlOutcome(ok=True)\n"
        content = content[:end_idx] + new_method + "\n" + content[end_idx:]
        with open("tests/test_verification.py", "w") as f:
            f.write(content)
        print("Fixed!")
    else:
        print("Could not find paste method")
else:
    print("Could not find scroll_bar")
