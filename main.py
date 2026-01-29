import os
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pymongo import MongoClient
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from bson import ObjectId
from datetime import datetime


load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

client = MongoClient(MONGO_URI)
db = client["TwoTable"]  # this is the DB name you should open in Compass
venue_surveys = db["venue_surveys"]

dating_survey = db["dating_survey_submissions"]
venue_applications = db["venue_applications"]

app = FastAPI()

# static/ for logo etc if you need it
# app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ---------- PAGES ----------

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/venues", response_class=HTMLResponse)
async def get_venues(request: Request):
    return templates.TemplateResponse("venues.html", {"request": request})


# ---------- API 1: Dater survey ----------

@app.post("/api/dater-survey")
async def submit_dater_survey(
    request: Request,
    age_range: str = Form(...),
    city: str = Form(...),
    status: str = Form(...),
    intent: str = Form(...),
    dates_per_month: str = Form(""),
    ghosting_freq: str = Form(""),
    noshow_freq: str = Form(""),
    frustrations: str = Form(""),
    venue_type: str = Form(""),
    try_twotable: str = Form(""),
    deposit_range: str = Form(""),
    safety: str = Form(""),
    ideal_date: str = Form(""),
    email: str = Form(...),
    source: str = Form("landing-survey"),
):
    doc = {
        "age_range": age_range,
        "city": city,
        "status": status,
        "intent": intent,
        "dates_per_month": dates_per_month,
        "ghosting_freq": ghosting_freq,
        "noshow_freq": noshow_freq,
        "frustrations": frustrations,
        "venue_type": venue_type,
        "try_twotable": try_twotable,
        "deposit_range": deposit_range,
        "safety": safety,
        "ideal_date": ideal_date,
        "email": email,
        "source": source,
    }
    result = dating_survey.insert_one(doc)
    print("Inserted dater survey:", result.inserted_id)
    return RedirectResponse(url="/?submitted=1", status_code=303)

@app.get("/surveys", response_class=HTMLResponse)
async def get_surveys_dashboard(request: Request):
    # Shell page; data loaded via JS
    return templates.TemplateResponse("surveys.html", {"request": request})


