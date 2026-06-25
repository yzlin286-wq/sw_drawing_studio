import sys
import ast

files = [
    r"c:\Users\Vision\Desktop\SW 相关\app\ui\drawing_review_workbench.py",
    r"c:\Users\Vision\Desktop\SW 相关\app\services\final_quality.py",
    r"c:\Users\Vision\Desktop\SW 相关\app\services\health_check.py",
]
for f in files:
    try:
        with open(f, "r", encoding="utf-8") as fp:
            ast.parse(fp.read())
        print(f"OK: {f}")
    except SyntaxError as e:
        print(f"FAIL: {f} - {e}")
        sys.exit(1)
print("All syntax checks passed")
