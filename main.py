import sys

import numpy as np
import osmnx as ox
import pandas as pd
import time as time
import matplotlib.pyplot as plt

def main():
    address = "600 Montgomery St, San Francisco, California, USA"

    place = "San Francisco"
    G = ox.graph_from_place(place_query, network_type="drive")

    G = add_node_elevations_open(G)
    G = ox.elevation.add_edge_grades(G)

    nc = ox.plot.get_node_colors_by_attr(G, "elevation", cmap="plasma")
    fig, ax = ox.plot_graph(G, node_color=nc, node_size=5, edge_color="#333333", bgcolor="k")

if __name__ == "__main__":
    main()

def add_node_elevations_open(G, max_locations_per_batch=350, precision=3, add_edge_grades=True):
    """
    Add `elevation` (meters) attribute to each node using a web service.

    This uses the open-elevation API.

    See also the `add_edge_grades` function.

    Parameters
    ----------
    G : networkx.MultiDiGraph
        input graph
    max_locations_per_batch : int
        max number of coordinate pairs to submit in each API call (if this is
        too high, the server will reject the request because its character
        limit exceeds the max allowed)
    pause_duration : float
        time to pause between API calls, which can be increased if you get
        rate limited
    precision : int
        decimal precision to round elevation values

    Returns
    -------
    G : networkx.MultiDiGraph
        graph with node elevation attributes
    """

    url = "https://api.open-elevation.com/api/v1/lookup"
    print(f"Requesting node elevations from {url}")

    # make a pandas series of all the nodes' coordinates as 'lat,lng'
    # round coordinates to 5 decimal places (approx 1 meter) to be able to fit
    # in more locations per API call

    node_points = pd.Series(
        {node: f'{data["y"]:.5f},{data["x"]:.5f}' for node, data in G.nodes(data=True)}
    )

    locations = [
        {"latitude": round(data["y"],5), "longitude": round(data["x"],5)}
        for node, data in G.nodes(data=True)
    ]


    n_calls = int(np.ceil(len(node_points) / max_locations_per_batch))
    print(f"Requesting node elevations from the API in {n_calls} calls")

    # break the series of coordinates into chunks of size max_locations_per_batch
    # API format is locations=lat,lng|lat,lng|lat,lng|lat,lng...
    results = []
    for i in range(0, len(node_points), max_locations_per_batch):
        locations_chunk = {"locations": locations[i : i + max_locations_per_batch]}

        try:
            response = requests.post(url, json = locations_chunk)
            response_json = response.json()
            results.extend(response_json["results"])
        except Exception as e:
            print(e)
            print(f"Server responded with {response.status_code}: {response.reason}")


    # sanity check that all our vectors have the same number of elements
    if not (len(results) == len(G) == len(node_points)):
        raise Exception(f"Graph has {len(G)} nodes but we received {len(results)} results from elevation API" )
    else: print(f"Graph has {len(G)} nodes and we received {len(results)} results from elevation API")

    # add elevation as an attribute to the nodes
    df = pd.DataFrame(node_points, columns=["node_points"])
    df["elevation"] = [result["elevation"] for result in results]
    df["elevation"] = df["elevation"].round(precision)
    nx.set_node_attributes(G, name="elevation", values=df["elevation"].to_dict())
    print("Added elevation data from open elevation to all nodes.")

    if add_edge_grades:
        elev_lookup = G.nodes(data="elevation")
        u, v, k, lengths = zip(*G.edges(keys=True, data="length"))
        uvk = tuple(zip(u, v, k))

        # calculate edges' elevation changes from u to v then divide by lengths
        elevs = np.array([(elev_lookup[u], elev_lookup[v]) for u, v, k in uvk])
        grades = ((elevs[:, 1] - elevs[:, 0]) / np.array(lengths)).round(precision)
        nx.set_edge_attributes(G, dict(zip(uvk, grades)), name="grade")

        # add grade absolute value to the edge attributes
        nx.set_edge_attributes(G, dict(zip(uvk, np.abs(grades))), name="grade_abs")
        utils.log("Added grade attributes to all edges.")

    return G
