from fastapi import FastAPI, HTTPException
from .database import engine
from sqlalchemy.exc import OperationalError
from . import models
from .routers import auth_routes, user_routes, wireguard_routes, me_routes, camera_routes, alerts_routes, super_admin_routes
import logging

# Create database tables
models.Base.metadata.create_all(bind=engine)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Visco backend API",
    description="FastAPI backend with JWT authentication and PostgreSQL to connect with Visco Connect",
    version="2.1.3",
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc"  # ReDoc
)

#########
#Add CORS Middleware later on 

# origins = [
#     "*"  # Add any other domains
# ]

# # Add CORS middleware
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=origins,
#     allow_credentials=True,
#     allow_methods=["*"], 
#     allow_headers=["*"],  # Allows all headers
# )
####

# Database initialization with error handling
@app.on_event("startup")
async def startup_event():
    try:
        # Test database connection
        with engine.connect() as conn:
            logger.info("Database connection successful")
        
        # Create tables
        models.Base.metadata.create_all(bind=engine)
        logger.info("Database tables created/verified")
        
    except OperationalError as e:
        logger.error(f"Database connection failed: {e}")
        logger.error("Please ensure PostgreSQL is running and database 'visco' exists")
        raise HTTPException(
            status_code=500, 
            detail="Database connection failed. Please check PostgreSQL service."
        )
    
# Include routers
app.include_router(auth_routes.router)
app.include_router(user_routes.router)
app.include_router(me_routes.router)
app.include_router(camera_routes.router)
app.include_router(alerts_routes.router)
app.include_router(super_admin_routes.router)
app.include_router(wireguard_routes.router)

@app.get("/")
def root():
    return {"message": "Visco Authentication API is running!"}

@app.get("/health")
def health_check():
    try:
        # Test database connection in health check
        with engine.connect():
            return {"status": "healthy", "message": "API and database are operational"}
    except Exception as e:
        return {"status": "unhealthy", "message": f"Database connection failed: {str(e)}"}