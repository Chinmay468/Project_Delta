"""
Forwarder to launch the interactive studio menu when run from the scripts/ directory.
Usage: python main.py (from inside scripts/)
"""
import os
import sys
import importlib.util

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
root_main = os.path.join(REPO_ROOT, "main.py")

spec = importlib.util.spec_from_file_location("project_delta_main", root_main)
main_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main_module)

if __name__ == "__main__":
    main_module.main_menu()
