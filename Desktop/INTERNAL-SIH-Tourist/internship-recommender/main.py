# api/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from api import schemas, utils

app = FastAPI(title="Internship Recommender API")

# CORS so frontend (React) can talk to backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # in prod, restrict this to your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["status"])
def root():
    return {"status": "ok", "message": "Internship recommender API running."}


@app.get("/status", tags=["status"])
def status():
    """Check if model + dataset loaded."""
    try:
        model, encoders, df = utils.load_model()
        return {
            "model_type": type(model).__name__,
            "num_internships": len(df)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/recommend", response_model=schemas.RecommendOut, tags=["recs"])
def recommend(candidate: schemas.CandidateIn, top_k: int = 5):
    """
    Main recommendation endpoint → called by frontend.
    """
    try:
        r = utils.recommend(candidate.dict(), top_k=top_k)
        return {
            "candidate": candidate,
            "match_probability": r["probability"],
            "recommendations": [
                {
                    "id": None,
                    "JobTitle": rec["JobTitle"],
                    "CompanyName": rec["CompanyName"],
                    "States": rec["States"],
                    "JobType": rec["JobType"],
                    "match_score": rec["match_score"],
                }
                for rec in r["recommendations"]
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
