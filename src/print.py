import pandas as pd
df = pd.read_pickle('race_return_20260206.pkl')

print(f"先頭から3行表示 = {df.head(3)}")