from __future__ import annotations

from pathlib import Path
from typing import Any

import geopandas as gpd
import networkx as nx
import osmnx as ox
from shapely.geometry import Point


class RoadMatcher:
    """
    Matches a GPS coordinate to the nearest road segment
    in the Vellore OSM road network.
    """

    def __init__(
        self,
        graph_path: str | Path,
        features_path: str | Path | None = None,
    ):
        self.graph_path = Path(graph_path)

        if not self.graph_path.exists():
            raise FileNotFoundError(
                f"Road network not found: {self.graph_path}"
            )

        self.graph = ox.load_graphml(self.graph_path)

        self.features = None

        if features_path:
            self.features_path = Path(features_path)

            if not self.features_path.exists():
                raise FileNotFoundError(
                    f"Road features not found: {self.features_path}"
                )

            self.features = gpd.read_file(self.features_path)

    def match(
        self,
        latitude: float,
        longitude: float,
    ) -> dict[str, Any]:

        if not (-90 <= latitude <= 90):
            raise ValueError("Invalid latitude")

        if not (-180 <= longitude <= 180):
            raise ValueError("Invalid longitude")

        # Find nearest OSM road edge.
        u, v, key = ox.distance.nearest_edges(
            self.graph,
            X=longitude,
            Y=latitude,
        )

        edge_data = self.graph.get_edge_data(u, v, key)

        if edge_data is None:
            raise RuntimeError(
                f"Road edge not found: {(u, v, key)}"
            )

        # Get the road geometry.
        geometry = edge_data.get("geometry")

        if geometry is None:
            u_data = self.graph.nodes[u]
            v_data = self.graph.nodes[v]

            from shapely.geometry import LineString

            geometry = LineString([
                (u_data["x"], u_data["y"]),
                (v_data["x"], v_data["y"]),
            ])

        # Calculate distance in meters.
        point = gpd.GeoSeries(
            [Point(longitude, latitude)],
            crs="EPSG:4326",
        )

        road = gpd.GeoSeries(
            [geometry],
            crs="EPSG:4326",
        )

        point_projected = point.to_crs("EPSG:32644")
        road_projected = road.to_crs("EPSG:32644")

        distance_m = float(
            point_projected.iloc[0].distance(
                road_projected.iloc[0]
            )
        )

        u_data = self.graph.nodes[u]
        v_data = self.graph.nodes[v]

        result = {
            "u": int(u),
            "v": int(v),
            "key": int(key),
            "road_name": edge_data.get("name"),
            "highway": edge_data.get("highway"),
            "length_m": float(edge_data.get("length", 0)),
            "distance_m": round(distance_m, 2),
            "lanes": edge_data.get("lanes"),
            "maxspeed": edge_data.get("maxspeed"),
            "oneway": edge_data.get("oneway"),
            "latitude": float(latitude),
            "longitude": float(longitude),
            "start_latitude": float(u_data["y"]),
            "start_longitude": float(u_data["x"]),
            "end_latitude": float(v_data["y"]),
            "end_longitude": float(v_data["x"]),
        }

        # Attach precomputed Vellore road features.
        if self.features is not None:
            matches = self.features[
                (self.features["u"] == u)
                & (self.features["v"] == v)
                & (self.features["key"] == key)
            ]

            if not matches.empty:
                feature_row = matches.iloc[0]

                for column in self.features.columns:
                    if column in {"geometry", "u", "v", "key"}:
                        continue

                    value = feature_row[column]

                    if hasattr(value, "item"):
                        value = value.item()

                    result[column] = value

        return result
