# ============================================================
# NAXA Phase 2 — engine/__init__.py
#
# Makes `engine` a Python package.
# ============================================================
#
# WHY THIS FILE EXISTS:
#   Without it, `from engine.ingestor import fetch_equities`
#   throws a ModuleNotFoundError. Python needs this file
#   to treat the engine/ folder as an importable package.
#
# ANALOGY:
#   A folder without __init__.py = a filing cabinet drawer
#   A folder WITH __init__.py    = a published book chapter
#   Python can only import from published chapters.
#
# WHAT WE EXPOSE HERE (will populate as modules are built):
#   The final state of this file will let analyze.py write:
#       from engine import run_pipeline
#   Instead of importing from each module individually.

__version__ = "0.2.0"