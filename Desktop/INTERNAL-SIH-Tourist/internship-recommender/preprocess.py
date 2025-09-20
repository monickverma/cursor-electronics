# preprocess.py
import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from pathlib import Path

# Path to dataset (outside project folder)
DATA_FILE = Path(__file__).parent.parent / "data" / "Aicte_Internship_With_Feedback.csv"

# Load dataset
df = pd.read_csv(DATA_FILE)

# --- Select relevant columns ---
# We'll use Job Title, Job Type, States, StipendValue, DurationValue
needed_cols = ["Job Title", "Job Type", "States", "StipendValue", "DurationValue", "Label"]
df = df[needed_cols].dropna()

# --- Encode categorical columns ---
sector_enc = LabelEncoder()
df["sector_enc"] = sector_enc.fit_transform(df["Job Title"].astype(str))

mode_enc = LabelEncoder()
df["mode_enc"] = mode_enc.fit_transform(df["Job Type"].astype(str))

loc_enc = LabelEncoder()
df["location_enc"] = loc_enc.fit_transform(df["States"].astype(str))

# --- Features and target ---
X = df[["sector_enc", "mode_enc", "location_enc", "StipendValue", "DurationValue"]]
y = df["Label"]

print("✅ Preprocessing complete")
print("Feature shape:", X.shape, "Target shape:", y.shape)

# Keep encoders for inference
encoders = {"sector_enc": sector_enc, "mode_enc": mode_enc, "loc_enc": loc_enc}
