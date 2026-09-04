import sys  
print('venv python:', sys.executable)  
import os  
site = r'C:\Users\Bindudhara D\Downloads\ATLAS_FINAL_MULTI_VISION_FIXED\DataEntry - Copy\venv\lib\python3.12\site-packages'  
print('site-packages exists:', os.path.exists(site))  
print(os.listdir(site) if os.path.exists(site) else 'N/A')  
