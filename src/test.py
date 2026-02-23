import re
import requests
import pandas as pd
from bs4 import BeautifulSoup

df_info = pd.read_pickle("today_race_info2.pkl")
print("race_info has race_id:", "race_id" in df_info.columns)
print(df_info["race_id"].head())