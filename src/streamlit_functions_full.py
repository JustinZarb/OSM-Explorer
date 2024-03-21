import requests
import json
import streamlit as st
import folium
from streamlit_folium import st_folium, folium_static
import matplotlib.pyplot as plt
from wordcloud import WordCloud, STOPWORDS, ImageColorGenerator
import utm
from pyproj import CRS, Transformer
import pandas as pd
import plotly.express as px
import osmnx as ox
import folium
import contextily as cx
from shapely.geometry import Polygon, Point, LineString, mapping, MultiPolygon
import pydeck as pdk
from math import sqrt, log
from geopandas import GeoDataFrame
import hashlib


def overpass_to_feature_group(data_str=""):
    """Takes the  result of an overpass query in string form as input.
    Selects 'elements' as nodes. Creates a folium.FeatureGroup.
    Adds a Marker for each node,  with coordinates and a tags dictionary."""
    # need to convert the string into a dictionary first.
    data = folium.GeoJson(data_str).data
    # these are the nodes we want
    if "elements" in data:
        elements = data["elements"]
        fg = folium.FeatureGroup(name="Elements from overpass")
        for node in elements:
            node_data = [(node["lat"], node["lon"], node["tags"])]
            # the tags content needs to be reformatted
            for lat, lon, tags in node_data:
                tags_content = "<br>".join(
                    [f"<b>{k}</b>: {v}" for k, v in tags.items()]
                )
                fg.add_child(folium.Marker(location=[lat, lon], popup=tags_content))
        return fg
    else:
        return None


def overpass_to_circles(data_str=""):
    data = folium.GeoJson(data_str).data
    # these are the nodes we want
    if "elements" in data:
        elements = data["elements"]
        circles = create_circles_from_nodes(elements)
        return circles
    else:
        return None


def create_circles_from_nodes(nodes):
    # Create a feature group
    feature_group = folium.FeatureGroup(name="circles")
    for node in nodes:
        # Loop over each node in the 'elements' key of the JSON object
        if node["type"] == "node":
            node_data = [(node["lat"], node["lon"], node["tags"])]
            # the tags content needs to be reformatted
            for lat, lon, tags in node_data:
                tags_content = "<br>".join(
                    [f"<b>{k}</b>: {v}" for k, v in tags.items()]
                )
                circle = folium.Circle(
                    location=[lat, lon],
                    radius=5,  # Set the radius as needed
                    color="blue",  # Set a default color or use a function to determine color based on tags
                    fill=True,
                    fill_color="blue",  # Set a default color or use a function to determine color based on tags
                    fill_opacity=0.4,
                    tooltip=tags_content,
                )
                # Add the circle to the feature group
                feature_group.add_child(circle)
        elif node["type"] == "area":
            pass
    return feature_group


def create_circles_from_node_dict(nodes):
    # Loop over each node in the 'bar' key of the JSON object
    circles = folium.FeatureGroup(name="State bounds")
    for tag_key in nodes.keys():
        color = word_to_color(tag_key)
        for node in nodes[tag_key]:
            # Get the latitude and longitude of the node
            lat = node["lat"]
            lon = node["lon"]

            # Get the 'tags' dictionary
            tags = node["tags"]

            # Create a string for the hover text
            hover_text = (
                f"{tag_key}: {tags.get('name', 'N/A')}\n"  # Add more details here
            )

            # Create a circle on the map for this key
            circles.add_child(
                folium.Circle(
                    location=[lat, lon],
                    radius=10,  # Set the radius as needed
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.4,
                    tooltip=hover_text,
                )
            )

    return circles


def calculate_center(bounds):
    center = [(bounds[0][0] + bounds[1][0]) / 2, (bounds[0][1] + bounds[1][1]) / 2]
    return center


def calculate_zoom_level(bounds):
    """Calculate zoom level for PYDECK
    Args:
        gdf (_type_): _description_

    Returns:
        _type_: _description_
    """
    # Get the bounds of the geometry
    try:
        minx, miny, maxx, maxy = bounds[0][0], bounds[0][1], bounds[1][0], bounds[1][1]

        # Calculate the diagonal length of the bounding box
        diagonal_length = sqrt((maxx - minx) ** 2 + (maxy - miny) ** 2)

        # Calculate a base zoom level based on the diagonal length
        # This is a rough estimate and may need to be adjusted to fit your specific needs
        base_zoom = 9 - log(maxx - minx)

        # Make sure the zoom level is within the valid range (0-22)
        zoom_level = max(0, min(base_zoom, 22))

    except:
        # st.markdown(["probably a math error. bounds:",  bounds,])
        zoom_level = 17
    return zoom_level


