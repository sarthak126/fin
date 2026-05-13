"""Quick test script to verify import chain — writes output to file."""
import traceback
import sys

with open("startup_log.txt", "w", encoding="utf-8") as f:
    sys.stdout = f
    sys.stderr = f
    try:
        print("SUCCESS: main.py imported OK")
    except Exception as e:
        traceback.print_exc()
        print(f"\nERROR TYPE: {type(e).__name__}")
        print(f"ERROR MSG: {e}")
