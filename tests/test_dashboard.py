"""Smoke test: every dashboard section renders without an exception."""
from pathlib import Path

import pytest

streamlit = pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"
SECTIONS = ["Overview", "Home advantage over time", "The COVID experiment", "Competition comparison",
            "Team explorer", "Travel and rest", "Team clusters", "Statistical models"]


@pytest.mark.parametrize("section", SECTIONS)
def test_section_renders(section):
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    at.sidebar.radio[0].set_value(section).run()
    assert not at.exception, [e.value for e in at.exception]
