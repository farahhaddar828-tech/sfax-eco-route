"""Graph-theory engine over the Sfax road network.

The city is modelled as a weighted graph G = (V, E):
  * V = intersections (OSM nodes), with coordinates;
  * E = road segments, weighted by length (m) and travel time (s).

What we compute and why it matters for a city:
  * Edge betweenness centrality  -> how many shortest paths cross a segment,
    i.e. how "load-bearing" it is. A pothole on a high-betweenness segment
    hurts far more people than one in a cul-de-sac.
  * Bridges (graph-theory bridges, not physical ones) -> segments whose loss
    disconnects part of the network. Those get the highest criticality.
  * Closure impact -> remove an edge, recompute Dijkstra, measure the detour.
  * Hazard-aware routing ("eco-route") -> Dijkstra with edge weights inflated
    around open reports, so citizens are routed around problems.
  * Crew dispatch -> a Travelling Salesman tour (nearest-neighbour + 2-opt)
    over shortest-path distances, so one maintenance crew visits several
    reports in a near-minimal drive.
"""
from __future__ import annotations

import logging
import math
import os
import random
from dataclasses import dataclass, field
from typing import Iterable

import networkx as nx
import numpy as np

from ..data.sfax import RADIAL_ROADS, RADIAL_STOPS_KM, RING_ROADS, SFAX_CENTER

log = logging.getLogger(__name__)

DEFAULT_SPEED_KMH = {
    "motorway": 90, "trunk": 70, "primary": 60, "secondary": 50,
    "tertiary": 40, "unclassified": 30, "residential": 30, "living_street": 15,
    "service": 20,
}
CO2_G_PER_KM = 120.0  # average Tunisian passenger car, rough


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _first(v):
    """OSM attributes can be lists (merged ways); keep the first value."""
    if isinstance(v, list):
        return v[0] if v else None
    if isinstance(v, str) and v.startswith("["):
        return v.strip("[]").split(",")[0].strip(" '\"")
    return v


def _speed(highway, maxspeed) -> float:
    try:
        return float(str(_first(maxspeed)).split()[0])
    except (TypeError, ValueError):
        hw = str(_first(highway) or "").replace("_link", "")
        return DEFAULT_SPEED_KMH.get(hw, 30)


@dataclass
class PathResult:
    nodes: list
    coords: list[tuple[float, float]]
    length_m: float
    time_s: float
    co2_g: float
    road_names: list[str] = field(default_factory=list)


