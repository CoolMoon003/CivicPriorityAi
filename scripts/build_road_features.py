import os
import pandas as pd
import geopandas as gpd
import osmnx as ox

ROAD_GRAPH = "data/vellore/vellore_drive_network.graphml"
FACILITIES = "data/public/vellore_public_facilities.geojson"
ACCIDENTS = "data/public/tamil_nadu_road_accidents_2021_2023.csv"
OUT = "data/processed"

os.makedirs(OUT, exist_ok=True)

print("=" * 60)
print("CIVICPRIORITYAI - BUILDING ROAD FEATURES")
print("=" * 60)

# 1. LOAD ROAD NETWORK
print("\n[1/4] Loading Vellore road network...")

G = ox.load_graphml(ROAD_GRAPH)

roads = ox.graph_to_gdfs(
    G,
    nodes=False,
    edges=True
).reset_index()

roads = roads.to_crs("EPSG:4326")

print("Road segments:", len(roads))

# 2. LOAD FACILITIES
print("\n[2/4] Loading public facilities...")

facilities = gpd.read_file(FACILITIES)
facilities = facilities.to_crs("EPSG:4326")

print("Facilities:", len(facilities))
print(facilities["amenity"].value_counts(dropna=False).to_string())

# 3. LOAD ACCIDENT DATA
print("\n[3/4] Loading accident data...")

acc = pd.read_csv(ACCIDENTS)

vellore_rows = acc[
    acc["District"].astype(str).str.upper() == "VELLORE"
]

if vellore_rows.empty:
    raise RuntimeError("VELLORE record not found in accident dataset")

vellore = vellore_rows.iloc[0]

accident_2021 = float(vellore["Total Accidents 2021"])
accident_2022 = float(vellore["Total Accidents 2022"])
accident_2023 = float(vellore["Total Accidents 2023"])

deaths_2021 = float(vellore["Total Deaths 2021"])
deaths_2022 = float(vellore["Total Deaths 2022"])
deaths_2023 = float(vellore["Total Deaths 2023"])

print(
    "Vellore accidents:",
    int(accident_2021),
    int(accident_2022),
    int(accident_2023)
)

print(
    "Vellore deaths:",
    int(deaths_2021),
    int(deaths_2022),
    int(deaths_2023)
)

# District-level historical signals.
roads["accidents_2023"] = accident_2023
roads["deaths_2023"] = deaths_2023

roads["accident_history_3yr"] = (
    accident_2021 +
    accident_2022 +
    accident_2023
)

roads["death_history_3yr"] = (
    deaths_2021 +
    deaths_2022 +
    deaths_2023
)

# 4. FACILITY PROXIMITY
print("\n[4/4] Calculating facility exposure...")

roads_m = roads.to_crs("EPSG:32644")
facilities_m = facilities.to_crs("EPSG:32644")

facility_points = facilities_m.copy()
facility_points["geometry"] = facility_points.geometry.representative_point()

facility_types = [
    "hospital",
    "clinic",
    "school",
    "college",
    "university",
    "police",
    "fire_station",
    "doctors",
]

search_radius = 500

for facility_type in facility_types:
    roads_m["near_" + facility_type] = 0

for idx, road in roads_m.iterrows():

    distances = facility_points.geometry.distance(
        road.geometry
    )

    nearby = facility_points[
        distances <= search_radius
    ]

    if nearby.empty:
        continue

    for facility_type in facility_types:

        count = (
            nearby["amenity"]
            .astype(str)
            .eq(facility_type)
            .sum()
        )

        roads_m.loc[
            idx,
            "near_" + facility_type
        ] = int(count)

roads = roads_m.to_crs("EPSG:4326")

# SAVE
geojson_output = os.path.join(
    OUT,
    "vellore_road_features.geojson"
)

csv_output = os.path.join(
    OUT,
    "vellore_road_features.csv"
)

roads.to_file(
    geojson_output,
    driver="GeoJSON"
)

roads.drop(
    columns="geometry"
).to_csv(
    csv_output,
    index=False
)

print("\n" + "=" * 60)
print("DONE")
print("=" * 60)

print("Road segments:", len(roads))
print("GeoJSON:", geojson_output)
print("CSV:", csv_output)

print("\nColumns:")
for column in roads.columns:
    print(" ", column)
