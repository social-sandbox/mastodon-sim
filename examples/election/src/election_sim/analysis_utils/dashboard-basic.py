import argparse  # Import argparse to handle command-line arguments

import dash
import dash_cytoscape as cyto
import matplotlib.colors as mcolors
import networkx as nx
import plotly.graph_objs as go
from dash import Input, Output, dcc, html
from matplotlib import cm

cyto.load_extra_layouts()


# Load and parse the data
def load_data(filepath):
    interaction_graph = nx.MultiDiGraph()
    user_activities = {}
    edge_counts = {}
    with open(filepath) as file:
        lines = file.readlines()

        for line in lines:
            line = line.strip()
            user = line.split()[0]
            if user not in user_activities:
                user_activities[user] = {
                    "posts": 0,
                    "likes": 0,
                    "replies": 0,
                    "retrieved": 0,
                    "boosts": 0,
                }

            if "posted" in line:
                user_activities[user]["posts"] += 1
            elif "retrieved" in line:
                user_activities[user]["retrieved"] += 1
            elif "boosted" in line:
                action = "liked"
                target_user = line.split()[-1]
                if target_user not in user_activities:
                    user_activities[target_user] = {
                        "posts": 0,
                        "likes": 0,
                        "replies": 0,
                        "retrieved": 0,
                        "boosts": 0,
                    }
                user_activities[target_user]["boosts"] += 1
                edge_key = (user, target_user, action)
                edge_counts[edge_key] = edge_counts.get(edge_key, 0) + 1
            elif "liked" in line:
                action = "liked"
                target_user = line.split()[-1]
                if target_user not in user_activities:
                    user_activities[target_user] = {
                        "posts": 0,
                        "likes": 0,
                        "replies": 0,
                        "retrieved": 0,
                        "boosts": 0,
                    }
                user_activities[target_user]["likes"] += 1
                edge_key = (user, target_user, action)
                edge_counts[edge_key] = edge_counts.get(edge_key, 0) + 1

    for (src, tgt, action), count in edge_counts.items():
        interaction_graph.add_edge(src, tgt, action=action, count=count, weight=count)

    return interaction_graph, user_activities, edge_counts


def load_votes(filepath):
    votes = {}
    with open(filepath) as file:
        lines = file.readlines()
        current_episode = None
        for line in lines:
            line = line.strip()
            if line.startswith("Episode:"):
                current_episode = int(line.split(":")[1].strip())
                votes[current_episode] = {}
            elif "votes for" in line:
                user, candidate = line.split(" votes for ")
                votes[current_episode][user.split()[0]] = candidate
    return votes


# Main entry point
if __name__ == "__main__":
    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Run the Dash app with specific data files.")
    parser.add_argument("interaction_file", type=str, help="The path to the interaction log file.")
    parser.add_argument("votes_file", type=str, help="The path to the votes log file.")

    args = parser.parse_args()  # Parse the arguments

    # Load the data using the files passed as arguments
    interaction_graph, user_activities, edge_counts = load_data(args.interaction_file)
    votes = load_votes(args.votes_file)

    # Normalize edge color based on interaction count
    max_count = max(edge_counts.values(), default=1)
    norm = mcolors.Normalize(vmin=0, vmax=max_count)
    cmap = cm.get_cmap("Blues")

    # Prepare Cytoscape elements
    elements = [
        {
            "data": {
                "id": node,
                "label": node,
                "posts": user_activities[node]["posts"],
                "likes": user_activities[node]["likes"],
                "replies": user_activities[node]["replies"],
                "boosts": user_activities[node]["boosts"],
            },
            "classes": "default_node",
        }
        for node in interaction_graph.nodes
    ] + [
        {
            "data": {
                "source": src,
                "target": tgt,
                "label": f"{attr['action']} ({attr['count']})",
                "weight": attr["weight"],
            },
            "style": {"line-color": mcolors.to_hex(cmap(norm(attr["count"]))), "opacity": 0.8},
            "classes": "default_edge",
        }
        for src, tgt, attr in interaction_graph.edges(data=True)
    ]

    app = dash.Dash(__name__)


