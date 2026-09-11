from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)

from app import *  # noqa: F401,F403
y