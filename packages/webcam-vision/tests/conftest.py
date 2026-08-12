"""Test bootstrap: put the package src (and aoep_shared) on sys.path."""

import os
import sys

_HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(_HERE, "..", "src"))
sys.path.insert(0, os.path.join(_HERE, "..", "..", "shared", "src"))
