import traceback
try:
    print("Success")
except Exception:
    print("Error during import:")
    traceback.print_exc()
