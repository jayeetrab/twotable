import os
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

client = MongoClient(MONGO_URI)
db = client["TwoTable"]  # this is the DB name you should open in Compass

dating_survey = db["dating_survey_submissions"]
venue_applications = db["venue_applications"]

app = FastAPI()

# static/ for logo etc if you need it
app.mount("/static", StaticFiles(directory="static"), name="static")
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