class RoadGraph:
    def __init__(self, g: nx.Graph, source: str):
        self.g = g
        self.source = source
        self._nodes = list(g.nodes)
        self._xy = np.array([[g.nodes[n]["y"], g.nodes[n]["x"]] for n in self._nodes], dtype=float)
        self._edges = list(g.edges)
        a = np.array([[g.nodes[u]["y"], g.nodes[u]["x"]] for u, _ in self._edges], dtype=float)
        b = np.array([[g.nodes[v]["y"], g.nodes[v]["x"]] for _, v in self._edges], dtype=float)
        self._ea, self._eb = a, b
        self._bridges: set[frozenset] | None = None
        if not any("betweenness" in d for *_, d in g.edges(data=True)):
            self.compute_centrality()

    # ------------------------------------------------------------------ loading
    @classmethod
    def load(cls, path: str) -> "RoadGraph":
        if path and os.path.exists(path):
            raw = nx.read_graphml(path)
            return cls(cls._simplify(raw), source=f"osm:{os.path.basename(path)}")
        log.warning("Graph file %s not found - using schematic demo graph", path)
        return cls(build_demo_graph(), source="demo")

    @staticmethod
    def _simplify(raw: nx.Graph) -> nx.Graph:
        """MultiDiGraph from OSMnx -> undirected simple graph, keeping the shortest parallel edge."""
        g = nx.Graph()
        for n, d in raw.nodes(data=True):
            g.add_node(n, x=float(d["x"]), y=float(d["y"]))
        for u, v, d in raw.edges(data=True):
            if u == v:
                continue
            length = float(d.get("length", 0) or 0) or haversine_m(
                g.nodes[u]["y"], g.nodes[u]["x"], g.nodes[v]["y"], g.nodes[v]["x"])
            speed = _speed(d.get("highway"), d.get("maxspeed"))
            attrs = dict(
                length=length,
                travel_time=length / (speed / 3.6),
                name=str(_first(d.get("name")) or ""),
                highway=str(_first(d.get("highway")) or ""),
            )
            if "betweenness" in d:
                attrs["betweenness"] = float(d["betweenness"])
            if not g.has_edge(u, v) or g.edges[u, v]["length"] > length:
                g.add_edge(u, v, **attrs)
        # keep the largest connected component so every route is solvable
        largest = max(nx.connected_components(g), key=len)
        return g.subgraph(largest).copy()

    # --------------------------------------------------------------- analytics
    def compute_centrality(self, k: int | None = None, seed: int = 42) -> None:
        """Edge betweenness on travel time. Sampled (k sources) for large graphs."""
        n = self.g.number_of_nodes()
        k = k or (None if n <= 600 else min(400, n))
        bc = nx.edge_betweenness_centrality(self.g, k=k, weight="travel_time", normalized=True, seed=seed)
        top = max(bc.values()) or 1.0
        for (u, v), val in bc.items():
            self.g.edges[u, v]["betweenness"] = val / top  # rescale to 0..1

    @property
    def bridges(self) -> set[frozenset]:
        if self._bridges is None:
            self._bridges = {frozenset(e) for e in nx.bridges(self.g)}
        return self._bridges

    def edge_criticality(self, u, v) -> float:
        """0..1 score: betweenness, boosted to >=0.9 for graph bridges, plus road class."""
        d = self.g.edges[u, v]
        score = d.get("betweenness", 0.0)
        cls_bonus = {"motorway": .2, "trunk": .2, "primary": .15, "secondary": .1, "tertiary": .05}
        score = min(1.0, score + cls_bonus.get(d.get("highway", ""), 0.0))
        if frozenset((u, v)) in self.bridges:
            score = max(score, 0.9)
        return round(score, 4)

    def stats(self) -> dict:
        g = self.g
        total_km = sum(d["length"] for *_, d in g.edges(data=True)) / 1000
        degrees = [d for _, d in g.degree()]
        return {
            "source": self.source,
            "nodes": g.number_of_nodes(),
            "edges": g.number_of_edges(),
            "total_km": round(total_km, 1),
            "avg_degree": round(sum(degrees) / len(degrees), 2),
            "bridges": len(self.bridges),
            # cyclomatic number = independent loops = redundancy of the network
            "cyclomatic_number": g.number_of_edges() - g.number_of_nodes() + nx.number_connected_components(g),
            "named_roads": len({d["name"] for *_, d in g.edges(data=True) if d.get("name")}),
        }

    def most_critical_edges(self, top: int = 15) -> list[dict]:
        scored = sorted(self._edges, key=lambda e: self.edge_criticality(*e), reverse=True)[:top]
        return [self.edge_info(u, v) for u, v in scored]

    def road_names(self) -> list[str]:
        return sorted({d["name"] for *_, d in self.g.edges(data=True) if d.get("name")})

    # ------------------------------------------------------------- geo lookup
    def nearest_node(self, lat: float, lon: float):
        d = (self._xy[:, 0] - lat) ** 2 + ((self._xy[:, 1] - lon) * math.cos(math.radians(lat))) ** 2
        return self._nodes[int(np.argmin(d))]

    def nearest_edge(self, lat: float, lon: float) -> tuple:
        """Point-to-segment projection, vectorised over all edges (equirectangular approx)."""
        k = math.cos(math.radians(lat))
        p = np.array([lat, lon * k])
        a = self._ea * [1, k]
        b = self._eb * [1, k]
        ab = b - a
        t = np.clip(((p - a) * ab).sum(1) / np.maximum((ab * ab).sum(1), 1e-18), 0, 1)
        proj = a + ab * t[:, None]
        i = int(np.argmin(((proj - p) ** 2).sum(1)))
        return self._edges[i]

    def edge_info(self, u, v) -> dict:
        d = self.g.edges[u, v]
        nu, nv = self.g.nodes[u], self.g.nodes[v]
        return {
            "u": str(u), "v": str(v),
            "name": d.get("name") or "Voie sans nom",
            "highway": d.get("highway", ""),
            "length_m": round(d["length"], 1),
            "criticality": self.edge_criticality(u, v),
            "is_bridge": frozenset((u, v)) in self.bridges,
            "coords": [[nu["y"], nu["x"]], [nv["y"], nv["x"]]],
        }

    # ---------------------------------------------------------------- routing
    def _path_result(self, nodes: list, g: nx.Graph | None = None) -> PathResult:
        g = g or self.g
        length = time = 0.0
        names: list[str] = []
        for u, v in zip(nodes, nodes[1:]):
            d = self.g.edges[u, v]
            length += d["length"]
            time += d["travel_time"]
            if d.get("name") and (not names or names[-1] != d["name"]):
                names.append(d["name"])
        coords = [(self.g.nodes[n]["y"], self.g.nodes[n]["x"]) for n in nodes]
        return PathResult(nodes, coords, round(length, 1), round(time, 1),
                          round(length / 1000 * CO2_G_PER_KM, 1), names)

    def route(self, origin: tuple[float, float], dest: tuple[float, float],
              hazards: Iterable[tuple[tuple, float]] = (), avoid_strength: float = 4.0) -> dict:
        """Fastest route vs hazard-aware route.

        hazards: iterable of ((u, v), severity 0..1). Each hazard multiplies the
        edge cost by (1 + avoid_strength * severity) — a soft penalty, so the
        route still passes when no reasonable alternative exists.
        """
        s, t = self.nearest_node(*origin), self.nearest_node(*dest)
        penalty: dict[frozenset, float] = {}
        for (u, v), sev in hazards:
            key = frozenset((u, v))
            penalty[key] = max(penalty.get(key, 0.0), sev)

        def weight(u, v, d):
            return d["travel_time"] * (1 + avoid_strength * penalty.get(frozenset((u, v)), 0.0))

        fastest = nx.shortest_path(self.g, s, t, weight="travel_time")
        safe = nx.shortest_path(self.g, s, t, weight=weight)
        f, r = self._path_result(fastest), self._path_result(safe)
        def hits(nodes):
            return sum(1 for e in zip(nodes, nodes[1:]) if frozenset(e) in penalty)

        return {
            "fastest": {**f.__dict__, "hazards_on_route": hits(fastest)},
            "eco_route": {**r.__dict__, "hazards_on_route": hits(safe)},
            "extra_time_s": round(r.time_s - f.time_s, 1),
            "hazards_avoided": hits(fastest) - hits(safe),
        }

    def closure_impact(self, u, v, samples: int = 60, seed: int = 7) -> dict:
        """What happens if segment (u, v) is closed (works, flooding, accident)?"""
        g2 = self.g.copy()
        g2.remove_edge(u, v)
        base = self.g.edges[u, v]["travel_time"]
        try:
            detour = nx.shortest_path(g2, u, v, weight="travel_time")
            detour_time = sum(g2.edges[a, b]["travel_time"] for a, b in zip(detour, detour[1:]))
            detour_len = sum(g2.edges[a, b]["length"] for a, b in zip(detour, detour[1:]))
            disconnected = 0
        except nx.NetworkXNoPath:
            detour, detour_time, detour_len = [], math.inf, math.inf
            disconnected = len(min(nx.connected_components(g2), key=len))

        # Network-wide effect: sample O-D pairs, compare mean travel time.
        rng = random.Random(seed)
        nodes = list(self.g.nodes)
        pairs = [(rng.choice(nodes), rng.choice(nodes)) for _ in range(samples)]
        affected, delta = 0, 0.0
        for a, b in pairs:
            t1 = nx.shortest_path_length(self.g, a, b, weight="travel_time")
            try:
                t2 = nx.shortest_path_length(g2, a, b, weight="travel_time")
            except nx.NetworkXNoPath:
                affected += 1
                continue
            if t2 > t1 + 1e-6:
                affected += 1
                delta += t2 - t1
        return {
            "edge": self.edge_info(u, v),
            "detour_extra_m": None if math.isinf(detour_len) else round(detour_len - self.g.edges[u, v]["length"], 1),
            "detour_extra_s": None if math.isinf(detour_time) else round(detour_time - base, 1),
            "detour_coords": [(self.g.nodes[n]["y"], self.g.nodes[n]["x"]) for n in detour],
            "nodes_cut_off": disconnected,
            "sampled_trips_affected_pct": round(100 * affected / samples, 1),
            "avg_delay_on_affected_s": round(delta / affected, 1) if affected else 0.0,
        }

    def crew_tour(self, depot: tuple[float, float], stops: list[tuple[float, float]]) -> dict:
        """Near-optimal visiting order for a maintenance crew (TSP: NN + 2-opt)."""
        pts = [depot] + stops
        nodes = [self.nearest_node(*p) for p in pts]
        n = len(nodes)
        dist = np.zeros((n, n))
        for i, s in enumerate(nodes):
            lengths = nx.single_source_dijkstra_path_length(self.g, s, weight="travel_time")
            for j, t in enumerate(nodes):
                dist[i, j] = lengths.get(t, 1e9)

        order, left = [0], set(range(1, n))
        while left:
            nxt = min(left, key=lambda j: dist[order[-1], j])
            order.append(nxt)
            left.remove(nxt)
        order.append(0)  # back to depot

        def cost(o):
            return sum(dist[a, b] for a, b in zip(o, o[1:]))

        improved = True
        while improved:  # 2-opt: reverse sub-tours while it shortens the tour
            improved = False
            for i in range(1, len(order) - 2):
                for j in range(i + 1, len(order) - 1):
                    new = order[:i] + order[i:j + 1][::-1] + order[j + 1:]
                    if cost(new) < cost(order) - 1e-9:
                        order, improved = new, True

        legs = []
        for a, b in zip(order, order[1:]):
            legs.extend(nx.shortest_path(self.g, nodes[a], nodes[b], weight="travel_time")[(1 if legs else 0):])
        p = self._path_result(legs)
        return {
            "visit_order": [i - 1 for i in order[1:-1]],  # indices into `stops`
            "total_time_s": round(cost(order), 1),
            "length_m": p.length_m,
            "coords": p.coords,
        }


