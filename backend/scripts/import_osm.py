"""Download the complete Grand Sfax drivable road network from OpenStreetMap.

This is what replaces the hard-coded list of 8 zones in v1: every street,
avenue, route and rocade OSM knows about (typically tens of thousands of
segments), with names, road class and speed limits.

Usage (needs internet, run once, or as a k8s Job / CI step):
    pip install osmnx
    python scripts/import_osm.py --out data/sfax_drive.graphml

The output also stores precomputed edge betweenness, so the API starts fast.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# west, south, east, north - covers Sfax, Sakiet Ezzit/Eddaïer, Chihia, Gremda, El Aïn, Thyna
GRAND_SFAX_BBOX = (10.60, 34.65, 10.90, 34.87)


def main() -> None:
    import networkx as nx
    import osmnx as ox

    from app.graph.road_graph import RoadGraph

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/sfax_drive.graphml")
    ap.add_argument("--k", type=int, default=500, help="betweenness sample size")
    args = ap.parse_args()

    print("Downloading OSM drive network for Grand Sfax ...")
    raw = ox.graph_from_bbox(bbox=GRAND_SFAX_BBOX, network_type="drive", simplify=True)
    rg = RoadGraph(RoadGraph._simplify(raw), source="osm")  # computes betweenness if missing
    rg.compute_centrality(k=args.k)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    nx.write_graphml(rg.g, args.out)
    with open(os.path.splitext(args.out)[0] + "_roads.json", "w", encoding="utf-8") as f:
        json.dump(rg.road_names(), f, ensure_ascii=False, indent=1)
    print(json.dumps(rg.stats(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
