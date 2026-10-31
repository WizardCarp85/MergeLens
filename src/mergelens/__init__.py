"""mergelens — a Git-native merge conflict advisor.

Hard invariants (enforced by tests):
  * Only ``mergelens.git.runner`` may invoke a subprocess.
  * Only ``mergelens commit`` may run ``git commit``.
  * No command ever writes to the user's working tree.
"""

__version__ = "0.1.0.dev0"

MIN_GIT_VERSION = (2, 38, 0)
NOTES_REF = "refs/notes/mergelens"

__all__ = ["__version__", "MIN_GIT_VERSION", "NOTES_REF"]
