import argparse
import math
import re

import dash
import dash_cytoscape as cyto
import networkx as nx
import plotly.graph_objs as go
from dash import Input, Output, dcc, html
from plotly.subplots import make_subplots

# Load extra layouts for Cytoscape
cyto.load_extra_layouts()


def compute_positions(graph):
    # Use Kamada-Kawai layout for better distribution
    pos = nx.kamada_kawai_layout(graph, scale=750)

    # Ensure positions are scaled and rounded to prevent overlaps
    scaled_pos = {}
    for node, (x, y) in pos.items():
        scaled_pos[node] = {"x": x, "y": y}

    return scaled_pos


# Load and parse the interaction data
def load_data(filepath):
    follow_graph = nx.DiGraph()
    interactions_by_episode = {}
    posted_users_by_episode = {}
    with open(filepath) as file:
        lines = file.readlines()
        current_episode = None
        for line in lines:
            line = line.strip()

            if "Episode:" in line:
                match = re.match(r"Episode:\s*(\d+)(.*)", line)
                if match:
                    current_episode = int(
                        match.group(1)
                    )  # First capturing group is the episode number
                    remaining_text = match.group(
                        2
                    ).strip()  # Remaining part of the line after the episode number
                    line = remaining_text  # Continue processing the rest of the line as an action
                    interactions_by_episode[current_episode] = []
                    posted_users_by_episode[current_episode] = set()

            if "followed" in line:
                user = line.split()[0]
                target_user = line.split()[-1]
                follow_graph.add_edge(user, target_user)
            elif "replied" in line:
                if current_episode is not None:
                    action = "replied"
                    user = line.split()[0]
                    target_user = line.split()[6]
                    interactions_by_episode[current_episode].append(
                        {
                            "source": user,
                            "target": target_user,
                            "action": action,
                            "episode": current_episode,
                        }
                    )
            elif "boosted" in line:
                if current_episode is not None:
                    action = "boosted"
                    user = line.split()[0]
                    target_user = line.split()[5]
                    interactions_by_episode[current_episode].append(
                        {
                            "source": user,
                            "target": target_user,
                            "action": action,
                            "episode": current_episode,
                        }
                    )
            elif "liked" in line:
                if current_episode is not None:
                    action = "liked"
                    user = line.split()[0]
                    target_user = line.split()[5]
                    interactions_by_episode[current_episode].append(
                        {
                            "source": user,
                            "target": target_user,
                            "action": action,
                            "episode": current_episode,
                        }
                    )
            elif "posted" in line:
                if current_episode is not None:
                    user = line.split()[0]
                    posted_users_by_episode[current_episode].add(user)

    return follow_graph, interactions_by_episode, posted_users_by_episode


