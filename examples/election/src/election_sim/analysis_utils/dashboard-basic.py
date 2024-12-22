import argparse
import base64

import dash
import dash_cytoscape as cyto
import networkx as nx
import pandas as pd
import plotly.graph_objs as go
from dash import Input, Output, State, dcc, html
from output_proc_utils import post_process_output
from plotly.subplots import make_subplots

cyto.load_extra_layouts()
from io import StringIO


def compute_positions(graph):
    pos = nx.kamada_kawai_layout(graph, scale=750)
    scaled_pos = {}
    for node, (x, y) in pos.items():
        scaled_pos[node] = {"x": x, "y": y}

    return scaled_pos


# Serialization function to convert complex data structures into JSON-serializable format
def serialize_data(follow_graph, interactions_by_episode, posted_users_by_episode, toots, votes):
    return {
        "nodes": list(follow_graph.nodes),
        "edges": list(follow_graph.edges),
        "interactions_by_episode": interactions_by_episode,
        "posted_users_by_episode": {k: list(v) for k, v in posted_users_by_episode.items()},
        "toots": toots,
        "votes": votes,
    }


# Deserialization function to convert JSON-serializable data back into original structures
def deserialize_data(serialized):
    follow_graph = nx.DiGraph()
    follow_graph.add_nodes_from(serialized["nodes"])
    follow_graph.add_edges_from(serialized["edges"])

    # Convert episode keys back to integers
    interactions_by_episode = {int(k): v for k, v in serialized["interactions_by_episode"].items()}
    posted_users_by_episode = {
        int(k): set(v) for k, v in serialized["posted_users_by_episode"].items()
    }
    toots = serialized["toots"]
    votes = {int(k): v for k, v in serialized["votes"].items()}
    return follow_graph, interactions_by_episode, posted_users_by_episode, toots, votes


def get_target_user(row):
    if row.label == "post":
        target_user = row.source_user
    elif row.label == "like_toot" or row.label == "boost_toot":
        target_user = row.data["target_user"]
    elif row.label == "reply":
        target_user = row.data["reply_to"]["target_user"]
    return target_user


def get_int_dict(int_df):
    past = dict(
        zip(
            ["post", "like_toot", "boost_toot", "reply"],
            ["posted", "liked", "boosted", "replied"],
            strict=False,
        )
    )
    int_df["int_data"] = int_df.apply(
        lambda x: {
            "action": past[x.label],
            "episode": x.episode,
            "source": x.source_user,
            "target": get_target_user(x),
            "toot_id": x.data["toot_id"],
        },
        axis=1,
    )
    int_df.int_data = int_df.apply(
        lambda x: x.int_data | {"parent_toot_id": x.data["reply_to"]["toot_id"]}
        if x.label == "reply"
        else x.int_data,
        axis=1,
    )
    return int_df.groupby("episode")["int_data"].apply(list).to_dict()


def get_toot_dict(int_df):
    past = dict(
        zip(
            ["post", "like_toot", "boost_toot", "reply"],
            ["posted", "liked", "boosted", "replied"],
            strict=False,
        )
    )
    text_df = int_df.loc[(int_df.label == "post") | (int_df.label == "reply"), :].reset_index(
        drop=True
    )

    # handle Nones as toot_ids by appending an index
    no_toot_id = text_df.data.apply(lambda x: x["toot_id"] is None)
    text_df["no_toot_id_idx"] = -1
    text_df.loc[no_toot_id, "no_toot_id_idx"] = range(no_toot_id.sum())
    text_df.loc[no_toot_id, "data"] = text_df.loc[no_toot_id, :].apply(
        lambda x: x.data | {"toot_id": "None" + str(x.no_toot_id_idx)}, axis=1
    )

    text_df["toot_id"] = text_df.data.apply(lambda x: x["toot_id"])
    text_df = text_df.set_index("toot_id")
    text_df["text_data"] = text_df.apply(
        lambda x: {"user": x.source_user, "action": past[x.label], "content": x.data["post_text"]},
        axis=1,
    )
    text_df.text_data = text_df.apply(
        lambda x: x.text_data | {"parent_toot_id": x.data["reply_to"]["toot_id"]}
        if x.label == "reply"
        else x.text_data,
        axis=1,
    )

    return text_df.text_data.to_dict()


