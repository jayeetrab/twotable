import os
from datetime import datetime

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

client = MongoClient(MONGO_URI)
db = client["TwoTable"]  # this is the DB name you should open in Compass

# Existing collections
datingsurvey = db["datingsurveysubmissions"]
venueapplications = db["venueapplications"]

# New collections for survey app
venues = db["venues"]  # your Google Places venues collection
venue_surveys = db["venue_surveys"]  # new collection for survey responses

app = FastAPI()

templates = Jinja2Templates(directory="templates")

# app.mount("/static", StaticFiles(directory="static"), name="static")

TITLE = "TwoTable"


# ---------- PAGES ----------

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/venues", response_class=HTMLResponse)
async def get_venues(request: Request):
    return templates.TemplateResponse("venues.html", {"request": request})


@app.get("/internal/surveys", response_class=HTMLResponse)
async def get_internal_surveys(request: Request):
    # Hidden internal survey app UI
    return templates.TemplateResponse("survey_app.html", {"request": request})


# ---------- API 1: Dater survey ----------

@app.post("/api/dater-survey")
async def submit_dater_survey(
    request: Request,
    agerange: str = Form(...),
    city: str = Form(...),
    status: str = Form(...),
    intent: str = Form(...),
    datespermonth: str = Form(...),
    ghostingfreq: str = Form(...),
    noshowfreq: str = Form(...),
    frustrations: str = Form(...),
    venuetype: str = Form(...),
    trytwotable: str = Form(...),
    depositrange: str = Form(...),
    safety: str = Form(...),
    idealdate: str = Form(...),
    email: str = Form(...),
    source: str = Form("landing-survey"),
):
    doc = {
        "agerange": agerange,
        "city": city,
        "status": status,
        "intent": intent,
        "datespermonth": datespermonth,
        "ghostingfreq": ghostingfreq,
        "noshowfreq": noshowfreq,
        "frustrations": frustrations,
        "venuetype": venuetype,
        "trytwotable": trytwotable,
        "depositrange": depositrange,
        "safety": safety,
        "idealdate": idealdate,
        "email": email,
        "source": source,
        "created_at": datetime.utcnow(),
    }
    result = datingsurvey.insert_one(doc)
    print("Inserted dater survey:", result.inserted_id)
    return RedirectResponse(url="/?submitted=1", status_code=303)


# ---------- API 2: Venue application ----------

@app.post("/api/venue-application")
async def submit_venue_application(
    request: Request,
    venue: str = Form(...),
    city: str = Form(...),
    type: str = Form(...),
    web: str = Form(...),

    contact: str = Form(...),
    role: str = Form(""),
    email: str = Form(...),
    phone: str = Form(...),

    nights: str = Form(...),
    capacity: str = Form(...),
    payout: str = Form(...),
    notes: str = Form(""),

    deadzonerevenue: str = Form(...),
    hardestslots: str = Form(...),
    cancellationfee: str = Form(...),
    cancellationfeecollection: str = Form(...),
    pricingpreference: str = Form(""),

    posintegration: str = Form(""),
    tabletwillingness: str = Form(""),
    connectivity: str = Form(""),
    checkinhardware: str = Form(""),

    greetingprotocol: str = Form(""),
    billsplitting: str = Form(""),
    menuagility: str = Form(""),

    acousticprofile: str = Form(...),
    seatinginventory: str = Form(...),
    privatebooths: str = Form(""),
    lightinglevel: str = Form(...),

    angelaalertdestination: str = Form(""),
    exitinfrastructure: str = Form(""),

    payoutpreference: str = Form(...),
    tippingculture: str = Form(""),
):
    doc = {
        "venue": venue,
        "city": city,
        "type": type,
        "web": web,
        "contact": contact,
        "role": role,
        "email": email,
        "phone": phone,
        "nights": nights,
        "capacity": capacity,
        "payout": payout,
        "notes": notes,
        "deadzonerevenue": deadzonerevenue,
        "hardestslots": hardestslots,
        "cancellationfee": cancellationfee,
        "cancellationfeecollection": cancellationfeecollection,
        "pricingpreference": pricingpreference,
        "posintegration": posintegration,
        "tabletwillingness": tabletwillingness,
        "connectivity": connectivity,
        "checkinhardware": checkinhardware,
        "greetingprotocol": greetingprotocol,
        "billsplitting": billsplitting,
        "menuagility": menuagility,
        "acousticprofile": acousticprofile,
        "seatinginventory": seatinginventory,
        "privatebooths": privatebooths,
        "lightinglevel": lightinglevel,
        "angelaalertdestination": angelaalertdestination,
        "exitinfrastructure": exitinfrastructure,
        "payoutpreference": payoutpreference,
        "tippingculture": tippingculture,
        "created_at": datetime.utcnow(),
    }
    result = venueapplications.insert_one(doc)
    print("Inserted venue application:", result.inserted_id)
    return RedirectResponse(url="/venues?submitted=1", status_code=303)


# ---------- API 3: Internal survey app (JSON) ----------