# Load and parse the vote data
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

    args = parser.parse_args()

    # Load the data using the files passed as arguments
    follow_graph, interactions_by_episode, posted_users_by_episode = load_data(
        args.interaction_file
    )
    votes = load_votes(args.votes_file)
    # Compute positions
    all_positions = compute_positions(follow_graph)

    # Add positions to the layout
    layout = {"name": "preset", "positions": all_positions}

    # Prepare Cytoscape elements with all nodes and all edges, classified by episode
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

    app = dash.Dash(__name__)

    # Create a list of unique names for the name selector dropdown
    unique_names = sorted(follow_graph.nodes)

    app.layout = html.Div(
        [
            # Line graphs container
            html.Div(
                [
                    # Vote distribution line graph
                    dcc.Graph(
                        id="vote-distribution-line",
                        config={"displayModeBar": False},
                        style={"height": "170px", "width": "48%", "display": "inline-block"},
                    ),
                    # Interactions count line graph
                    dcc.Graph(
                        id="interactions-line-graph",
                        config={"displayModeBar": False},
                        style={"height": "170px", "width": "48%", "display": "inline-block"},
                    ),
                ],
                style={"display": "flex", "justify-content": "space-between", "margin-top": "20px"},
            ),
            # Cytoscape graph
            html.Div(
                [
                    html.Div(
                        [
                            dcc.Dropdown(
                                id="name-selector",
                                options=[{"label": name, "value": name} for name in unique_names],
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
                        children=f"Episode: {min(interactions_by_episode.keys())}",
                    ),
                    cyto.Cytoscape(
                        id="cytoscape-graph",
                        elements=elements,  # Start with all nodes and edges
                        layout=layout,
                        style={"width": "100%", "height": "620px", "background-color": "#e1e1e1"},
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
                                "selector": '[id="Bill"]',
                                "style": {
                                    "background-color": "blue",
                                    "border-color": "#000000",
                                },
                            },
                            {
                                "selector": '[id="Bradley"]',
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
                min=min(interactions_by_episode.keys()),
                max=max(interactions_by_episode.keys()),
                value=min(interactions_by_episode.keys()),
                marks={str(episode): str(episode) for episode in interactions_by_episode.keys()},
                step=None,
                tooltip={"placement": "bottom", "always_visible": True},
            ),
            dcc.Graph(
                id="vote-percentages-bar",
                config={"displayModeBar": False},
                style={"height": "50px", "margin-top": "20px"},
            ),
        ]
    )

    @app.callback(
        [
            Output("cytoscape-graph", "layout"),
            Output("cytoscape-graph", "stylesheet"),
            Output("vote-percentages-bar", "figure"),
            Output("vote-distribution-line", "figure"),
            Output("interactions-line-graph", "figure"),
            Output("current-episode", "children"),  # Added Output
        ],
        [
            Input("episode-slider", "value"),
            Input("mode-dropdown", "value"),
            Input("name-selector", "value"),  # Added Input
        ],
    )
    def update_graph(selected_episode, selected_mode, selected_name):
        # Base stylesheet (node styles, follow edges)
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
                "selector": '[id="Bill"]',
                "style": {
                    "background-color": "blue",
                    "border-color": "#000000",
                },
            },
            {
                "selector": '[id="Bradley"]',
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

        layout = {}
        current_episode_display = f"Episode: {selected_episode}"  # Updated episode display

        active_nodes = set()
        active_nodes = {
            interaction["source"] for interaction in interactions_by_episode[selected_episode]
        }.union(
            {interaction["target"] for interaction in interactions_by_episode[selected_episode]}
        ).union(posted_users_by_episode[selected_episode])
        if selected_mode == "focused":
            # Identify active nodes based on interactions and posted users
            active_nodes = {
                interaction["source"] for interaction in interactions_by_episode[selected_episode]
            }.union(
                {interaction["target"] for interaction in interactions_by_episode[selected_episode]}
            ).union(posted_users_by_episode[selected_episode])

            non_active_nodes = [node for node in follow_graph.nodes if node not in active_nodes]

            # Compute positions for active nodes using NetworkX's Kamada-Kawai layout
            active_subgraph = follow_graph.subgraph(active_nodes)
            if len(active_nodes) > 0:
                active_pos = nx.kamada_kawai_layout(active_subgraph, scale=1500)
            else:
                active_pos = {}

            for node in active_pos:
                x, y = active_pos[node]
                active_pos[node] = {"x": x, "y": y}

            # Assign peripheral positions to non-active nodes in a circular layout
            num_non_active = len(non_active_nodes)
            peripheral_radius = 1800  # Distance from the center for peripheral nodes

            angle_step = (2 * math.pi) / max(num_non_active, 1)
            positions_non_active = {}
            for i, node in enumerate(non_active_nodes):
                angle = i * angle_step
                x_pos = peripheral_radius * math.cos(angle)
                y_pos = peripheral_radius * math.sin(angle)
                positions_non_active[node] = {"x": x_pos, "y": y_pos}

            # Combine positions
            all_positions = {}
            for node, pos in active_pos.items():
                all_positions[node] = pos
            for node, pos in positions_non_active.items():
                all_positions[node] = pos

            # Set layout to preset with all positions
            layout = {"name": "preset", "positions": all_positions}

            # Style non-active nodes in gray and smaller
            for node in non_active_nodes:
                stylesheet.append(
                    {
                        "selector": f'[id="{node}"]',
                        "style": {
                            "background-color": "#d3d3d3",  # Gray out inactive nodes
                            "width": "120px",
                            "height": "120px",
                            "font-size": "30px",
                            "border-width": 4,
                        },
                    }
                )

            # Style active nodes to be larger and more visible
            for node in active_nodes:
                stylesheet.append(
                    {
                        "selector": f'[id="{node}"]',
                        "style": {
                            "width": "200px",  # Increase active node size
                            "height": "200px",
                            "border-width": 10,  # Thicker border for visibility
                            "font-size": "60px",  # Larger font size
                            "border-color": "#000000",  # High contrast border
                        },
                    }
                )
        else:
            # Normal mode: use preset layout with precomputed positions
            all_positions = compute_positions(follow_graph)
            layout = {"name": "preset", "positions": all_positions}

            # Reapply base styles since we're resetting layout
            # No additional styling needed as positions are already spread out

        # Highlight selected node and the nodes they follow (Added functionality)
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
        episode_votes = votes[selected_episode]
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

        # Initialize lists to store normalized interactions and active user fractions

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
                interactions_over_time[interaction].append(counts[interaction] / num_active_users)

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
                    0,
                    len(episodes) + 1,
                ],  # Setting the range from 0 to length of episodes + 1
                "dtick": 10,  # Show a tick marker every 5 episodes
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
        return (
            layout,
            stylesheet,
            fig,
            vote_line_fig,
            interactions_line_fig,
            current_episode_display,
        )  # Added Output

    # Run the Dash app
    app.run_server(debug=True)
