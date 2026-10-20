import networkx as nx

from app.data.sfax import RADIAL_ROADS
from app.graph.road_graph import RoadGraph, build_demo_graph


def g():
    return RoadGraph(build_demo_graph(), "demo")


def test_demo_graph_is_connected_and_named():
    rg = g()
    assert nx.is_connected(rg.g)
    names = rg.road_names()
    for road, _ in RADIAL_ROADS:
        assert road in names
    assert "Rocade km 11" in names


def test_exit_segments_are_bridges_and_maximally_critical():
    rg = g()
    u, v = "Route de Gabès@11.0", "Route de Gabès@14.0"
    assert frozenset((u, v)) in rg.bridges
    assert rg.edge_criticality(u, v) >= 0.9
    impact = rg.closure_impact(u, v, samples=30)
    assert impact["nodes_cut_off"] == 1 and impact["detour_extra_m"] is None


def test_ring_gives_redundancy_inside_the_city():
    rg = g()
    u, v = "Route de Tunis@4.0", "Route de Tunis@5.5"
    assert frozenset((u, v)) not in rg.bridges
    imp = rg.closure_impact(u, v, samples=30)
    assert imp["detour_extra_m"] > 0 and imp["nodes_cut_off"] == 0


def test_nearest_edge_snaps_to_a_road():
    rg = g()
    n = rg.g.nodes["Route de Mahdia@4.0"]
    u, v = rg.nearest_edge(n["y"] + 0.0003, n["x"])
    assert "Route de Mahdia@4.0" in (u, v)


def test_eco_route_avoids_hazard_when_cheap_alternative_exists():
    rg = g()
    o = rg.g.nodes["Route de Tunis@7.0"]
    d = rg.g.nodes["C"]
    plain = rg.route((o["y"], o["x"]), (d["y"], d["x"]))
    first_edge = tuple(plain["fastest"]["nodes"][:2])
    res = rg.route((o["y"], o["x"]), (d["y"], d["x"]), hazards=[(first_edge, 1.0)], avoid_strength=20)
    assert res["fastest"]["hazards_on_route"] == 1
    assert res["eco_route"]["hazards_on_route"] == 0
    assert res["extra_time_s"] >= 0


def test_crew_tour_visits_every_stop_once():
    rg = g()
    stops = [(rg.g.nodes[n]["y"], rg.g.nodes[n]["x"]) for n in
             ["Route de Gremda@7.0", "Route de Tunis@4.0", "Route de Gabès@9.0", "Route de Mahdia@2.5"]]
    tour = rg.crew_tour((rg.g.nodes["C"]["y"], rg.g.nodes["C"]["x"]), stops)
    assert sorted(tour["visit_order"]) == [0, 1, 2, 3]
    assert tour["total_time_s"] > 0
