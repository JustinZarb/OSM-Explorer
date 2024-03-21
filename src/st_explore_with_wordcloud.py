import src.streamlit_functions as st_functions
import streamlit as st
import pandas as pd


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
    st.session_state.value_frequency = st_functions.count_tag_frequency_old(
        st.session_state.nodes, tag=st.session_state.selected_key
    )

    # Generate word cloud
    values_wordcloud = st_functions.generate_wordcloud(st.session_state.value_frequency)
    st.subheader(f"Things tagged as '{st.session_state.selected_key}'")
    st.image(values_wordcloud.to_array(), use_column_width=True)


def explore_data(st_data):
    if st_data["zoom"] >= 13:
        # Initialize the checkbox value in the session state if it's not already set
        if "explore_area" not in st.session_state:
            st.session_state.explore_area = False

        def explore_button():
            if st.session_state["explore_area"]:
                st.session_state["explore_area"] = False
            else:
                st.session_state["explore_area"] = True

        # Use the session state value for the checkbox
        st.button(
            label=f"Common tags in this view",
            on_click=explore_button,
        )
        # Create a checkbox that will control whether the map and data are stored in the session state
        if st.session_state.explore_area:
            # check if  m and st_data already exist in the session state
            if "st_data" in st.session_state:
                # st_data already in session state
                pass
            else:
                # Store the map and data in the session state
                st.session_state["st_data"] = st_data
                # get bbox
                st.session_state["bbox"] = st_functions.bbox_from_st_data(
                    st.session_state.st_data
                )
                # query all nodes with tags in bbox
                st.session_state["nodes"] = st_functions.get_nodes_with_tags_in_bbox(
                    st.session_state.bbox
                )
                # get the tag content as a dictionary
                st.session_state["tags_in_bbox"] = st_functions.count_tag_frequency_old(
                    st.session_state.nodes
                )

            # show a wordcloud of amenities in the search area
            generate_wordcloud()

            # Multiselect options from the currently selected tag
            if "multiselected_options" not in st.session_state:
                st.session_state.multiselected_options = []

            st.multiselect(
                "Add items to map:",
                options=st.session_state.value_frequency.keys(),
                key="multiselected_options",
            )

            # Dictionary of key:value pairs where the keys are a tag key and the value are different tag values
            st.session_state.mask = {
                st.session_state.selected_key: st.session_state.multiselected_options
            }
            # filter the nodes in the bounding box which match the mask
            st.session_state.selected_nodes = st_functions.filter_nodes_with_tags(
                st.session_state.nodes, st.session_state.mask
            )
            ## Create colored circles for each of the above nodes
            st.session_state.circles = st_functions.create_circles_from_node_dict(
                st.session_state.selected_nodes
            )
            # Reset the checkbox
            st.session_state.add_selection = False
            st_functions.update_map()

            if "selected_nodes" in st.session_state:
                st.subheader("Currently shown on map:")
                for key, value in st.session_state.selected_nodes.items():
                    st.markdown(f"{key}")
                    df = pd.json_normalize(value, sep="\n")
                    st.table(df)

        else:
            # delete
            temporary_variables = [
                "gdf",
                "m",
                "st_data",
                "bbox",
                "tags_in_bbox",
                "nodes",
            ]
            for var in temporary_variables:
                if var in st.session_state:
                    del st.session_state[var]

    else:
        st.markdown("Zoom in to see what's in the map")
