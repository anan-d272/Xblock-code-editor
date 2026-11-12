"""
Minimal Coding Exam XBlock — "Hello" slice.

Displays a placeholder student view and a stub studio view.
Real features (code editor, run/submit, grading) will be added later.
"""
from web_fragments.fragment import Fragment
from xblock.core import XBlock
from xblock.fields import Scope, String


class CodingExamXBlock(XBlock):
    """An XBlock that will host coding exam functionality."""

    # ------------------------------------------------------------------ #
    # Fields
    # ------------------------------------------------------------------ #

    display_name = String(
        display_name="Display Name",
        default="Coding Exam",
        scope=Scope.settings,
        help="The name shown to students and in Studio.",
    )

    # ------------------------------------------------------------------ #
    # Views
    # ------------------------------------------------------------------ #

    def student_view(self, context=None):
        """Rendered for students (and in the LMS preview)."""
        html = "<p>Hello from the Coding Exam XBlock</p>"
        return Fragment(html)

    def studio_view(self, context=None):
        """Rendered inside Studio when an author opens the block editor."""
        html = "<p>Studio settings will go here</p>"
        return Fragment(html)

