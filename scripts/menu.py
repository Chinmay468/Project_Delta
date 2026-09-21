"""
Wrapper to launch the interactive menu from the scripts/ directory.
Usage: python scripts/menu.py
"""
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO_ROOT)

from main import main_menu

if __name__ == "__main__":
    main_menu()
