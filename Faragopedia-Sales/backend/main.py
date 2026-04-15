import os
from dotenv import load_dotenv

# Load environment variables. load_dotenv() handles common locations
# automatically. In Docker, docker-compose handles this.
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router as api_router

app = FastAPI()

# Set up CORS - allow all origins for deployment prototype/MVP
# This ensures it works on remote servers without fixed IP/hostname
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

@app.get("/")
def read_root():
    return {"message": "Hello World from FastAPI"}
