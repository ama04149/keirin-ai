import pandas as pd
from pathlib import Path

# 🔴 実際のファイル名に合わせて変更してください
path = Path("race_return_20260227.pkl")

if not path.exists():
    print("File not found:", path)
    exit()

df = pd.read_pickle(path)

print("=== SHAPE ===")
print(df.shape)

print("\n=== COLUMNS ===")
for c in df.columns:
    print(c)

print("\n=== HEAD ===")
print(df.head().to_string())