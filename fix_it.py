with open(\"atlas/vision/capture.py\", \"r\") as f:  
    lines = f.readlines()  
  
for i, line in enumerate(lines):  
    if \"def grab_rect\" in line and \"-> np.ndarray:\" not in line:  
        print(\"Found broken grab_rect at line\", i, \":\", line.strip())  
        lines[i] = \"    def grab_rect(self, left: int, top: int, width: int, height: int) -> np.ndarray:\n\"  
