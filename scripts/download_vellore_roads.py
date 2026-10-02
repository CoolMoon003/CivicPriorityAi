import osmnx as ox
from pathlib import Path

OUT = Path("data/vellore")
OUT.mkdir(parents=True, exist_ok=True)

print("Downloading Vellore road network from OpenStreetMap...")

G = ox.graph.graph_from_place(
    "Vellore, Tamil Nadu, India",
    network_type="drive",
    simplify=True,
    retain_all=True,
)

output = OUT / "vellore_drive_network.graphml"

ox.io.save_graphml(G, filepath=output)

print("\nDONE!")
print(f"Nodes: {len(G.nodes)}")
print(f"Road edges: {len(G.edges)}")
print(f"Saved to: {output}")