def load_data(input_var):
    if len(input_var) < 500:
        df = pd.read_json(input_var, lines=True)
    else:
        df = pd.read_json(StringIO(input_var), lines=True)

    names = list(df.source_user.unique())
    name_dict = dict(zip([n.split()[0] for n in names], names, strict=False))
    print(name_dict)

    # replace all first name occurence with fullnames in target field
    def replace_full(data):
        if "target_user" in data:
            if len(data["target_user"].split()) == 1:
                data.update(target_user=name_dict[data["target_user"]])
        return data

    df.loc[:, "data"] = df.loc[:, "data"].apply(lambda x: replace_full(x))

    # make sure all tootids are strings
    def get_toot_id(data):
        if "toot_id" in data:
            data["toot_id"] = str(data["toot_id"])
        if "reply_to" in data:
            data["reply_to"]["toot_id"] = str(data["reply_to"]["toot_id"])
        return data

    df["data"] = df.data.apply(get_toot_id)

    eval_df, int_df, edge_df = post_process_output(df)

    # votes
    votes = (
        eval_df.loc[eval_df.label == "vote_pref", ["source_user", "response", "episode"]]
        .groupby("episode")
        .apply(lambda x: dict(zip(x.source_user, x.response, strict=False)))
        .to_dict()
    )

    # final follow network
    follow_graph = nx.from_pandas_edgelist(
        edge_df, "source_user", "target_user", create_using=nx.DiGraph()
    )  # invalid in presence of unfollows (in which case use episodewise_graphbuild)

    # active users with episode keys
    posted_users_by_episode = int_df.groupby("episode")["source_user"].apply(set).to_dict()

    # interaction data
    int_dict = get_int_dict(int_df.copy())

    # toot_data
    toot_dict = get_toot_dict(int_df.copy())

    return follow_graph, int_dict, posted_users_by_episode, toot_dict, votes


