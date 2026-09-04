fixed = b'''\"\"\"Window client-area capture. >> write_fixed_full.py && echo. >> write_fixed_full.py && echo Attaches to a single target window and captures ONLY its client area, returning >> write_fixed_full.py && echo the image as a numpy array together with the offset of the client area on the >> write_fixed_full.py && echo physical screen (so element boxes can be translated to absolute screen >> write_fixed_full.py && echo coordinates for mouse actions). >> write_fixed_full.py && echo. >> write_fixed_full.py && echo \"\"\"  
  
from __future__ import annotations  
  
import time  
from dataclasses import dataclass  
from typing import Any  
  
import numpy as np  
  
from atlas.core.logging import logger  
  
try:  
    import mss  
    import mss.tools  
except ImportError:  # pragma: no cover - dependency guard  
    mss = None  # type: ignore[assignment]  
  
  
@dataclass  
class ClientArea:  
    \"\"\"A captured client area plus the geometry needed to act on it.\"\"\"  
  
    image: np.ndarray  # RGB (H, W, 3)  
    left: int  # screen x of client origin  
    top: int  # screen y of client origin  
    width: int  
    height: int  
  
    def to_screen(self, x: int, y: int) -, int]:  
        \"\"\"Translate capture-relative coordinates to absolute screen coords.\"\"\"  
        return self.left + x, self.top + y  
  
    @property  
    def offset(self) -, int]:  
        return (self.left, self.top)  
  
    def save(self, path: Any) - 
        from PIL import Image  
        Image.fromarray(self.image).save(path) 
