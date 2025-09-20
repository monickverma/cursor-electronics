import joblib
import difflib
import numpy as np
import pandas as pd
from pathlib import Path

# --- Paths ---
MODEL_PATH = Path(__file__).parent.parent / "internship_model.pkl"
DATA_FILE = Path(__file__).parent.parent.parent / "data" / "Aicte_Internship_With_Feedback.csv"

# --- Globals ---
_model = None
_encoders = None
_df = None


# ----------------- LOAD MODEL -----------------
def load_model():
    """Load trained RandomForest + encoders + dataset once."""
    global _model, _encoders, _df
    if _model is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(f"Trained model not found at {MODEL_PATH}")
        bundle = joblib.load(MODEL_PATH)
        _model = bundle["model"]
        _encoders = bundle["encoders"]
    if _df is None:
        if not DATA_FILE.exists():
            raise FileNotFoundError(f"Dataset not found at {DATA_FILE}")
        _df = pd.read_csv(DATA_FILE)
    return _model, _encoders, _df


# ----------------- SAFE TRANSFORM -----------------
def safe_transform(enc, values):
    """Transform values safely, unseen labels → fallback 0."""
    mapped = []
    for v in values:
        if v in enc.classes_:
            mapped.append(enc.transform([v])[0])
        else:
            mapped.append(0)  # fallback to first class
    return mapped


# ----------------- ENCODE CANDIDATE -----------------
def encode_candidate(candidate: dict, encoders: dict):
    """Turn candidate dict into encoded feature vector."""
    sector_enc = encoders["sector_enc"]
    mode_enc = encoders["mode_enc"]
    loc_enc = encoders["loc_enc"]

    matched_title = fuzzy_match(candidate.get("JobTitle", ""), list(sector_enc.classes_))
    t_val = sector_enc.transform([matched_title])[0] if matched_title else 0

    matched_mode = fuzzy_match(candidate.get("Mode", ""), list(mode_enc.classes_))
    m_val = mode_enc.transform([matched_mode])[0] if matched_mode else 0

    matched_loc = fuzzy_match(candidate.get("Location", ""), list(loc_enc.classes_))
    l_val = loc_enc.transform([matched_loc])[0] if matched_loc else 0

    stipend = float(candidate.get("Stipend") or 0)
    duration = float(candidate.get("Duration") or 0)

    features = np.array([[t_val, m_val, l_val, stipend, duration]])
    return features, {
        "matched_title": matched_title,
        "matched_mode": matched_mode,
        "matched_location": matched_loc,
    }


# ----------------- FUZZY MATCH -----------------
def fuzzy_match(value: str, choices: list, cutoff=0.6):
    """Closest match for value from choices (case-insensitive)."""
    if not value:
        return None
    best = difflib.get_close_matches(value, choices, n=1, cutoff=cutoff)
    return best[0] if best else None


# ----------------- RECOMMEND -----------------
def recommend(candidate: dict, top_k: int = 5):
    model, encoders, df = load_model()

    # Encode candidate
    X_cand, matched = encode_candidate(candidate, encoders)

    # Candidate probability
    prob = float(model.predict_proba(X_cand)[0][1])

    # --- ML scores ---
    df_enc = df.copy()
    df_enc["Job Title"] = df_enc["Job Title"].fillna("").astype(str)
    df_enc["Job Type"] = df_enc["Job Type"].fillna("").astype(str)
    df_enc["States"] = df_enc["States"].fillna("").astype(str)

    df_enc["sector_enc"] = safe_transform(encoders["sector_enc"], df_enc["Job Title"])
    df_enc["mode_enc"] = safe_transform(encoders["mode_enc"], df_enc["Job Type"])
    df_enc["location_enc"] = safe_transform(encoders["loc_enc"], df_enc["States"])

    X_all = df_enc[["sector_enc", "mode_enc", "location_enc", "StipendValue", "DurationValue"]]
    ml_probs = model.predict_proba(X_all)[:, 1]

    # Normalize ML scores
    min_p, max_p = ml_probs.min(), ml_probs.max()
    if max_p > min_p:
        ml_scores = (ml_probs - min_p) / (max_p - min_p)
    else:
        ml_scores = ml_probs

    # --- Fuzzy scores ---
    title_query = candidate.get("JobTitle", "")
    loc_query = candidate.get("Location", "")

    title_scores = df["Job Title"].fillna("").astype(str).apply(
        lambda x: difflib.SequenceMatcher(None, title_query.lower(), x.lower()).ratio()
    )
    loc_scores = df["States"].fillna("").astype(str).apply(
        lambda x: difflib.SequenceMatcher(None, loc_query.lower(), x.lower()).ratio()
    )

    # --- Final weighted score ---
    df_with = df.copy()
    df_with["match_score"] = (
        0.7 * ml_scores + 0.2 * title_scores + 0.1 * loc_scores
    )

    # Top-k
    top = df_with.sort_values("match_score", ascending=False).head(top_k)

    recs = []
    for _, r in top.iterrows():
        recs.append({
            "JobTitle": r["Job Title"],
            "CompanyName": r.get("Company Name", ""),
            "States": r.get("States", ""),
            "JobType": r.get("Job Type", ""),
            "match_score": float(r["match_score"])
        })

    return {"probability": prob, "matched": matched, "recommendations": recs}
