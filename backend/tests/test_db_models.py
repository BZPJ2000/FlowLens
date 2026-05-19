import sys
from pathlib import Path

from sqlalchemy import Text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.models import AnalysisReport


def test_report_content_is_text_type():
    """content_md is a Text column (compatible with both SQLite and MySQL)."""
    content_type = AnalysisReport.__table__.columns.content_md.type
    assert isinstance(content_type, Text)
