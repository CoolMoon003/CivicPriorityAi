import os
import osmnx as ox

PLACE = "Vellore, Tamil Nadu, India"
OUT = "data/public"

os.makedirs(OUT, exist_ok=True)

print("Downloading Vellore public facilities from OpenStreetMap...")

tags = {
    "amenity": [
        "school",
        "hospital",
        "clinic",
        "doctors",
        "fire_station",
        "police",
        "college",
        "university"
    ]
}

gdf = ox.features_from_place(PLACE, tags)

print(f"Total facilities: {len(gdf)}")

keep = [
    "name",
    "amenity",
    "healthcare",
    "operator",
    "geometry"
]

for col in keep:
    if col not in gdf.columns:
        gdf[col] = None

gdf = gdf[keep]

path = os.path.join(OUT, "vellore_public_facilities.geojson")
gdf.to_file(path, driver="GeoJSON")

print(f"SAVED: {path}")

print("\nFacility types:")
print(gdf["amenity"].value_counts(dropna=False))
