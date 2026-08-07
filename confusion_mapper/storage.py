"""
Tiny persistence layer for session JSON files. Load, save, and a
default-path helper. I kept this separate from the analytical modules
so a change to the file format only touches one place.
"""

import os
import json
import importlib.metadata

from .taxonomy import DATA_FILE


def installed_package_version():
    """
    Read the installed package version from importlib.metadata rather
    than a hardcoded string. Learned this the hard way when my
    __version__ constant got out of sync with pyproject.toml one release.
    Falls back to a clear "not installed via pip" note instead of
    raising, this is only used for provenance, never for a real check.
    """
    try:
        return importlib.metadata.version("confusion-mapper")
    except importlib.metadata.PackageNotFoundError:
        return "unknown (not installed via pip)"


def load_sessions():
    """Load all saved sessions from the JSON data file."""
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_session(session):
    """Append a completed session dict to the JSON data file."""
    sessions = load_sessions()
    sessions.append(session)
    with open(DATA_FILE, "w") as f:
        json.dump(sessions, f, indent=2)


