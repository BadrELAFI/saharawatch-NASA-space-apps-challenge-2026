"""Inspect the actual local GPCP schema and unit-converted subset."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from saharawatch.data import load_data
if __name__ == '__main__':
    monthly, annual, metadata = load_data()
    print(metadata)
    print(monthly)
    print(annual)
