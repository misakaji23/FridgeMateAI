import sys
import os

# Ensure we are in the right directory
os.chdir(r"c:\Users\Owner\Desktop\学校関連\FridgemateAI")

# Mock sys.argv
sys.argv = ["app2.py"]

try:
    print("Importing app2...")
    # Import app2, which should run the initialization code at module level
    import app2
    
    if app2.recommender is not None:
        print("SUCCESS: app2.recommender initialized successfully.")
        print(f"Recommender type: {type(app2.recommender)}")
    else:
        print("FAILURE: app2.recommender is None.")
        
except Exception as e:
    import traceback
    print(f"FAILURE: Exception during import: {e}")
    traceback.print_exc()
