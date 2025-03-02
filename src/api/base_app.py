from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# --- CORS Configuration ---
origins = [
    "http://localhost",
    "http://localhost:8080",
    "https://your-frontend-domain.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,  # Allow sending cookies (if needed)
    allow_methods=["*"],  # Allows all HTTP methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allows all headers.
)


@app.get("/api/health", tags=["admin"])
async def health():
    """
    A simple root route that returns a welcome message.
    """
    return {"message": "Jarvis says Hi"}
