# main.py
import os
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
import logging
from typing import Optional 
import sys

load_dotenv()

# ========== LOGGING ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# ========== MONGODB SETUP ==========
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    logger.error("MONGO_URI not set in environment variables")
    raise ValueError("MONGO_URI environment variable is required")

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
    db = client["TwoTable"]
    # Test connection
    client.admin.command('ping')
    logger.info("✓ Connected to MongoDB")
except Exception as e:
    logger.error(f"✗ MongoDB connection failed: {e}")
    raise

# Collections
waitlist_collection = db["waitlist"]
contact_collection = db["contact_submissions"]
venue_applications = db["venue_applications"]

# ========== FASTAPI SETUP ==========
app = FastAPI(
    title="TwoTable API",
    version="1.0.0",
    description="API for TwoTable - Curated Date Nights"
)

# ========== CORS CONFIGURATION ==========
origins = [
    # Local development
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    
    # Production domains
    "https://twotable.co.uk",
    "https://www.twotable.co.uk",
    
    # Cloudflare Pages
    "https://twotable-frontend.pages.dev",
    "https://twotable.pages.dev",
    
    # Allow subdomain variations
    "https://*.twotable.co.uk",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=3600,
)

# ========== PYDANTIC MODELS ==========
class WaitlistPayload(BaseModel):
    """Waitlist signup payload"""
    email: EmailStr

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com"
            }
        }


class ContactPayload(BaseModel):
    """Contact form submission payload"""
    name: str
    email: EmailStr
    message: str

    class Config:
        json_schema_extra = {
            "example": {
                "name": "John Doe",
                "email": "john@example.com",
                "message": "I'm interested in becoming a partner."
            }
        }
# ========== VENUE APPLICATION ENDPOINTS ==========

class VenueApplicationPayload(BaseModel):
    """Venue application submission payload"""
    venue: str
    city: str
    type: str
    web: Optional[str] = None
    contact: str
    role: Optional[str] = None
    email: EmailStr
    phone: str
    nights: str
    capacity: str
    payout: str
    notes: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "venue": "The Bistro",
                "city": "Bristol",
                "type": "fine-dining",
                "web": "https://thebistro.com",
                "contact": "John Smith",
                "role": "Manager",
                "email": "john@thebistro.com",
                "phone": "+441173331111",
                "nights": "Tue-Thu after 6pm",
                "capacity": "3-4 tables for two",
                "payout": "30-40",
                "notes": "We're interested in testing this."
            }
        }


@app.post("/api/venue-application")
async def submit_venue_application(payload: VenueApplicationPayload):
    """
    Submit venue partnership application.
    
    Returns:
    - ok: true if successful
    - id: MongoDB document ID
    - message: Status message
    """
    try:
        doc = {
            "venue": payload.venue.strip(),
            "city": payload.city.strip(),
            "type": payload.type,
            "web": payload.web.strip() if payload.web else None,
            "contact": payload.contact.strip(),
            "role": payload.role.strip() if payload.role else None,
            "email": payload.email.lower(),
            "phone": payload.phone.strip(),
            "nights": payload.nights.strip(),
            "capacity": payload.capacity.strip(),
            "payout": payload.payout,
            "notes": payload.notes.strip() if payload.notes else None,
            "created_at": datetime.utcnow(),
            "status": "pending_review",
        }
        result = venue_applications.insert_one(doc)
        logger.info(f"Venue application from: {payload.venue} ({payload.email})")
        
        return {
            "ok": True,
            "id": str(result.inserted_id),
            "message": "Application submitted successfully. We'll review it within 2 business days.",
        }
    except Exception as e:
        logger.error(f"Venue application error: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit application")


@app.get("/api/venue-application/{application_id}")
async def get_venue_application(application_id: str):
    """Get specific venue application by ID"""
    try:
        oid = ObjectId(application_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid application ID format")
    
    try:
        application = venue_applications.find_one({"_id": oid})
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
        
        application["id"] = str(application["_id"])
        del application["_id"]
        return application
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Application query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve application")


@app.get("/api/venue-applications")
async def get_all_venue_applications(skip: int = 0, limit: int = 100):
    """
    Get all venue applications (admin endpoint).
    
    Query params:
    - skip: Number of entries to skip (default: 0)
    - limit: Maximum entries to return (default: 100, max: 1000)
    """
    try:
        if limit > 1000:
            limit = 1000
        
        applications = list(
            venue_applications.find({})
            .skip(skip)
            .limit(limit)
            .sort("created_at", -1)
        )
        
        for app in applications:
            app["id"] = str(app["_id"])
            del app["_id"]
        
        total = venue_applications.count_documents({})
        return {
            "applications": applications,
            "total": total,
            "skip": skip,
            "limit": limit,
            "returned": len(applications)
        }
    except Exception as e:
        logger.error(f"Applications query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve applications")


class SuccessResponse(BaseModel):
    """Standard success response"""
    ok: bool
    id: str = None
    message: str = None

    class Config:
        json_schema_extra = {
            "example": {
                "ok": True,
                "id": "507f1f77bcf86cd799439011",
                "message": "Success"
            }
        }


# ========== HEALTH CHECK ==========
@app.get("/health")
async def health_check():
    """Health check endpoint - returns connection status"""
    try:
        client.admin.command('ping')
        return {
            "status": "healthy",
            "database": "connected",
            "service": "TwoTable API"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail="Database connection failed"
        )


@app.get("/")
async def root():
    """Root endpoint - API info"""
    return {
        "name": "TwoTable API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "waitlist": "/api/waitlist",
            "contact": "/api/contact",
            "docs": "/docs"
        }
    }


