"""build.py (ch5) -- Chapters 4 and 5 share one sample, one model, and one replicate engine, so the
pipeline lives in ../ch04-regression/build.py and writes both chapters' artifacts. This wrapper
exists so `python build.py` in this folder regenerates artifacts/ as CONTRACT section 4 expects.
"""
import runpy
import sys

sys.argv = [sys.argv[0]] + sys.argv[1:]
runpy.run_path("C:/Users/Vishal Singh/Box/ipums/book/chapters/ch04-regression/build.py", run_name="__main__")