@app.get("/api/internal/cities", response_class=JSONResponse)
async def internal_get_cities():
    pipeline = [
        {"$match": {"includedinsurvey": True}},
        {"$group": {"_id": "$city", "restaurant_count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    data = list(venues.aggregate(pipeline))
    cities = [
        {"city": d["_id"], "restaurant_count": d["restaurant_count"]}
        for d in data
    ]
    return {"cities": cities}


@app.get("/api/internal/zones", response_class=JSONResponse)
async def internal_get_zones(city: str):
    pipeline = [
        {"$match": {"city": city, "includedinsurvey": True}},
        {
            "$group": {
                "_id": "$zone",
                "restaurant_count": {"$sum": 1},
                "surveyed_count": {
                    "$sum": {
                        "$cond": [
                            {"$ne": ["$lastsurveyedat", None]},
                            1,
                            0,
                        ]
                    }
                },
            }
        },
        {"$sort": {"_id": 1}},
    ]
    data = list(venues.aggregate(pipeline))
    zones = [
        {
            "zone": d["_id"],
            "restaurant_count": d["restaurant_count"],
            "surveyed_count": d["surveyed_count"],
        }
        for d in data
    ]
    return {"zones": zones}


@app.get("/api/internal/postcodes", response_class=JSONResponse)
async def internal_get_postcodes(city: str, zone: str):
    pipeline = [
        {"$match": {"city": city, "zone": zone, "includedinsurvey": True}},
        {
            "$group": {
                "_id": "$postcode",
                "restaurant_count": {"$sum": 1},
                "surveyed_count": {
                    "$sum": {
                        "$cond": [
                            {"$ne": ["$lastsurveyedat", None]},
                            1,
                            0,
                        ]
                    }
                },
            }
        },
        {"$sort": {"_id": 1}},
    ]
    data = list(venues.aggregate(pipeline))
    postcodes = [
        {
            "postcode": d["_id"],
            "restaurant_count": d["restaurant_count"],
            "surveyed_count": d["surveyed_count"],
        }
        for d in data
    ]
    return {"postcodes": postcodes}


@app.get("/api/internal/venues", response_class=JSONResponse)
async def internal_get_venues(city: str, zone: str, postcode: str):
    cursor = venues.find(
        {
            "city": city,
            "zone": zone,
            "postcode": postcode,
            "includedinsurvey": True,
        },
        {
            "name": 1,
            "rating": 1,
            "userratingstotal": 1,
            "pricelevel": 1,
            "googlemapsuri": 1,
            "websiteuri": 1,
            "lastsurveyedat": 1,
            "survey_priorityscore": 1,
        },
    ).sort("survey_priorityscore", -1)

    items = []
    for d in cursor:
        items.append(
            {
                "id": str(d["_id"]),
                "name": d.get("name"),
                "rating": d.get("rating"),
                "user_ratings_total": d.get("userratingstotal"),
                "price_level": d.get("pricelevel"),
                "google_maps_uri": d.get("googlemapsuri"),
                "website_uri": d.get("websiteuri"),
                "last_surveyed_at": d.get("lastsurveyedat"),
                "priority": d.get("survey_priorityscore"),
            }
        )

    return {"venues": items}


@app.get("/api/internal/stats/summary", response_class=JSONResponse)
async def internal_get_summary(city: str | None = None):
    match_stage = {"includedinsurvey": True}
    if city:
        match_stage["city"] = city

    pipeline = [
        {"$match": match_stage},
        {
            "$group": {
                "_id": None,
                "total": {"$sum": 1},
                "surveyed": {
                    "$sum": {
                        "$cond": [
                            {"$ne": ["$lastsurveyedat", None]},
                            1,
                            0,
                        ]
                    }
                },
            }
        },
    ]
    data = list(venues.aggregate(pipeline))
    if not data:
        return {"total": 0, "surveyed": 0, "coverage": 0.0}

    d = data[0]
    coverage = (d["surveyed"] / d["total"]) * 100 if d["total"] else 0.0
    return {
        "total": d["total"],
        "surveyed": d["surveyed"],
        "coverage": coverage,
    }


@app.post("/api/internal/surveys", response_class=JSONResponse)
async def internal_submit_venue_survey(
    restaurant_id: str = Form(...),
    city: str = Form(...),
    zone: str = Form(...),
    postcode: str = Form(...),
    visited_on: str = Form(...),
    surveyed_by: str = Form(...),
    vibe_score: int = Form(...),
    crowd_type: str = Form(...),
    noise_level: str = Form(...),
    lighting: str = Form(...),
    two_table_fit: str = Form(...),
    notes: str = Form(""),
):
    # Save survey
    doc = {
        "restaurant_id": ObjectId(restaurant_id),
        "city": city,
        "zone": zone,
        "postcode": postcode,
        "visit_date": visited_on,
        "surveyed_by": surveyed_by,
        "vibe_score": int(vibe_score),
        "crowd_type": crowd_type,
        "noise_level": noise_level,
        "lighting": lighting,
        "two_table_fit": two_table_fit,
        "notes": notes,
        "created_at": datetime.utcnow(),
    }
    result = venue_surveys.insert_one(doc)

    # Mark venue as surveyed
    venues.update_one(
        {"_id": ObjectId(restaurant_id)},
        {"$set": {"lastsurveyedat": datetime.utcnow()}},
    )

    return {"ok": True, "id": str(result.inserted_id)}
