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
