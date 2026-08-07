"""
Session persistence: load and save coded sessions to the local JSON data file.

load_sessions() and save_session() were moved unmodified from the
"SECTION 5, DATA PERSISTENCE (file I/O)" block of the pre-2.6.0 single-file
confusion_mapper.py during the v2.6.0 package reorganization -- no logic
changed. installed_package_version() is new in this release, added to
support session provenance (see console.py's run_session()).
"""

import os
import json
import importlib.metadata

from .taxonomy import DATA_FILE


def installed_package_version():
    """
    The actually-installed confusion-mapper package version, read from
    package metadata rather than a hardcoded string -- so it can't drift
    out of sync with what's really on PyPI the way the internal
    `confusion_mapper.__version__` string has (see CHANGELOG v2.6.0 note).
    Falls back to a clear "not installed via pip" marker rather than
    raising, since this is only ever used for informational provenance,
    never for a version check anything depends on.
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


