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


def wordcloud(frequency_dict):
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


def generate_wordcloud():
    tag_keys = list(st.session_state.tags_in_bbox.keys())
    default_key_index = tag_keys.index("amenity") if "amenity" in tag_keys else 0

    # Select a tag key for wordcloud visualisation
    st.selectbox(
        label="Select a different tag",
        options=st.session_state.tags_in_bbox.keys(),
        index=default_key_index,
        key="selected_key",
    )

    # Return a dictionary with the frequency each value appears in the bounding box
    st.session_state.value_frequency = count_tag_frequency_old(
        st.session_state.nodes, tag=st.session_state.selected_key
    )

    # Generate word cloud
    values_wordcloud = wordcloud(st.session_state.value_frequency)
    st.subheader(f"Things tagged as '{st.session_state.selected_key}'")
    st.image(values_wordcloud.to_array(), use_column_width=True)
