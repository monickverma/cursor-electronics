import pandas as pd

df = pd.read_csv("../data/Aicte_Internship_With_Feedback.csv")
print(df.head())         # see first 5 rows
print(df.columns.tolist())  # list column names
