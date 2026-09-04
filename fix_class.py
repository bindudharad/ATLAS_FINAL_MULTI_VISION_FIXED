with open('atlas/vision/capture.py', 'r') as f:  
    content = f.read()  
  
import re  
  
fixed_class = '''class ScreenGrabber:  
    \"\"\"Low-level screen grabber using mss, with a BitBlt fallback. >> fix_class.py && echo >> fix_class.py && echo     ``gdi32.GetDIBits() failed.`` errors are a known mss failure mode: once the >> fix_class.py && echo     mss instance's internal DC goes stale (display changes, GPU/driver reset, >> fix_class.py && echo     prolonged capture) every subsequent grab fails and the agent stalls. We >> fix_class.py && echo     re-initialise the mss session on failure and, if it keeps failing, switch to >> fix_class.py && echo     a PIL ``ImageGrab`` BitBlt path for a cooldown window so the loop never >> fix_class.py && echo     deadlocks on a broken grabber. >> fix_class.py && echo     \"\"\"  
  
    #: Consecutive failures that trigger the BitBlt fallback.  
    _FALLBACK_AFTER = 2  
  
    #: How long (seconds) to stay on the BitBlt fallback once engaged.  
    _FALLBACK_WINDOW = 30.0  
  
    def __init__(self) - 
        if mss is None:  
            raise RuntimeError(\"mss is required for screen capture\")  
        self._mss = mss.mss()  
        self._consecutive_failures = 0  
        self._fallback_until = 0.0  
  
    def grab_rect(self, left: int, top: int, width: int, height: int) - 
        \"\"\"Grab a rectangle and return an RGB numpy array using BitBlt (avoids mss window maximization side effect).\"\"\"  
        # Use BitBlt directly to avoid mss side effects  
        return self._grab_bitblt(left, top, width, height)  
  
    def _grab_mss(self, left: int, top: int, width: int, height: int) - 
        shot = self._mss.grab({\"left\": left, \"top\": top, \"width\": width, \"height\": height})  
        arr = np.frombuffer(shot.raw, dtype=np.uint8).reshape(shot.height, shot.width, 4)  
        return arr[:, :, :3][:, :, ::-1].copy()  # BGRA - 
  
    def _grab_bitblt(self, left: int, top: int, width: int, height: int) - 
        \"\"\"BitBlt-based capture via PIL (different GDI path than mss).\"\"\"  
        from PIL import ImageGrab  
  
