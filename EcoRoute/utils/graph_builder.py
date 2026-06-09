import osmnx as ox

def load_graphml(graph_path):
    # Load a road network graph from a GraphML file
    print(f"Loading road network data from {graph_path}...")
    G = ox.load_graphml(graph_path)
    print("Road network data loaded successfully.")
    return G

def base_travel_time(G, speed_kmph=30):
    # Calculate base travel time for each edge in the graph (min)
    for u, v, k, data in G.edges(keys=True, data=True):
        dist_km = data["length"] /1000
        data['base_time'] = (dist_km / speed_kmph) * 60  # in minutes

    return G