# Main entry point
if __name__ == "__main__":
    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Run the Dash app with specific data files.")
    parser.add_argument(
        "--output_file",
        type=str,
        nargs="?",
        default=None,
        help="The path to the output log file.",
    )

    args = parser.parse_args()

    # Initialize variables
    if args.output_file:
        # Load the data using the files passed as arguments
        (follow_graph, interactions_by_episode, posted_users_by_episode, toots, votes) = load_data(
            args.output_file
        )

        # Compute positions
        all_positions = compute_positions(follow_graph)

        layout = {"name": "preset", "positions": all_positions}

        # Serialize the initial data
        serialized_initial_data = serialize_data(
            follow_graph, interactions_by_episode, posted_users_by_episode, toots, votes
        )
    else:
        # No initial data provided
        serialized_initial_data = None

    app = dash.Dash(__name__)

    # Create the layout with conditional sections
    app.layout = html.Div(
        [
            # Store component to hold serialized data
            dcc.Store(id="data-store", data=serialized_initial_data),
            # Upload Screen
            html.Div(
                id="upload-screen",
                children=[
                    # Upload Output Log
                    html.Div(
                        [
                            html.Label(
                                "Upload Output Log:",
                                style={
                                    "font-size": "18px",
                                    "font-weight": "bold",
                                    "margin-bottom": "10px",
                                    "color": "#555555",
                                    "text-align": "center",
                                },
                            ),
                            dcc.Upload(
                                id="upload-app-logger",
                                children=html.Div(
                                    [
                                        "Drag and Drop or ",
                                        html.A(
                                            "Select Files",
                                            style={
                                                "color": "#1a73e8",
                                                "text-decoration": "underline",
                                            },
                                        ),
                                    ]
                                ),
                                style={
                                    "width": "100%",
                                    "max-width": "400px",
                                    "height": "80px",
                                    "lineHeight": "80px",
                                    "borderWidth": "2px",
                                    "borderStyle": "dashed",
                                    "borderRadius": "10px",
                                    "textAlign": "center",
                                    "background-color": "#f9f9f9",
                                    "cursor": "pointer",
                                    "margin": "0 auto",  # Center the upload box
                                    "transition": "border 0.3s ease-in-out",
                                },
                                multiple=False,
                            ),
                        ],
                        style={"width": "100%", "max-width": "500px", "margin-bottom": "30px"},
                    ),
                    # Submit Button
                    html.Button(
                        "Submit",
                        id="submit-button",
                        n_clicks=0,
                        style={
                            "width": "200px",
                            "height": "50px",
                            "font-size": "18px",
                            "background-color": "#4CAF50",  # Green background
                            "color": "white",
                            "border": "none",
                            "border-radius": "8px",
                            "cursor": "pointer",
                            "box-shadow": "0 4px 6px rgba(0, 0, 0, 0.1)",
                            "transition": "background-color 0.3s ease, transform 0.2s ease",
                            "margin-bottom": "20px",
                            "align-self": "center",  # Center the button
                        },
                    ),
                    # Error Message
                    html.Div(
                        id="upload-error-message",
                        style={
                            "color": "red",
                            "textAlign": "center",
                            "margin-top": "20px",
                            "font-size": "16px",
                        },
                    ),
                ],
                style={
                    "display": "flex",
                    "flexDirection": "column",
                    "alignItems": "center",
                    "justifyContent": "center",
                    "height": "100vh",
                    "background-color": "#f0f2f5",  # Light gray background for better contrast
                    "padding": "20px",
                },
            ),
            # Dashboard
            html.Div(
                id="dashboard",  # Added 'dashboard' id here
                children=[
                    # Line graphs container
                    html.Div(
                        [
                            # Vote distribution line graph
                            dcc.Graph(
                                id="vote-distribution-line",
                                config={"displayModeBar": False},
                                style={
                                    "height": "170px",
                                    "width": "48%",
                                    "display": "inline-block",
                                },
                            ),
                            # Interactions count line graph
                            dcc.Graph(
                                id="interactions-line-graph",
                                config={"displayModeBar": False},
                                style={
                                    "height": "170px",
                                    "width": "48%",
                                    "display": "inline-block",
                                },
                            ),
                        ],
                        style={
                            "display": "flex",
                            "justify-content": "space-between",
                            "margin-top": "20px",
                        },
                    ),
                    # Main content: Cytoscape graph and interactions window
                    html.Div(
                        [
                            html.Div(
                                [
                                    dcc.Dropdown(
                                        id="name-selector",
                                        options=[],  # To be populated by callback
                                        value=None,
                                        placeholder="Select Name",
                                        clearable=True,
                                        style={
                                            "padding": "10px",
                                            "font-size": "16px",
                                            "font-weight": "bold",
                                            "width": "200px",
                                            "z-index": "1000",  # Ensure it stays on top of the Cytoscape graph
                                        },
                                    ),
                                    dcc.Dropdown(
                                        id="mode-dropdown",
                                        options=[
                                            {"label": "Universal View", "value": "normal"},
                                            {"label": "Active View", "value": "focused"},
                                        ],
                                        value="normal",
                                        clearable=False,
                                        style={
                                            "padding": "10px",
                                            "font-size": "16px",
                                            "font-weight": "bold",
                                            "width": "200px",
                                            "z-index": "1000",  # Ensure it stays on top of the Cytoscape graph
                                        },
                                    ),
                                ],
                                style={
                                    "position": "absolute",
                                    "top": "10px",  # Aligns at the top of the graph
                                    "left": "10px",  # Aligns on the left
                                    "display": "flex",
                                    "gap": "10px",  # Space between the two dropdowns
                                    "z-index": "1000",  # Ensure it's above the Cytoscape graph
                                },
                            ),
                            # Episode number display (top-right)
                            html.Div(
                                id="current-episode",
                                style={
                                    "position": "absolute",
                                    "top": "10px",
                                    "right": "10px",
                                    "padding": "10px",
                                    "font-size": "20px",
                                    "font-weight": "bold",
                                    "background-color": "#ffcc99",  # Optional: add a background color
                                    "z-index": "1000",  # Ensure it stays on top of the Cytoscape graph
                                },
                                children="",
                            ),
                            # Flex container for Cytoscape and Interactions Window
                            html.Div(
                                [
                                    cyto.Cytoscape(
                                        id="cytoscape-graph",
                                        elements=[],  # To be populated by callback
                                        layout={
                                            "name": "preset",
                                            "positions": {},
                                        },  # To be updated by callback
                                        style={
                                            "width": "100%",  # Initial width set to 100%
                                            "height": "600px",
                                            "background-color": "#e1e1e1",
                                            "transition": "width 0.5s",  # Smooth width transition
                                        },
                                        stylesheet=[
                                            {
                                                "selector": ".default_node",
                                                "style": {
                                                    "background-color": "#fffca0",
                                                    "label": "data(label)",
                                                    "color": "#000000",
                                                    "font-size": "20px",
                                                    "text-halign": "center",
                                                    "text-valign": "center",
                                                    "width": "70px",
                                                    "height": "70px",
                                                    "border-width": 6,
                                                    "border-color": "#000000",
                                                },
                                            },
                                            {
                                                "selector": ".follow_edge",
                                                "style": {
                                                    "curve-style": "bezier",
                                                    "target-arrow-shape": "triangle",
                                                    "opacity": 0.8,
                                                    "width": 2,
                                                    "line-color": "#FFFFFF",
                                                },
                                            },
                                            {
                                                "selector": ".interaction_edge",
                                                "style": {
                                                    "curve-style": "bezier",
                                                    "target-arrow-shape": "triangle",
                                                    "opacity": 0.8,
                                                    "width": 4,
                                                    "line-color": "#000000",
                                                    "visibility": "hidden",
                                                },
                                            },
                                            {
                                                "selector": ".interaction_edge:hover",
                                                "style": {
                                                    "label": "data(label)",
                                                    "font-size": "14px",
                                                    "color": "#000000",
                                                },
                                            },
                                            # Edge labels
                                            {
                                                "selector": "edge",
                                                "style": {
                                                    "label": "data(label)",
                                                    "text-rotation": "autorotate",
                                                    "text-margin-y": "-10px",
                                                    "font-size": "10px",
                                                    "color": "#000000",
                                                    "text-background-color": "#FFFFFF",
                                                    "text-background-opacity": 0.8,
                                                    "text-background-padding": "3px",
                                                },
                                            },
                                            # Specific styles for "Bill" and "Bradley" nodes
                                            {
                                                "selector": '[id="Bill Fredrickson"]',
                                                "style": {
                                                    "background-color": "blue",
                                                    "border-color": "#000000",
                                                },
                                            },
                                            {
                                                "selector": '[id="Bradley Carter"]',
                                                "style": {
                                                    "background-color": "orange",
                                                    "border-color": "#000000",
                                                },
                                            },
                                            # Highlighted Nodes (Added)
                                            {
                                                "selector": ".highlighted",
                                                "style": {
                                                    "background-color": "#98FF98",  # Mint color
                                                    "border-color": "#FF69B4",  # Hot pink border for visibility
                                                    "border-width": 4,
                                                },
                                            },
                                        ],
                                    ),
                                    # Interactions Window
                                    html.Div(
                                        [
                                            html.H3("Interactions"),
                                            html.Div(
                                                id="interactions-window",
                                                style={"overflowY": "auto", "height": "580px"},
                                            ),
                                        ],
                                        style={
                                            "width": "0%",  # Initial width set to 0%
                                            "height": "600px",
                                            "padding": "10px",
                                            "border-left": "1px solid #ccc",
                                            "background-color": "#f9f9f9",
                                            "transition": "width 0.5s",  # Smooth width transition
                                            "overflow": "hidden",
                                        },
                                        id="interactions-container",
                                    ),
                                ],
                                style={
                                    "display": "flex",
                                    "flexDirection": "row",
                                    "height": "600px",
                                    "transition": "all 0.5s ease",  # Smooth transition for all properties
                                },
                            ),
                        ],
                        style={
                            "position": "relative",
                            "height": "600px",
                            "margin-top": "10px",
                            "margin-bottom": "20px",
                        },
                    ),
                    # Episode slider
                    dcc.Slider(
                        id="episode-slider",
                        min=0,  # To be updated by callback
                        max=0,  # To be updated by callback
                        value=0,  # To be updated by callback
                        marks={},  # To be updated by callback
                        step=None,
                        tooltip={"placement": "bottom", "always_visible": True},
                    ),
                    dcc.Graph(
                        id="vote-percentages-bar",
                        config={"displayModeBar": False},
                        style={"height": "50px", "margin-top": "20px"},
                    ),
                    # Upload components and Submit button added at the bottom
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Label("Upload Output Log:"),
                                    dcc.Upload(
                                        id="upload-app-logger-dashboard",
                                        children=html.Div([html.A("Select Files")]),
                                        style={
                                            "width": "60%",
                                            "height": "50px",
                                            "lineHeight": "80px",
                                            "borderWidth": "2px",
                                            "borderStyle": "dashed",
                                            "borderRadius": "10px",
                                            "textAlign": "center",
                                            "background-color": "#f0f0f0",
                                            "cursor": "pointer",
                                            "margin-bottom": "20px",
                                            "padding": "30px",
                                        },
                                        multiple=False,
                                    ),
                                ],
                                className="upload-component",
                            ),
                            html.Div(
                                [
                                    html.Button(
                                        "Upload Files",
                                        id="upload-button-dashboard",
                                        n_clicks=0,
                                        style={
                                            "width": "100px",
                                            "height": "50px",
                                            "font-size": "12px",
                                            "padding": "30px",
                                        },
                                    ),
                                ],
                                className="upload-button-container",
                            ),
                        ],
                        style={
                            "display": "flex",
                            "justify-content": "space-around",
                            # 'flex-wrap': 'wrap',
                            "gap": "20px",
                            "margin-top": "20px",
                            "margin-bottom": "20px",
                        },
                        id="dashboard-upload-section",
                    ),
                ],
                style={"display": "none"},  # Initially hidden; shown when data is available
            ),
            # Hidden div for error messages (specific to dashboard uploads)
            html.Div(id="error-message", style={"color": "red", "textAlign": "center"}),
        ]
    )

    @app.callback(
        [
            Output("upload-screen", "style"),
            Output("dashboard", "style"),
            Output("dashboard-upload-section", "style"),
            Output("name-selector", "options"),
        ],
        [Input("data-store", "data")],
    )
    def toggle_layout(data_store):
        if data_store and "nodes" in data_store and len(data_store["nodes"]) > 0:
            # Data is available; show dashboard and hide upload screen
            return (
                {"display": "none"},
                {"display": "block"},
                {"display": "flex"},
                [{"label": name, "value": name} for name in sorted(data_store["nodes"])],
            )
        # No data; show upload screen and hide dashboard
        return {"display": "flex"}, {"display": "none"}, {"display": "none"}, []

    # Combined Callback for Initial and Dashboard Uploads
    @app.callback(
        [
            Output("data-store", "data"),
            Output("upload-error-message", "children"),
            Output("error-message", "children"),
        ],
        [
            Input("submit-button", "n_clicks"),
            Input("upload-button-dashboard", "n_clicks"),
        ],
        [
            State("upload-app-logger", "contents"),
            # State("upload-vote-logger", "contents"),
            State("upload-app-logger", "filename"),
            # State("upload-vote-logger", "filename"),
            State("upload-app-logger-dashboard", "contents"),
            # State("upload-vote-logger-dashboard", "contents"),
            State("upload-app-logger-dashboard", "filename"),
            # State("upload-vote-logger-dashboard", "filename"),
            State("data-store", "data"),
        ],
    )
    def update_data(
        n_clicks_initial,
        n_clicks_dashboard,
        app_logger_contents_initial,
        app_logger_filename_initial,
        app_logger_contents_dashboard,
        app_logger_filename_dashboard,
        current_data,
    ):
        ctx = dash.callback_context

        if not ctx.triggered:
            raise dash.exceptions.PreventUpdate

        triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]

        try:
            if triggered_id == "submit-button":
                # Handle initial upload
                if app_logger_contents_initial is not None:
                    # Process app_logger
                    content_type, content_string = app_logger_contents_initial.split(",")
                    decoded = base64.b64decode(content_string)
                    app_logger_string = decoded.decode("utf-8")
                    (
                        follow_graph_new,
                        interactions_by_episode_new,
                        posted_users_by_episode_new,
                        toots_new,
                        votes_new,
                    ) = load_data(app_logger_string)

                    # Serialize the new data
                    serialized_new_data = serialize_data(
                        follow_graph_new,
                        interactions_by_episode_new,
                        posted_users_by_episode_new,
                        toots_new,
                        votes_new,
                    )

                    return serialized_new_data, "", ""
                raise ValueError("Output Log file required.")

            if triggered_id == "upload-button-dashboard":
                # Handle dashboard upload
                if app_logger_contents_dashboard is not None:
                    # Process app_logger
                    content_type, content_string = app_logger_contents_dashboard.split(",")
                    decoded = base64.b64decode(content_string)
                    app_logger_string = decoded.decode("utf-8")
                    (
                        follow_graph_new,
                        interactions_by_episode_new,
                        posted_users_by_episode_new,
                        toots_new,
                        votes_new,
                    ) = load_data(app_logger_string)

                    # Serialize the new data
                    serialized_new_data = serialize_data(
                        follow_graph_new,
                        interactions_by_episode_new,
                        posted_users_by_episode_new,
                        toots_new,
                        votes_new,
                    )

                    return serialized_new_data, "", ""
                raise ValueError("Output Log files required for dashboard upload.")

            raise dash.exceptions.PreventUpdate

        except Exception as e:
            if triggered_id == "submit-button":
                return dash.no_update, f"Error uploading initial data: {e!s}", ""
            if triggered_id == "upload-button-dashboard":
                return dash.no_update, "", f"Error uploading dashboard data: {e!s}"
            return dash.no_update, "", ""

    # Callback to update the dashboard based on data-store
    @app.callback(
        [
            Output("cytoscape-graph", "elements"),
            Output("cytoscape-graph", "layout"),
            Output("cytoscape-graph", "stylesheet"),
            Output("vote-percentages-bar", "figure"),
            Output("vote-distribution-line", "figure"),
            Output("interactions-line-graph", "figure"),
            Output("current-episode", "children"),
            Output("interactions-window", "children"),  # Added Output
            Output("interactions-container", "style"),  # Added Output to control width
            Output("cytoscape-graph", "style"),  # Added Output to control width
            Output("episode-slider", "min"),
            Output("episode-slider", "max"),
            Output("episode-slider", "value"),
            Output("episode-slider", "marks"),
            Output("name-selector", "value"),
        ],
        [
            Input("episode-slider", "value"),
            Input("mode-dropdown", "value"),
            Input("name-selector", "value"),  # Added Input
            Input("data-store", "data"),  # Added Input to trigger update on data change
        ],
    )
    def update_graph(selected_episode, selected_mode, selected_name, data_store):
        if not data_store:
            # If no data is present, return defaults
            return (
                [],  # elements
                {"name": "preset", "positions": {}},  # layout
                [],  # stylesheet
                {},  # vote-percentages-bar
                {},  # vote-distribution-line
                {},  # interactions-line-graph
                "Episode: N/A",  # current-episode
                [],  # interactions-window
                {
                    "width": "0%",  # Collapsed width
                    "height": "600px",
                    "padding": "10px",
                    "border-left": "1px solid #ccc",
                    "background-color": "#f9f9f9",
                    "transition": "width 0.5s",  # Smooth width transition
                    "overflow": "hidden",
                },  # interactions-container
                {
                    "width": "100%",  # Full width
                    "height": "600px",
                    "background-color": "#e1e1e1",
                    "transition": "width 0.5s",  # Smooth width transition
                },  # cytoscape-style
                0,  # slider min
                0,  # slider max
                0,  # slider value
                {},  # slider marks
                None,  # name-selector value
            )

        # Deserialize the data_store.
        (follow_graph, interactions_by_episode, posted_users_by_episode, toots, votes) = (
            deserialize_data(data_store)
        )

        # Compute positions based on the current follow_graph
        all_positions = compute_positions(follow_graph)
        layout = {"name": "preset", "positions": all_positions}

        # Build Cytoscape elements
        elements = [
            {
                "data": {"id": node, "label": node},
                "classes": "default_node",
            }
            for node in follow_graph.nodes
        ] + [
            {
                "data": {
                    "source": src,
                    "target": tgt,
                },
                "classes": "follow_edge",
            }
            for src, tgt in follow_graph.edges
        ]

        # Add all interaction edges classified by the episode they belong to
        for episode, interactions in interactions_by_episode.items():
            for interaction in interactions:
                source = interaction["source"]
                target = interaction["target"]

                # Check if both source and target exist in the graph before creating the edge
                if source in follow_graph.nodes and target in follow_graph.nodes:
                    elements.append(
                        {
                            "data": {
                                "source": source,
                                "target": target,
                                "label": f"{interaction['action']}",
                            },
                            "classes": f"interaction_edge episode_{episode}",  # Classify edge by episode
                        }
                    )

        # Initialize the stylesheet
        stylesheet = [
            {
                "selector": ".default_node",
                "style": {
                    "background-color": "#fffca0",
                    "label": "data(label)",
                    "color": "#000000",
                    "font-size": "20px",
                    "text-halign": "center",
                    "text-valign": "center",
                    "width": "70px",
                    "height": "70px",
                    "border-width": 6,
                    "border-color": "#000000",
                },
            },
            {
                "selector": ".follow_edge",
                "style": {
                    "curve-style": "bezier",
                    "target-arrow-shape": "triangle",
                    "opacity": 0.8,
                    "width": 2,
                    "line-color": "#FFFFFF",
                },
            },
            {
                "selector": "edge",
                "style": {
                    "label": "data(label)",
                    "text-rotation": "autorotate",
                    "text-margin-y": "-10px",
                    "font-size": "10px",
                    "color": "#000000",
                    "text-background-color": "#FFFFFF",
                    "text-background-opacity": 0.8,
                    "text-background-padding": "3px",
                },
            },
            {
                "selector": ".interaction_edge:hover",
                "style": {
                    "label": "data(label)",
                    "font-size": "14px",
                    "color": "#000000",
                },
            },
            # Specific styles for "Bill" and "Bradley" nodes
            {
                "selector": '[id="Bill Fredrickson"]',
                "style": {
                    "background-color": "blue",
                    "border-color": "#000000",
                },
            },
            {
                "selector": '[id="Bradley Carter"]',
                "style": {
                    "background-color": "orange",
                    "border-color": "#000000",
                },
            },
            # Highlighted Nodes
            {
                "selector": ".highlighted",
                "style": {
                    "background-color": "#98FF98",  # Mint color
                    "border-color": "#FF69B4",  # Hot pink border for visibility
                    "border-width": 4,
                },
            },
        ]

        # Determine the sizing of the interactions window and Cytoscape graph
        interactions_content = []

        if selected_name:
            # Get interactions where source is selected_name in selected_episode
            interactions = [
                interaction
                for interaction in interactions_by_episode.get(selected_episode, [])
                if interaction["source"] == selected_name
            ]
            if interactions:
                for interaction in interactions:
                    action = interaction["action"]
                    if action in ["liked", "boosted"]:
                        toot_id = interaction["toot_id"]
                        content = toots.get(toot_id, {}).get("content", "No content available.")
                        user = toots.get(toot_id, {}).get("user", "No user available.")
                        interactions_content.append(
                            html.Div(
                                [
                                    html.H4(
                                        f"{action.capitalize()} a toot (ID: {toot_id}) by {user}"
                                    ),
                                    html.P(content),
                                ],
                                style={
                                    "border": "1px solid #ccc",
                                    "padding": "10px",
                                    "margin-bottom": "10px",
                                },
                            )
                        )
                    elif action == "replied":
                        parent_toot_id = interaction.get("parent_toot_id")
                        reply_toot_id = interaction.get("toot_id")
                        parent_content = toots.get(parent_toot_id, {}).get(
                            "content", "No content available."
                        )
                        reply_content = toots.get(reply_toot_id, {}).get(
                            "content", "No content available."
                        )
                        user = toots.get(ot_id, {}).get("user", "No user available.")
                        interactions_content.append(
                            html.Div(
                                [
                                    html.H4(f"Replied to toot (ID: {parent_toot_id}) by {user}"),
                                    html.P(parent_content),
                                    html.H5(f"Reply (ID: {ot_id}):"),
                                    html.P(reply_content),
                                ],
                                style={
                                    "border": "1px solid #ccc",
                                    "padding": "10px",
                                    "margin-bottom": "10px",
                                },
                            )
                        )
                    elif action == "posted":
                        toot_id = interaction["toot_id"]
                        content = toots.get(toot_id, {}).get("content", "No content available.")
                        interactions_content.append(
                            html.Div(
                                [
                                    html.H4(f"Posted a toot (ID: {toot_id})"),
                                    html.P(content),
                                ],
                                style={
                                    "border": "1px solid #ccc",
                                    "padding": "10px",
                                    "margin-bottom": "10px",
                                },
                            )
                        )
            else:
                interactions_content.append(
                    html.P("No interactions found for this agent in the selected episode.")
                )
        else:
            interactions_content.append(html.P("Select an agent to view their interactions."))

        if selected_name:
            interactions_style = {
                "width": "30%",  # Expanded width
                "height": "600px",
                "padding": "10px",
                "border-left": "1px solid #ccc",
                "background-color": "#f9f9f9",
                "transition": "width 0.5s",  # Smooth width transition
                "overflow": "auto",
            }
            cytoscape_style = {
                "width": "70%",  # Reduced width
                "height": "600px",
                "background-color": "#e1e1e1",
                "transition": "width 0.5s",  # Smooth width transition
            }
        else:
            interactions_style = {
                "width": "0%",  # Collapsed width
                "height": "600px",
                "padding": "10px",
                "border-left": "1px solid #ccc",
                "background-color": "#f9f9f9",
                "transition": "width 0.5s",  # Smooth width transition
                "overflow": "hidden",
            }
            cytoscape_style = {
                "width": "100%",  # Full width
                "height": "600px",
                "background-color": "#e1e1e1",
                "transition": "width 0.5s",  # Smooth width transition
            }

        # Highlight selected node and the nodes they follow
        if selected_name:
            # Find the nodes that the selected node follows (outgoing edges)
            follows = list(follow_graph.successors(selected_name))
            # Define the selector for the selected node and its followees
            if follows:
                highlight_selector = f'[id="{selected_name}"], ' + ", ".join(
                    [f'[id="{follow}"]' for follow in follows]
                )
            else:
                highlight_selector = f'[id="{selected_name}"]'

            # Apply the 'highlighted' class to the selected node and its followees
            stylesheet.append(
                {
                    "selector": highlight_selector,
                    "style": {
                        "background-color": "#98FF98",  # Mint color
                        "border-color": "#FF69B4",  # Hot pink border for visibility
                        "border-width": 4,
                    },
                }
            )

        # Show interaction edges for the selected episode
        for episode in interactions_by_episode.keys():
            visibility = "visible" if episode == selected_episode else "hidden"
            stylesheet.append(
                {
                    "selector": f".episode_{episode}",
                    "style": {"visibility": visibility},
                }
            )

        # Update node border colors based on votes
        episode_votes = votes.get(selected_episode, {})
        total_votes = len(episode_votes)
        vote_counts = {"Bill": 0, "Bradley": 0, "None": 0}
        for node in follow_graph.nodes:
            if node in episode_votes:
                vote = episode_votes[node]
                if vote == "Bill":
                    color = "#1f77b4"
                    vote_counts["Bill"] += 1
                elif vote == "Bradley":
                    color = "#ff7f0e"
                    vote_counts["Bradley"] += 1
                else:
                    color = "#000000"
                    vote_counts["None"] += 1

                stylesheet.append(
                    {
                        "selector": f'[id="{node}"]',
                        "style": {"border-color": color},
                    }
                )

        # Calculate vote percentages
        bill_percentage = (vote_counts["Bill"] / total_votes) * 100 if total_votes > 0 else 0
        bradley_percentage = (vote_counts["Bradley"] / total_votes) * 100 if total_votes > 0 else 0

        # Create bar graph for vote percentages
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=[bill_percentage],
                y=["Support"],
                orientation="h",
                marker=dict(color="#1f77b4"),
                text=f"Bill: {bill_percentage:.1f}%",
                textposition="inside",
            )
        )
        fig.add_trace(
            go.Bar(
                x=[bradley_percentage],
                y=["Support"],
                orientation="h",
                marker=dict(color="#ff7f0e"),
                text=f"Bradley: {bradley_percentage:.1f}%",
                textposition="inside",
                base=bill_percentage,
            )
        )
        fig.update_layout(
            xaxis=dict(range=[0, 100], showticklabels=False),
            yaxis=dict(showticklabels=False),
            barmode="stack",
            title=f"Vote Percentages for Episode {selected_episode}",
            showlegend=False,
            height=50,
            margin=dict(l=0, r=0, t=30, b=0),
        )

        # Create the line graph showing vote distribution over time
        episodes = sorted(votes.keys())
        Bill_votes_over_time = []
        Bradley_votes_over_time = []

        for ep in episodes:
            ep_votes = votes[ep]
            total_ep_votes = len(ep_votes)
            Bill_votes = sum(1 for vote in ep_votes.values() if vote == "Bill")
            Bradley_votes = sum(1 for vote in ep_votes.values() if vote == "Bradley")

            Bill_votes_over_time.append(
                (Bill_votes / total_ep_votes) * 100 if total_ep_votes > 0 else 0
            )
            Bradley_votes_over_time.append(
                (Bradley_votes / total_ep_votes) * 100 if total_ep_votes > 0 else 0
            )

        vote_line_fig = go.Figure()
        vote_line_fig.add_trace(
            go.Scatter(
                x=episodes,
                y=Bill_votes_over_time,
                mode="lines+markers",
                name="Bill",
                line=dict(color="#1f77b4"),
            )
        )
        vote_line_fig.add_trace(
            go.Scatter(
                x=episodes,
                y=Bradley_votes_over_time,
                mode="lines+markers",
                name="Bradley",
                line=dict(color="#ff7f0e"),
            )
        )
        vote_line_fig.update_layout(
            title={"text": "Vote Distribution Over Time", "font": {"size": 14}},
            xaxis={"title": {"text": "Episode", "font": {"size": 10}}, "tickfont": {"size": 8}},
            yaxis={
                "title": {"text": "Vote Percentage", "font": {"size": 10}},
                "tickfont": {"size": 8},
            },
            height=200,
            margin=dict(l=40, r=40, t=20, b=10),
        )

        # Create the line graph showing interactions over time
        interaction_types = ["liked", "boosted", "replied", "posted"]
        interactions_over_time = {interaction: [] for interaction in interaction_types}

        total_users = len(follow_graph.nodes)

        active_user_fractions = []

        for ep in episodes:
            # Initialize counts
            active_nodes_in_ep = set()
            active_nodes_in_ep = {
                interaction["source"] for interaction in interactions_by_episode.get(ep, [])
            }.union(
                {interaction["target"] for interaction in interactions_by_episode.get(ep, [])}
            ).union(set(posted_users_by_episode.get(ep, [])))

            num_active_users = len(active_nodes_in_ep)

            counts = {interaction: 0 for interaction in interaction_types}

            # Count interactions
            for interaction in interactions_by_episode.get(ep, []):
                action = interaction["action"]
                if action in counts:
                    counts[action] += 1

            # Count posts
            counts["posted"] = len(posted_users_by_episode.get(ep, []))

            # Append counts to the respective lists
            for interaction in interaction_types:
                interactions_over_time[interaction].append(
                    counts[interaction] / num_active_users if num_active_users > 0 else 0
                )

            # Calculate active user fraction
            active_user_fraction = num_active_users / total_users if total_users > 0 else 0
            active_user_fractions.append(active_user_fraction)

        interactions_line_fig = make_subplots(specs=[[{"secondary_y": True}]])

        # Add normalized interaction traces to the primary y-axis
        interactions_line_fig.add_trace(
            go.Scatter(
                x=episodes,
                y=interactions_over_time["liked"],
                mode="lines+markers",
                name="Likes",
                line=dict(color="#2ca02c"),  # Green
                marker=dict(symbol="circle", size=6),
            ),
            secondary_y=False,
        )
        interactions_line_fig.add_trace(
            go.Scatter(
                x=episodes,
                y=interactions_over_time["boosted"],
                mode="lines+markers",
                name="Boosts",
                line=dict(color="#ff7f0e"),  # Orange
                marker=dict(symbol="square", size=6),
            ),
            secondary_y=False,
        )
        interactions_line_fig.add_trace(
            go.Scatter(
                x=episodes,
                y=interactions_over_time["replied"],
                mode="lines+markers",
                name="Replies",
                line=dict(color="#9467bd"),  # Purple
                marker=dict(symbol="diamond", size=6),
            ),
            secondary_y=False,
        )
        interactions_line_fig.add_trace(
            go.Scatter(
                x=episodes,
                y=interactions_over_time["posted"],
                mode="lines+markers",
                name="Posts",
                line=dict(color="#1f77b4"),  # Blue
                marker=dict(symbol="triangle-up", size=6),
            ),
            secondary_y=False,
        )

        # Add active users fraction trace to the secondary y-axis
        interactions_line_fig.add_trace(
            go.Scatter(
                x=episodes,
                y=active_user_fractions,
                mode="lines",
                name="Active User Fraction",
                line=dict(color="gray"),
            ),
            secondary_y=True,
        )

        # Define the y-axis range
        y_axis_range = [0, 2]

        # Update both y-axes
        interactions_line_fig.update_yaxes(
            title_text="Action Rate of Active Users",
            range=y_axis_range,
            secondary_y=False,
            showgrid=True,
            gridcolor="lightgray",
        )

        interactions_line_fig.update_yaxes(
            title_text="Active User Fraction",
            range=[0, 1],
            secondary_y=True,
            showgrid=False,  # Typically, grid lines are only on the primary y-axis
            gridcolor="lightgray",
        )

        interactions_line_fig.update_layout(
            title={
                "text": "Interactions Over Time",
                "font": {"size": 14},  # Reduced title font size to 14
            },
            xaxis={
                "title": {
                    "text": "Episode",
                    "font": {"size": 10},  # Reduced x-axis label font size to 12
                },
                "tickfont": {"size": 8},  # Reduced x-axis tick font size
                "range": [
                    min(episodes),
                    max(episodes) + 1,
                ],  # Setting the range from min to max episode
                "dtick": 1,  # Show a tick marker every episode
            },
            yaxis={
                "title": {
                    "text": "Interactions/ Num. Agents",
                    "font": {"size": 10},  # Reduced y-axis label font size to 12
                },
                "tickfont": {"size": 8},  # Reduced y-axis tick font size
            },
            height=200,
            margin=dict(l=40, r=40, t=20, b=10),
            showlegend=True,
        )
        # Adjust the x-axis range to include all episodes
        interactions_line_fig.update_xaxes(range=[min(episodes), max(episodes) + 1])

        # Update the name-selector dropdown options
        unique_names = sorted(follow_graph.nodes)
        name_options = [{"label": name, "value": name} for name in unique_names]

        # Set episode slider properties
        episodes = sorted(interactions_by_episode.keys())
        slider_min = min(episodes)
        slider_max = max(episodes)
        slider_value = selected_episode if selected_episode in episodes else slider_min
        slider_marks = {str(ep): f"{ep}" for ep in sorted(episodes)}

        # Return all outputs, including the interactions window content and styles
        return (
            elements,  # Updated elements
            layout,
            stylesheet,
            fig,
            vote_line_fig,
            interactions_line_fig,
            f"Episode: {selected_episode}",  # Updated episode display
            interactions_content,
            interactions_style,
            cytoscape_style,
            slider_min,
            slider_max,
            slider_value,
            slider_marks,
            selected_name,
        )

    # Run the Dash app
    app.run_server(debug=True)