app.layout = html.Div(
    [
        dcc.Slider(
            id="episode-slider",
            min=min(votes.keys()),
            max=max(votes.keys()),
            value=min(votes.keys()),
            marks={str(episode): str(episode) for episode in votes.keys()},
            step=None,
        ),
        dcc.Graph(
            id="vote-percentages-bar", config={"displayModeBar": False}, style={"height": "50px"}
        ),
        dcc.Graph(
            id="vote-distribution-line",  # Add the new line graph
            config={"displayModeBar": False},
            style={"height": "200px"},  # Adjust the height to fit into the layout
        ),
        dcc.Dropdown(
            id="user-select",
            options=[{"label": node, "value": node} for node in interaction_graph.nodes]
            + [{"label": "Clear Selection", "value": "clear"}],
            value=None,
            placeholder="Select a user",
            style={"width": "300px"},
        ),
        html.Div(
            [
                html.Div(
                    id="episode-label",
                    style={
                        "position": "absolute",
                        "top": "0",
                        "right": "0",
                        "padding": "20px",
                        "font-size": "20px",
                        "font-weight": "bold",
                        "z-index": "1000",  # Ensure it stays on top of the Cytoscape graph
                        "background-color": "#ffcc99",  # Optional: add a background color
                    },
                ),
                cyto.Cytoscape(
                    id="cytoscape-graph",
                    elements=elements,
                    layout={
                        "name": "cose-bilkent",  # Change the layout to cose-bilkent
                        "idealEdgeLength": 100,
                        "nodeRepulsion": 800000,
                        "gravity": 0.4,
                        "numIter": 5000,
                        "initialTemp": 100,
                    },
                    style={"width": "100%", "height": "600px", "background-color": "#ffcc99"},
                    stylesheet=[
                        {
                            "selector": ".default_node",
                            "style": {
                                "background-color": "#0074D9",
                                "label": "data(label)",
                                "color": "#FFFFFF",
                                "font-size": "16px",
                                "text-halign": "center",
                                "text-valign": "center",
                                "width": "50px",
                                "height": "50px",
                                "border-width": 2,
                                "border-color": "#0057A7",
                            },
                        },
                        {
                            "selector": ".default_edge",
                            "style": {
                                "curve-style": "bezier",
                                "target-arrow-shape": "triangle",
                                "opacity": 0.8,
                                "width": 4,
                                "line-color": mcolors.to_hex(cmap(norm(1))),
                                "label": "",
                                "font-size": "12px",
                                "color": "#000000",
                                "text-rotation": "autorotate",
                            },
                        },
                        {
                            "selector": ".default_edge:hover",
                            "style": {
                                "label": "data(label)",
                                "font-size": "14px",
                                "color": "#000000",
                            },
                        },
                        {
                            "selector": ".highlighted",
                            "style": {
                                "background-color": "#FF4136",
                                "border-color": "red",
                                "border-width": 4,
                            },
                        },
                        {
                            "selector": ".connected",
                            "style": {"opacity": 1, "line-color": "#FF851B"},
                        },
                        {
                            "selector": ".connected_node",
                            "style": {"background-color": "#2ECC40", "color": "#FFFFFF"},
                        },
                    ],
                ),
            ],
            style={"position": "relative", "height": "600px"},
        ),
    ]
)


