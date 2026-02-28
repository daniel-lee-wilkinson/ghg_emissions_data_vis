"""
conftest.py — pytest configuration for the project root.

Ensures the project root is on sys.path so that imports like
`from loaders import ...` work without installing the package.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
