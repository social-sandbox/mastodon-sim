"""Sphinx configuration file for the Mastodon Social Simulation documentation."""

import os
import sys

sys.path.insert(0, os.path.abspath("../.."))

# -- Project information -----------------------------------------------------
project = "Mastodon Social Simulation"
copyright = "2024, TODO"
author = "TODO"

# -- General configuration ---------------------------------------------------
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "myst_parser",
    "sphinx_material",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Options for HTML output -------------------------------------------------
html_theme = "sphinx_material"

# Material theme options (see theme.conf for more information)
html_theme_options = {
    "nav_title": "Mastodon Social Simulation",
    "color_primary": "blue",
    "color_accent": "light-blue",
    "repo_url": "https://github.com/yourusername/mastodon-sim/",
    "repo_name": "Mastodon Social Simulation",
    # Visible levels of the global TOC; -1 means unlimited
    "globaltoc_depth": 3,
    "globaltoc_collapse": True,
    "globaltoc_includehidden": True,
}

html_static_path = ["_static"]

# Support both reStructuredText and Markdown
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}