# ========== WAITLIST ENDPOINTS ==========
@app.post("/api/waitlist", response_model=SuccessResponse)
async def submit_waitlist(payload: WaitlistPayload):
    """
    Add email to waitlist.
    
    Returns:
    - ok: true if successful
    - id: MongoDB document ID
    - message: Status message
    """
    try:
        email_lower = payload.email.lower()
        
        # Check if email already exists
        existing = waitlist_collection.find_one({"email": email_lower})
        if existing:
            logger.info(f"Email already on waitlist: {email_lower}")
            return {
                "ok": True,
                "id": str(existing["_id"]),
                "message": "Already on waitlist",
            }
        
        # Insert new entry
        doc = {
            "email": email_lower,
            "created_at": datetime.utcnow(),
        }
        result = waitlist_collection.insert_one(doc)
        logger.info(f"Added to waitlist: {email_lower}")
        
        return {
            "ok": True,
            "id": str(result.inserted_id),
            "message": "Added to waitlist",
        }
    except Exception as e:
        logger.error(f"Waitlist submission error: {e}")
        raise HTTPException(status_code=500, detail="Failed to add to waitlist")


@app.get("/api/waitlist/count")
async def get_waitlist_count():
    """Get total number of waitlist entries"""
    try:
        count = waitlist_collection.count_documents({})
        return {"count": count}
    except Exception as e:
        logger.error(f"Count query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get count")


@app.get("/api/waitlist", response_model=dict)
async def get_all_waitlist(skip: int = 0, limit: int = 100):
    """
    Get all waitlist entries (admin endpoint).
    
    Query params:
    - skip: Number of entries to skip (default: 0)
    - limit: Maximum entries to return (default: 100, max: 1000)
    """
    try:
        if limit > 1000:
            limit = 1000
        
        entries = list(
            waitlist_collection.find({})
            .skip(skip)
            .limit(limit)
            .sort("created_at", -1)
        )
        
        for entry in entries:
            entry["id"] = str(entry["_id"])
            del entry["_id"]
        
        total = waitlist_collection.count_documents({})
        return {
            "entries": entries,
            "total": total,
            "skip": skip,
            "limit": limit,
            "returned": len(entries)
        }
    except Exception as e:
        logger.error(f"Waitlist query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve waitlist")


# ========== CONTACT ENDPOINTS ==========
@app.post("/api/contact", response_model=SuccessResponse)
async def submit_contact(payload: ContactPayload):
    """
    Submit contact form.
    
    Returns:
    - ok: true if successful
    - id: MongoDB document ID
    - message: Status message
    """
    try:
        doc = {
            "name": payload.name.strip(),
            "email": payload.email.lower(),
            "message": payload.message.strip(),
            "created_at": datetime.utcnow(),
        }
        result = contact_collection.insert_one(doc)
        logger.info(f"Contact submission from: {payload.email}")
        
        return {
            "ok": True,
            "id": str(result.inserted_id),
            "message": "Message submitted successfully",
        }
    except Exception as e:
        logger.error(f"Contact submission error: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit message")


@app.get("/api/contact/{contact_id}")
async def get_contact(contact_id: str):
    """Get specific contact submission by ID"""
    try:
        oid = ObjectId(contact_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid contact ID format")
    
    try:
        contact = contact_collection.find_one({"_id": oid})
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        
        contact["id"] = str(contact["_id"])
        del contact["_id"]
        return contact
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Contact query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve contact")


@app.get("/api/contact")
async def get_all_contacts(skip: int = 0, limit: int = 100):
    """
    Get all contact submissions (admin endpoint).
    
    Query params:
    - skip: Number of entries to skip (default: 0)
    - limit: Maximum entries to return (default: 100, max: 1000)
    """
    try:
        if limit > 1000:
            limit = 1000
        
        submissions = list(
            contact_collection.find({})
            .skip(skip)
            .limit(limit)
            .sort("created_at", -1)
        )
        
        for submission in submissions:
            submission["id"] = str(submission["_id"])
            del submission["_id"]
        
        total = contact_collection.count_documents({})
        return {
            "submissions": submissions,
            "total": total,
            "skip": skip,
            "limit": limit,
            "returned": len(submissions)
        }
    except Exception as e:
        logger.error(f"Contact query error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve contacts")


# ========== STARTUP & SHUTDOWN ==========
@app.on_event("startup")
async def startup_event():
    """Initialize collections with indexes on startup"""
    try:
        # Create indexes for faster queries
        waitlist_collection.create_index("email", unique=True)
        contact_collection.create_index("email")
        contact_collection.create_index("created_at")
        logger.info("✓ Database indexes created")
    except Exception as e:
        logger.warning(f"Index creation warning: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Close MongoDB connection on shutdown"""
    try:
        client.close()
        logger.info("✓ MongoDB connection closed")
    except Exception as e:
        logger.error(f"Shutdown error: {e}")


# ========== RUN ==========
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,  # Never reload in production
        log_level="info"
    )