@app.get("/surveys/{venue_id}", response_class=HTMLResponse)
async def get_survey_for_venue(venue_id: str, request: Request):
    try:
        oid = ObjectId(venue_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Invalid venue id")

    venue = db["venues"].find_one({"_id": oid})
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")

    survey = venue_surveys.find_one({"venue_id": oid})

    context = {
        "request": request,
        "venue": venue,
        "survey": survey,
    }
    return templates.TemplateResponse("survey_form.html", context)

def get_survey_status_map():
    """Map venue_id -> status for quick lookups."""
    status_map = {}
    for doc in venue_surveys.find({}, {"venue_id": 1, "status": 1}):
        status_map[str(doc["venue_id"])] = doc.get("status", "completed")
    return status_map


@app.get("/api/survey-overview")
async def survey_overview():
    venues_coll = db["venues"]

    # Fetch minimal fields
    venues = list(
        venues_coll.find(
            {},
            {
                "_id": 1,
                "city": 1,
                "zone": 1,
                "postcode": 1,
            },
        )
    )

    status_map = get_survey_status_map()

    by_city = {}
    by_city_zone = {}
    by_city_zone_pc = {}

    for v in venues:
        vid = str(v["_id"])
        city = v.get("city") or "Unknown"
        zone = v.get("zone") or "Unknown"
        pc = v.get("postcode") or "Unknown"

        status = status_map.get(vid, "not_started")
        is_done = status == "completed"

        # City level
        city_bucket = by_city.setdefault(city, {"total": 0, "completed": 0})
        city_bucket["total"] += 1
        if is_done:
            city_bucket["completed"] += 1

        # City+zone
        cz_key = f"{city}|{zone}"
        cz_bucket = by_city_zone.setdefault(
            cz_key, {"city": city, "zone": zone, "total": 0, "completed": 0}
        )
        cz_bucket["total"] += 1
        if is_done:
            cz_bucket["completed"] += 1

        # City+zone+pc
        czp_key = f"{city}|{zone}|{pc}"
        czp_bucket = by_city_zone_pc.setdefault(
            czp_key,
            {
                "city": city,
                "zone": zone,
                "postcode": pc,
                "total": 0,
                "completed": 0,
            },
        )
        czp_bucket["total"] += 1
        if is_done:
            czp_bucket["completed"] += 1

    payload = {
        "by_city": [
            {"city": c, **vals} for c, vals in sorted(by_city.items(), key=lambda x: x[0])
        ],
        "by_city_zone": list(by_city_zone.values()),
        "by_city_zone_postcode": list(by_city_zone_pc.values()),
    }
    return JSONResponse(payload)
from fastapi.responses import JSONResponse
from bson import ObjectId
from typing import Optional

@app.get("/api/venues-by-hierarchy")
async def venues_by_hierarchy(
    city: str,
    zone: Optional[str] = None,
    postcode: Optional[str] = None,
):
    venues_coll = db["venues"]

    # Adjust these keys if your docs use different names
    query = {"city": city}
    if zone:
        query["zone"] = zone
    if postcode:
        query["postcode"] = postcode

    venues = list(
        venues_coll.find(
            query,
            {
                "_id": 1,
                "core.name": 1,
                "location.formattedaddress": 1,
                "city": 1,
                "zone": 1,
                "postcode": 1,
            },
        )
    )

    # Map survey status
    status_map = {}
    for doc in venue_surveys.find({}, {"venue_id": 1, "status": 1}):
        status_map[str(doc["venue_id"])] = doc.get("status", "completed")

    items = []
    for v in venues:
        vid = str(v["_id"])

        # Try to pull a nicer label from photos.authorAttributions[0].displayName
        display_name = None
        photos = v.get("photos") or []
        if photos:
            attributions = (
                photos[0].get("authorAttributions")
                or photos[0].get("author_attributions")
                or []
            )
            if attributions:
                display_name = attributions[0].get("displayName")

        items.append(
            {
                "id": vid,
                "name": (
                    display_name
                    or v.get("name")
                    or v.get("location", {}).get("shortaddress")
                ),
                "address": v.get("location", {}).get("formattedaddress"),
                "city": v.get("city"),
                "zone": v.get("zone"),
                "postcode": v.get("postcode"),
                "status": status_map.get(vid, "not_started"),
            }
        )


    return JSONResponse({"venues": items})

@app.post("/api/venue-surveys")
async def submit_venue_survey(
    request: Request,
    venue_id: str = Form(...),
    surveyor_name: str = Form(...),
    status: str = Form("completed"),  # or "in_progress"
    # Section: Dates capacity
    nights: str = Form(""),
    capacity: str = Form(""),
    payout: str = Form(""),
    # Part 1
    dead_zone_revenue: str = Form(""),
    hardest_slots: str = Form(""),
    cancellation_fee: str = Form(""),
    cancellation_fee_collection: str = Form(""),
    pricing_preference: str = Form(""),
    # Part 2
    pos_integration: str = Form(""),
    tablet_willingness: str = Form(""),
    connectivity: str = Form(""),
    checkin_hardware: str = Form(""),
    # Part 3
    greeting_protocol: str = Form(""),
    bill_splitting: str = Form(""),
    menu_agility: str = Form(""),
    # Part 4
    acoustic_profile: str = Form(""),
    seating_inventory: str = Form(""),
    private_booths: str = Form(""),
    lighting_level: str = Form(""),
    # Part 5
    angela_alert_destination: str = Form(""),
    exit_infrastructure: str = Form(""),
    # Part 6
    payout_preference: str = Form(""),
    tipping_culture: str = Form(""),
    # Final notes
    notes: str = Form(""),
):
    try:
        oid = ObjectId(venue_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid venue id")

    venue = db["venues"].find_one({"_id": oid})
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")

    now = datetime.utcnow()

    survey_body = {
        "nights": nights,
        "capacity": capacity,
        "payout": payout,
        "dead_zone_revenue": dead_zone_revenue,
        "hardest_slots": hardest_slots,
        "cancellation_fee": cancellation_fee,
        "cancellation_fee_collection": cancellation_fee_collection,
        "pricing_preference": pricing_preference,
        "pos_integration": pos_integration,
        "tablet_willingness": tablet_willingness,
        "connectivity": connectivity,
        "checkin_hardware": checkin_hardware,
        "greeting_protocol": greeting_protocol,
        "bill_splitting": bill_splitting,
        "menu_agility": menu_agility,
        "acoustic_profile": acoustic_profile,
        "seating_inventory": seating_inventory,
        "private_booths": private_booths,
        "lighting_level": lighting_level,
        "angela_alert_destination": angela_alert_destination,
        "exit_infrastructure": exit_infrastructure,
        "payout_preference": payout_preference,
        "tipping_culture": tipping_culture,
        "notes": notes,
    }

    base = {
        "venue_id": oid,
        "google_place_id": venue.get("core", {}).get("google_place_id"),
        "city": venue.get("city"),
        "zone": venue.get("zone"),
        "postcode": venue.get("postcode"),
        "surveyor_name": surveyor_name,
        "status": status,
        "survey": survey_body,
        "updated_at": now,
    }

    existing = venue_surveys.find_one({"venue_id": oid})
    if existing:
        venue_surveys.update_one(
            {"_id": existing["_id"]},
            {"$set": base},
        )
        doc_id = existing["_id"]
    else:
        base["created_at"] = now
        result = venue_surveys.insert_one(base)
        doc_id = result.inserted_id

    # After saving, go back to venue survey page
    return RedirectResponse(url=f"/surveys/{venue_id}?saved=1", status_code=303)


# ---------- API 2: Venue application ----------

@app.post("/api/venue-application")
async def submit_venue_application(
    request: Request,
    # About venue
    venue: str = Form(...),
    city: str = Form(...),
    type: str = Form(...),
    web: str = Form(""),
    # Contact
    contact: str = Form(...),
    role: str = Form(""),
    email: str = Form(...),
    phone: str = Form(""),
    # Dates config
    nights: str = Form(""),
    capacity: str = Form(""),
    payout: str = Form(""),
    notes: str = Form(""),

    # Part 1
    dead_zone_revenue: str = Form(""),
    hardest_slots: str = Form(""),
    cancellation_fee: str = Form(""),
    cancellation_fee_collection: str = Form(""),
    pricing_preference: str = Form(""),

    # Part 2
    pos_integration: str = Form(""),
    tablet_willingness: str = Form(""),
    connectivity: str = Form(""),
    checkin_hardware: str = Form(""),

    # Part 3
    greeting_protocol: str = Form(""),
    bill_splitting: str = Form(""),
    menu_agility: str = Form(""),

    # Part 4
    acoustic_profile: str = Form(""),
    seating_inventory: str = Form(""),
    private_booths: str = Form(""),
    lighting_level: str = Form(""),

    # Part 5
    angela_alert_destination: str = Form(""),
    exit_infrastructure: str = Form(""),

    # Part 6
    payout_preference: str = Form(""),
    tipping_culture: str = Form(""),
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
        "dead_zone_revenue": dead_zone_revenue,
        "hardest_slots": hardest_slots,
        "cancellation_fee": cancellation_fee,
        "cancellation_fee_collection": cancellation_fee_collection,
        "pricing_preference": pricing_preference,
        "pos_integration": pos_integration,
        "tablet_willingness": tablet_willingness,
        "connectivity": connectivity,
        "checkin_hardware": checkin_hardware,
        "greeting_protocol": greeting_protocol,
        "bill_splitting": bill_splitting,
        "menu_agility": menu_agility,
        "acoustic_profile": acoustic_profile,
        "seating_inventory": seating_inventory,
        "private_booths": private_booths,
        "lighting_level": lighting_level,
        "angela_alert_destination": angela_alert_destination,
        "exit_infrastructure": exit_infrastructure,
        "payout_preference": payout_preference,
        "tipping_culture": tipping_culture,
    }
    result = venue_applications.insert_one(doc)
    print("Inserted venue application:", result.inserted_id)
    return RedirectResponse(url="/venues?submitted=1", status_code=303)
