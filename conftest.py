"""
Root conftest.py — adds the project root to sys.path so that
``from src.inventory.item import ...`` style imports resolve correctly
when pytest is invoked from any working directory.
"""
import sys
import os

# Ensure the project root (directory that contains src/ and tests/) is on the path.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
