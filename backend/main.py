import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(
    title="Project AI Cooking API",
    description="FastAPI Backend for Project AI Cooking React Native App",
    version="1.0.0"
)

# CORS Setup - Enable cross-origin requests for React Native mobile & web apps
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, specify domain origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class StatusResponse(BaseModel):
    status: str
    message: str
    version: str

@app.get("/", response_model=StatusResponse)
def root():
    return StatusResponse(
        status="success",
        message="Welcome to Project AI Cooking API Server!",
        version="1.0.0"
    )

@app.get("/api/v1/health")
def health_check():
    return {
        "status": "healthy",
        "service": "fastapi-backend",
        "environment": os.getenv("ENV", "development")
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
