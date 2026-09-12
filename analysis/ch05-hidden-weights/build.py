"""build.py (ch5) -- Chapters 4 and 5 share one sample, one model, and one replicate engine, so the
pipeline lives in ../ch04-regression/build.py and writes both chapters' artifacts. This wrapper runs
it and then gender_cells.py, which adds the chapter's second example (the within-cell gender gap) to
this folder's artifacts from the pipeline's analytic cache. `python build.py` here therefore
regenerates artifacts/ in full, as CONTRACT section 4 expects; running ../ch04-regression/build.py
alone leaves the gg_* facts, the two gender figures, and the gender_gap ledger out.

Arguments pass through to the shared pipeline (--no-r, --reuse-r).
"""
import runpy
import sys

sys.argv = [sys.argv[0]] + sys.argv[1:]
runpy.run_path("C:/Users/Vishal Singh/Box/ipums/book/chapters/ch04-regression/build.py", run_name="__main__")
runpy.run_path("C:/Users/Vishal Singh/Box/ipums/book/chapters/ch05-hidden-weights/gender_cells.py", run_name="__main__")
