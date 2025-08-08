from fastapi import FastAPI
from .database import engine
from . import models
from .routers import auth_routes, user_routes

# Create database tables
models.Base.metadata.create_all(bind=engine)

# Create FastAPI app
app = FastAPI(
    title="Visco backend API",
    description="FastAPI backend with JWT authentication and PostgreSQL to connect with Visco Connect",
    version="1.0.0",
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc"  # ReDoc
)

# Include routers
app.include_router(auth_routes.router)
app.include_router(user_routes.router)

@app.get("/")
def root():
    return {"message": "Visco Authentication API is running!"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "message": "API is operational"}
