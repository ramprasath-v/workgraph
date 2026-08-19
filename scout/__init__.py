"""Read-only current-task scouting and handoff artifacts."""

from .schema import ScoutHandoff, load_scout_handoff

__all__ = ["ScoutHandoff", "load_scout_handoff"]
