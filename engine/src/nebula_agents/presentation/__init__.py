"""Terminal presentation for the Nebula Agents cockpit.

The presentation package deliberately owns no authorization or state-transition
rules.  It translates argv and keyboard input into application-service calls and
renders the resulting immutable projections.
"""

from __future__ import annotations

__all__ = ["cli", "formatters", "session_entry", "transcript_filter", "tui"]
