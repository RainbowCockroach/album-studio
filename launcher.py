"""PyInstaller entry point for Album Studio.

This script exists because PyInstaller runs the entry point as __main__,
which breaks relative imports in src/main.py. By importing src.main as a
module, the relative imports within the src package work correctly.
"""
from src.main import main

main()
