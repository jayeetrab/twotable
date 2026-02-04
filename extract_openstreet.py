# app.py
import os
import re
import requests
import streamlit as st
import pandas as pd
from pymongo import MongoClient, UpdateOne
from datetime import datetime

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Big bounding boxes for "Greater" areas (you can tweak these)
# Format: (south, west, north, east)
CITY_BBOXES = {
    "Bristol": (51.35, -2.75, 51.55, -2.45),   # Greater Bristol-ish
    "London": (51.25, -0.55, 51.75, 0.35),     # Roughly M25 area
}

# Expanded amenity set to "max out" going-out venues
AMENITY_REGEX = "^(restaurant|fast_food|bar|pub|cafe|biergarten|food_court|nightclub)$"

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "twotable_osm"
COLLECTION_NAME = "venues"


# ----------------- HELPERS ----------------- #

def clean_markdown_link(value: str) -> str:
    """Convert '[text](mailto:foo@bar.com)' -> 'foo@bar.com' etc."""
    if not isinstance(value, str):
        return value
    m = re.match(r"\[.*?\]\((.*?)\)", value)
    if m:
        inner = m.group(1)
        if inner.startswith("mailto:"):
            inner = inner[len("mailto:"):]
        return inner
    return value


def build_overpass_query(city: str) -> str:
    south, west, north, east = CITY_BBOXES[city]
    # Use bbox, bigger timeout + maxsize for large results
    return f"""
[out:json][timeout:300][maxsize:1073741824];

(
  node["amenity"~"{AMENITY_REGEX}"]({south},{west},{north},{east});
  way["amenity"~"{AMENITY_REGEX}"]({south},{west},{north},{east});
  relation["amenity"~"{AMENITY_REGEX}"]({south},{west},{north},{east});
);

out center tags;
"""


def fetch_overpass(query: str) -> dict:
    resp = requests.get(OVERPASS_URL, params={"data": query})
    resp.raise_for_status()
    return resp.json()


def extract_coords(el: dict):
    if "lat" in el and "lon" in el:
        return el["lat"], el["lon"]
    center = el.get("center")
    if center:
        return center.get("lat"), center.get("lon")
    return None, None


def element_to_document(el: dict, city: str) -> dict:
    tags = el.get("tags", {}) or {}

    raw_email = tags.get("contact:email") or tags.get("email")
    email = clean_markdown_link(raw_email) if raw_email else None

    raw_website = tags.get("website")
    website = clean_markdown_link(raw_website) if raw_website else None

    raw_phone = tags.get("contact:phone") or tags.get("phone")
    phone = raw_phone

    lat, lon = extract_coords(el)

    cleaned_tags = {}
    for k, v in tags.items():
        cleaned_tags[k] = clean_markdown_link(v) if isinstance(v, str) else v

    doc = {
        "city": city,
        "name": cleaned_tags.get("name"),
        "amenity": cleaned_tags.get("amenity"),
        "email": email,
        "website": website,
        "phone": phone,
        "street": cleaned_tags.get("addr:street"),
        "housenumber": cleaned_tags.get("addr:housenumber"),
        "postcode": cleaned_tags.get("addr:postcode"),
        "lat": lat,
        "lon": lon,
        "osm_type": el.get("type"),
        "osm_id": el.get("id"),
        "raw_tags": cleaned_tags,
        "fetched_at": datetime.utcnow(),
    }
    return doc


def get_mongo_collection():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    return db[COLLECTION_NAME]


def upsert_documents(col, docs):
    if not docs:
        return 0
    ops = []
    for d in docs:
        try:
            key = {"osm_type": d["osm_type"], "osm_id": d["osm_id"]}
            ops.append(
                UpdateOne(
                    filter=key,
                    update={"$set": d},
                    upsert=True,
                )
            )
        except Exception:
            continue
    if not ops:
        return 0
    result = col.bulk_write(ops, ordered=False)
    return (result.upserted_count or 0) + (result.modified_count or 0)


# ----------------- STREAMLIT APP ----------------- #

st.set_page_config(page_title="TwoTable OSM Importer", layout="wide")
st.title("TwoTable – OSM Venue Importer (Max Coverage)")

st.markdown(
    "Fetch **restaurants, bars, pubs, cafes, food courts, biergartens, nightclubs** "
    "from OpenStreetMap for **Greater Bristol** or **Greater London** using big bounding boxes, "
    "clean emails/URLs, and store everything in MongoDB."
)

with st.sidebar:
    st.header("Settings")
    city = st.selectbox("City", ["Bristol", "London"])
    run_query = st.button(f"Fetch & Save {city}")

    st.subheader("MongoDB")
    st.code(f"URI: {MONGO_URI}\nDB: {DB_NAME}\nCollection: {COLLECTION_NAME}")

if run_query:
    with st.spinner(f"Querying Overpass for {city} venues… (this may take a while)"):
        q = build_overpass_query(city)
        try:
            data = fetch_overpass(q)
            elements = data.get("elements", [])
        except Exception as e:
            st.error(f"Error calling Overpass API: {e}")
            st.stop()

    st.success(f"Fetched {len(elements)} raw elements from Overpass.")

    docs = []
    for el in elements:
        try:
            doc = element_to_document(el, city)
            docs.append(doc)
        except Exception:
            continue

    st.write(f"Prepared {len(docs)} documents (expanded amenity set, large bbox).")

    col = get_mongo_collection()
    try:
        changed = upsert_documents(col, docs)
        st.success(f"Upserted {changed} documents into MongoDB.")
    except Exception as e:
        st.error(f"Error writing to MongoDB: {e}")

    if docs:
        df = pd.DataFrame(docs)
        st.subheader("All fetched venues")
        st.dataframe(
            df[[
                "city", "name", "amenity", "email", "website", "phone",
                "street", "housenumber", "postcode", "lat", "lon"
            ]]
        )
else:
    st.info("Choose a city and click the button to fetch venues.")
