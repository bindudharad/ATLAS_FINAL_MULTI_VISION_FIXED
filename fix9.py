from pathlib import Path  
Path('test_write.txt').write_text('hello')  
import os  
print(os.path.exists('test_write.txt')) 