@app.callback(
    Output("cytoscape-graph", "stylesheet"),
    Output("vote-percentages-bar", "figure"),
    Output("vote-distribution-line", "figure"),  # Add output for the line graph
    Output("episode-label", "children"),  # Add this output for the episode label
    [Input("episode-slider", "value"), Input("user-select", "value")],
)
def update_graph(selected_episode, selected_user):
    # Base stylesheet
    stylesheet = [
        {
            "selector": ".default_node",
            "style": {
                "background-color": "#0074D9",
                "label": "data(label)",
                "color": "#FFFFFF",
                "font-size": "16px",
                "text-halign": "center",
                "text-valign": "center",
                "width": "50px",
                "height": "50px",
                "border-width": 2,
                "border-color": "#0057A7",
            },
        },
        {
            "selector": ".default_edge",
            "style": {
                "curve-style": "bezier",
                "target-arrow-shape": "triangle",
                "opacity": 0.8,
                "width": 4,
                "line-color": mcolors.to_hex(cmap(norm(1))),
                "label": "",
                "font-size": "12px",
                "color": "#000000",
                "text-rotation": "autorotate",
            },
        },
    ]

    # Update nodes based on voting
    episode_votes = votes[selected_episode]
    total_votes = len(episode_votes)
    vote_counts = {"Bill": 0, "Bradley": 0, "None": 0}  # Adjust according to candidate names
    for node in interaction_graph.nodes:
        if node in episode_votes:
            vote = episode_votes[node]
            if vote == "Bill":
                color = "#1f77b4"  # Blue for Bill
                vote_counts["Bill"] += 1
            elif vote == "Bradley":
                color = "#ff7f0e"  # Orange for Bradley
                vote_counts["Bradley"] += 1
            else:
                color = "#d3d3d3"  # Gray for None
                vote_counts["None"] += 1
            stylesheet.append(
                {"selector": f'[id = "{node}"]', "style": {"background-color": color}}
            )

    # Calculate percentages
    bill_percentage = (vote_counts["Bill"] / total_votes) * 100 if total_votes > 0 else 0
    bradley_percentage = (vote_counts["Bradley"] / total_votes) * 100 if total_votes > 0 else 0

    # Create the single bar showing vote percentages
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
            base=bill_percentage,  # Start Bradley's bar after Bill's
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

    line_fig = go.Figure()
    line_fig.add_trace(
        go.Scatter(
            x=episodes,
            y=Bill_votes_over_time,
            mode="lines+markers",
            name="Bill",
            line=dict(color="#1f77b4"),
        )
    )
    line_fig.add_trace(
        go.Scatter(
            x=episodes,
            y=Bradley_votes_over_time,
            mode="lines+markers",
            name="Bradley",
            line=dict(color="#ff7f0e"),
        )
    )

    line_fig.update_layout(
        title="Vote Distribution Over Time",
        xaxis_title="Episode",
        yaxis_title="Vote Percentage",
        height=200,
        margin=dict(l=40, r=40, t=20, b=10),
    )

    # If a user is selected, highlight them
    if selected_user and selected_user != "clear":
        stylesheet.append(
            {
                "selector": f'[id = "{selected_user}"]',
                "style": {
                    "opacity": 1,
                    "background-color": "#FF4136",
                    "color": "#FF4136",
                    "label": "data(label)",
                },
            }
        )

        connected_nodes = set()
        connected_edges = []

        # Determine connected nodes and edges
        for src, tgt, attr in interaction_graph.edges(data=True):
            if selected_user == src or selected_user == tgt:
                connected_nodes.update([src, tgt])
                connected_edges.append((src, tgt, attr))

        # Highlight connected nodes
        for n in connected_nodes:
            if n != selected_user:
                stylesheet.append(
                    {
                        "selector": f'[id = "{n}"]',
                        "style": {
                            "opacity": 1,
                            "background-color": "#2ECC40",
                            "color": "#000",
                            "label": "data(label)",
                        },
                    }
                )

        # Highlight connected edges
        for src, tgt, attr in connected_edges:
            stylesheet.append(
                {
                    "selector": f'[source = "{src}"][target = "{tgt}"]',
                    "style": {
                        "opacity": 1,
                        "line-color": "#FF851B",
                        "label": "data(label)",
                        "width": 6,
                        "curve-style": "bezier",
                        "target-arrow-shape": "triangle",
                    },
                }
            )

    return (
        stylesheet,
        fig,
        line_fig,
        f"Episode: {selected_episode}",
    )  # Return the new line graph figure


if __name__ == "__main__":
    app.run_server(debug=True)