def calculate_parameters_for_map(overpass_answer=None, gdf=None):
    """
    takes an overpass answer string or a geodataframe
    and returns:
    fg, center, zoom
    """
    default_bounds = [[52.5210821, 13.3942864], [52.525776, 13.4038867]]
    fg = None
    bounds = default_bounds

    if overpass_answer is not None:
        fg = overpass_to_circles(overpass_answer)
        bounds = fg.get_bounds()
        # Nasty hack for empty answers
        if bounds == [[None, None], [None, None]]:
            bounds = default_bounds
    elif gdf is not None:
        # Drop missing geometries
        gdf = gdf[gdf["geometry"].notna()]

        # Repair invalid geometries
        gdf["geometry"] = gdf["geometry"].buffer(0)

        # Convert to GeoJSON
        geojson_data = json.loads(gdf.to_json())

        # Calculate bounds from GeoJSON
        if geojson_data["features"]:
            all_coords = [
                feat["geometry"]["coordinates"] for feat in geojson_data["features"]
            ]
            lats = [coord[1] for coords in all_coords for coord in coords]
            lons = [coord[0] for coords in all_coords for coord in coords]
            bounds = [[min(lats), min(lons)], [max(lats), max(lons)]]
        else:
            bounds = default_bounds
        fg = geojson_data

    center = calculate_center(bounds)
    zoom = calculate_zoom_level(bounds)
    return fg, center, zoom


def calculate_parameters_for_map_old(
    overpass_answer=None,
    gdf=None,
):
    """
    takes an overpass answer string
    and returns:
    fg, center, zoom
    """
    default_bounds = [[52.5210821, 13.3942864], [52.525776, 13.4038867]]
    fg = None
    bounds = default_bounds

    if overpass_answer is not None:
        fg = overpass_to_circles(overpass_answer)
        bounds = fg.get_bounds()
        # Nasty hack for empty answers
        if bounds == [[None, None], [None, None]]:
            bounds = default_bounds
    elif gdf is not None:
        print(gdf)
        south = gdf.loc[:, "bbox_south"].min()
        north = gdf.loc[:, "bbox_north"].max()
        west = gdf.loc[:, "bbox_west"].min()
        east = gdf.loc[:, "bbox_east"].max()
        bounds = [[south, west], [north, east]]

    center = calculate_center(bounds)
    zoom = calculate_zoom_level(bounds)
    return fg, center, zoom


def name_to_gdf(place_name):
    """Return a Pandas.GeoDataframe object for a name if Nominatim can find it

    Args:
        place_name (str): eg. "Berlin"

    Returns:
        gdf: a geodataframe
    """
    # Use OSMnx to geocode the location (OSMnx uses some other libraries)
    gdf = ox.geocode_to_gdf(place_name)
    return gdf


def map_location(
    gdf=None,
):
    """Create a map object given an optional gdf and feature group
    Args:
        gdf (_type_, optional): _description_. Defaults to None.

    Returns:
        map object: _description_
    """
    # Initialize the map
    m = folium.Map(height="50%")

    if gdf is None:
        _, center, zoom = calculate_parameters_for_map()

    # Add the gdf to the map
    if gdf is not None:
        folium.GeoJson(gdf).add_to(m)

    # Fit the map to the bounds of all features
    m.fit_bounds(m.get_bounds())
    return m


