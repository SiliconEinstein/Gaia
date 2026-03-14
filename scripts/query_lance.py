#!/usr/bin/env python3
"""Quick peek at all LanceDB v2 tables.

Usage:
    python scripts/query_lance.py                          # default path
    python scripts/query_lance.py ./data/lancedb/gaia_v2   # custom path
"""

import sys

import warnings

import lancedb
import pandas as pd

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*Pandas4Warning.*")

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)
pd.set_option("display.max_colwidth", 80)

path = sys.argv[1] if len(sys.argv) > 1 else "./data/lancedb/gaia_v2"
db = lancedb.connect(path)
tables = sorted(db.table_names())
print(f"Database: {path}")
print(f"Tables:   {tables}\n")

for name in tables:
    t = db.open_table(name)
    df = t.to_pandas()
    # Truncate long text columns for display
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].astype(str).str[:100]
    print(f"{'=' * 60}")
    print(f"  {name}  ({len(df)} rows)")
    print(f"{'=' * 60}")
    print(df.head(5).to_string(index=False))
    print()