# ---------------------------------------------------------------- demo graph
def _offset(lat: float, lon: float, km: float, bearing_deg: float) -> tuple[float, float]:
    b = math.radians(bearing_deg)
    return (lat + km * math.cos(b) / 111.0,
            lon + km * math.sin(b) / (111.0 * math.cos(math.radians(lat))))


def build_demo_graph() -> nx.Graph:
    """Schematic Sfax: radial roads fanning out from the centre, cut by ring roads.

    The sea lies to the south-east, so rings are open arcs (no edge across the
    gulf). Used for tests/CI and as a fallback before the OSM import.
    """
    g = nx.Graph()
    lat0, lon0 = SFAX_CENTER
    g.add_node("C", y=lat0, x=lon0)
    for name, bearing in RADIAL_ROADS:
        prev = "C"
        for km in RADIAL_STOPS_KM:
            nid = f"{name}@{km}"
            lat, lon = _offset(lat0, lon0, km, bearing)
            g.add_node(nid, y=lat, x=lon)
            hw = "primary" if km <= 4 else "trunk"
            _add(g, prev, nid, name, hw)
            prev = nid
    arc = sorted(RADIAL_ROADS, key=lambda r: (r[1] - 200) % 360)  # west-around, coast to coast
    for ring, km in RING_ROADS:
        for (a, _), (b, _) in zip(arc, arc[1:]):
            _add(g, f"{a}@{km}", f"{b}@{km}", ring, "secondary")
    return g


def _add(g: nx.Graph, u, v, name: str, hw: str) -> None:
    length = haversine_m(g.nodes[u]["y"], g.nodes[u]["x"], g.nodes[v]["y"], g.nodes[v]["x"])
    g.add_edge(u, v, length=length, travel_time=length / (DEFAULT_SPEED_KMH[hw] / 3.6), name=name, highway=hw)


_graph: RoadGraph | None = None


def get_graph() -> RoadGraph:
    global _graph
    if _graph is None:
        from ..config import get_settings
        _graph = RoadGraph.load(get_settings().graph_path)
    return _graph
