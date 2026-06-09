import osmnx as ox
import os

def road_graph(place, save_path):
    """Download road network data from OpenStreetMap and save it locally."""
    ox.settings.use_cache = True
    ox.settings.log_console = True

    print(f"Downloading road network data for {place}...")

    G = ox.graph_from_place(place, network_type='drive', simplify=True)

    # Edge lengths are automatically added by OSMnx
    # No need to call add_edge_lengths()

    #chck if directory exists
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    #save
    ox.save_graphml(G, save_path)
    print(f"Road network data saved to {save_path}")
    return G