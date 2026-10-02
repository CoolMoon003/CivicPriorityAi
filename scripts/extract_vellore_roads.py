import os
import pandas as pd
import osmnx as ox

OUTPUT = "data/processed/roads.csv"

print("Downloading Vellore road network from OpenStreetMap...")

place = "Vellore, Tamil Nadu, India"

graph = ox.graph_from_place(
    place,
    network_type="drive",
    simplify=True
)

print(f"Downloaded graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges")

edges = ox.graph_to_gdfs(
    graph,
    nodes=False,
    edges=True
)

rows = []

for idx, row in edges.iterrows():

    geometry = row.geometry

    centroid = geometry.centroid

    road_name = row.get("name")

    if isinstance(road_name, list):
        road_name = ", ".join(map(str, road_name))

    rows.append({
        "road_id": f"OSM_{idx[0]}_{idx[1]}_{idx[2]}",
        "road_name": road_name if pd.notna(road_name) else "Unnamed Road",
        "road_type": row.get("highway"),
        "length_m": row.get("length"),
        "latitude": centroid.y,
        "longitude": centroid.x
    })

df = pd.DataFrame(rows)

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)

df.to_csv(
    OUTPUT,
    index=False
)

print(f"Saved {len(df)} roads to:")
print(OUTPUT)