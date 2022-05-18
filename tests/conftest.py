import os
import sys


TESTS_DIR = os.path.abspath(os.path.dirname(__file__))
if TESTS_DIR not in sys.path:
    sys.path.append(TESTS_DIR)
