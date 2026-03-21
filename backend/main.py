from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

from incident_narrative.routes import router as narrative_router

app = FastAPI(title="SENTINEL API")

# Configure CORS so the frontend can communicate with the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(narrative_router)

@app.get("/")
def read_root():
    return {"status": "ok", "service": "SENTINEL-API"}