def word_to_color(word):
    # Use MD5 hash to convert the word into a hexadecimal number
    hash_object = hashlib.md5(word.encode())
    hex_dig = hash_object.hexdigest()
    # Take the first 6 characters of the hex number and convert it into an RGB color
    hex_color = hex_dig[:6]
    r = int(hex_color[:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    a = 255
    # Return the RGB color as a tuple
    return f"rgb({r}, {g}, {b})"


def overpass_query(query):
    overpass_url = "http://overpass-api.de/api/interpreter"
    response = requests.get(overpass_url, params={"data": query})
    data = response.json()
    return data


def bbox_from_st_data(st_data):
    """
    Return a list of coordinates [W, S, N, E]
    bounds = {'_southWest': {'lat': 52.494239118767496, 'lng': 13.329420089721681}, '_northEast': {'lat': 52.50338318818063, 'lng': 13.344976902008058}}
    """
    bounds = st_data["bounds"]
    bbox = [
        bounds["_southWest"]["lat"],
        bounds["_southWest"]["lng"],
        bounds["_northEast"]["lat"],
        bounds["_northEast"]["lng"],
    ]
    return bbox


def gdf_data(row, original_crs):
    """Get the area of a polygon
    can take a row of a gdf"""
    utm_zone = utm.latlon_to_zone_number(row["lat"], row["lon"])
    south = row["lat"] < 0
    utm_crs = CRS.from_dict({"proj": "utm", "zone": utm_zone, "south": south})
    epsg_code = utm_crs.to_authority()[1]
    unit = list({ai.unit_name for ai in utm_crs.axis_info})[0]
    gdf_projected = GeoDataFrame([row], crs=original_crs).to_crs(epsg_code)
    area = gdf_projected.area.values[0]
    return pd.Series({"area": area, "unit": f"square {unit}"})


def longest_distance_to_vertex(geometry):
    """Calculate the radius between the polygon centroid and its furthest point.
    Not callable by the LLM
    Args:
        polygon (shapely.geometry.Polygon): _description_
    Returns:
        max_distance (float): _description_
    """
    # Check if the geometry is a MultiPolygon
    if isinstance(geometry, MultiPolygon):
        # If it is, iterate over the individual polygons
        polygons = list(geometry)
    else:
        # If it's not a MultiPolygon, assume it's a single Polygon and put it in a list
        polygons = [geometry]

    max_distance = 0
    for polygon in polygons:
        centroid = polygon.centroid
        # Calculate the distance from the centroid to each vertex
        distances = [
            centroid.distance(Point(vertex)) for vertex in polygon.exterior.coords
        ]
        # Update max_distance if the maximum distance for this polygon is greater
        max_distance = max(max_distance, max(distances))

    # Return the maximum distance
    return max_distance


def add_value(tag_frequency, t, v):
    if isinstance(v, str):
        values = v.split(";")
        for value in values:
            if t in tag_frequency:
                if (
                    value not in tag_frequency[t]
                ):  # Check if value is not already in the list
                    tag_frequency[t].append(value)
            else:
                tag_frequency[t] = [value]
    else:
        if t in tag_frequency:
            if (
                str(v) not in tag_frequency[t]
            ):  # Check if value is not already in the list
                tag_frequency[t].append(str(v))
        else:
            tag_frequency[t] = [str(v)]
    return tag_frequency


def count_tag_frequency_in_nodes(nodes, tag=None):
    tag_frequency = {}

    for node in nodes:
        if "tags" in node:
            for t, v in node["tags"].items():
                # Split the tag on the first separator
                t = t.split(":")[0]

                if tag is None:
                    # Collecting unique values for each tag
                    tag_frequency = add_value(tag_frequency, t, v)
                else:
                    # Collecting unique values for a specific tag
                    if t == tag:
                        tag_frequency = add_value(tag_frequency, t, v)

    return tag_frequency


def count_tag_frequency_old(data, tag=None):
    tag_frequency = {}

    for element in data["elements"]:
        if "tags" in element:
            for t, v in element["tags"].items():
                if tag is None:
                    # Counting tag frequency
                    if t in tag_frequency:
                        tag_frequency[t] += 1
                    else:
                        tag_frequency[t] = 1
                else:
                    # Counting value frequency for a specific tag
                    if t == tag:
                        if v in tag_frequency:
                            tag_frequency[v] += 1
                        else:
                            tag_frequency[v] = 1

    return tag_frequency


def count_tag_frequency(datasets, tag=None):
    # Combine elements of all datasets into a single list
    nodes = [element for data in datasets for element in data["elements"]]
    return count_tag_frequency_in_nodes(nodes, tag)


def count_unique_values(datasets, tag=None):
    unique_values = set()

    # Combine elements of all datasets into a single list
    elements = [element for data in datasets for element in data["elements"]]

    for element in elements:
        if "tags" in element:
            for t, v in element["tags"].items():
                # Split the tag on the first separator
                t = t.split(":")[0]

                if t == tag:
                    unique_values.add(v)

    return {tag: len(unique_values)}


def count_value_frequency(datasets):
    value_frequency = {}

    # Combine elements of all datasets into a single list
    elements = [element for data in datasets for element in data["elements"]]

    for element in elements:
        if "tags" in element:
            for _, v in element["tags"].items():
                # Counting value frequency
                if v in value_frequency:
                    value_frequency[v] += 1
                else:
                    value_frequency[v] = 1

    # Sort the dictionary by its values in descending order
    value_frequency = {
        k: v
        for k, v in sorted(
            value_frequency.items(), key=lambda item: item[1], reverse=True
        )
    }

    return value_frequency


def generate_wordcloud(frequency_dict):
    tags_freq = [(tag, freq) for tag, freq in frequency_dict.items()]
    tags_freq.sort(key=lambda x: x[1], reverse=True)  # Sort tags by frequency
    tags_freq_200 = tags_freq[:200]  # Limit to top 200 tags

    wordcloud = WordCloud(
        width=800,
        height=200,
        background_color="white",
        stopwords=STOPWORDS,
        colormap="viridis",
        random_state=42,
    )
    wordcloud.generate_from_frequencies({tag: freq for tag, freq in tags_freq_200})
    return wordcloud


def get_nodes_with_tags_in_bbox(bbox: list, what_to_get="nodes"):
    """Get unique tag keys within a bounding box and plot the top 200 in a wordcloud
    In this case it is necessary to run a query in overpass because
    osmnx.geometries.geometries_from_bbox requires an input for "tags", but here
    we want to get all of them.

    ToDo: Limit the query size

    returns:
        data: the query response in json format
    """
    overpass_url = "http://overpass-api.de/api/interpreter"
    if what_to_get == "nodes":
        overpass_query = f"""
        [out:json];
        (
        node({bbox[0]}, {bbox[1]}, {bbox[2]}, {bbox[3]})[~"."~"."];
        );
        out body;
        """
    elif "way" in what_to_get.lower():
        overpass_query = f"""
        [out:json];
        (
        way({bbox[0]}, {bbox[1]}, {bbox[2]}, {bbox[3]})[~"."~"."];
        );
        out body;
        """

    response = requests.get(overpass_url, params={"data": overpass_query})
    data = response.json()

    return data


def save_nodes_to_json(self, file_path: str, this_run_name: str, log: dict):
    """Raw pasted from naturalmaps_bot

    Args:
        file_path (str): _description_
        this_run_name (str): _description_
        log (dict): _description_
    """
    json_file_path = file_path if file_path.endswith(".json") else file_path + ".json"
    # Check if the folder exists and if not, create it.
    folder_path = os.path.dirname(json_file_path)
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    # Check if the file exists
    if os.path.isfile(json_file_path):
        # If it exists, open it and load the JSON data
        try:
            with open(json_file_path, "r") as f:
                data = json.load(f)
        except:
            data = {}
    else:
        # If it doesn't exist, create an empty dictionary
        data = {}

    data[this_run_name] = {
        "log": log,
    }
    try:
        with open(json_file_path, "w") as f:
            json.dump(data, f, indent=4)
    except TypeError as e:
        with open("error.txt", "w") as error_file:
            error_file.write(str(e))


def get_tag_keys():
    # Seems excessive
    url = "https://taginfo.openstreetmap.org/api/4/keys/all"
    response = requests.get(url)
    data = response.json()
    return data["data"]


def get_points_from_bbox_and_tags(bbox: list, tags: dict):
    """OX has a get things from bbox already..."""
    # bbox = [S, W, N, E]
    west = bbox[1]
    south = bbox[0]
    north = bbox[2]
    east = bbox[3]

    poly_from_bbox = Polygon(
        [(west, south), (east, south), (east, north), (west, north)]
    )

    geometries = ox.geometries_from_polygon(poly_from_bbox, tags)
    return geometries


def filter_nodes_with_tags(nodes: dict, tags: dict):
    """Get a subset of nodes from some geometry returned by overpass

    Args:
        nodes (dict): Objects returned from Overpass
        tags (dict): Tags to search for
    """
    selection = {}

    for key, values in tags.items():
        for value in values:
            selection[value] = [
                e
                for e in nodes["elements"]
                if (key in e["tags"].keys()) and (value in e["tags"].values())
            ]

    return selection
