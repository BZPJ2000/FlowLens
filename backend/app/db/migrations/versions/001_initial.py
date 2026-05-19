"""Initial schema — all tables

Revision ID: 001
Revises:
Create Date: 2026-05-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Projects
    op.create_table(
        "projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_url", sa.Text(), default=""),
        sa.Column("storage_path", sa.Text(), default=""),
        sa.Column("file_count", sa.Integer(), default=0),
        sa.Column("total_size_kb", sa.Integer(), default=0),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    # Analyses
    op.create_table(
        "analyses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("error_message", sa.Text(), default=""),
        sa.Column("progress_pct", sa.Integer(), default=0),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
    )

    # FileNodes
    op.create_table(
        "file_nodes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("analysis_id", sa.String(36),
                  sa.ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_path", sa.String(1000), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("language", sa.String(50), default="unknown"),
        sa.Column("content_hash", sa.String(64), default=""),
        sa.Column("summary", sa.String(500), default=""),
        sa.Column("detail_explain", sa.Text(), default=""),
        sa.Column("imports_json", sa.JSON(), default=list),
        sa.Column("exports_json", sa.JSON(), default=list),
        sa.Column("functions_json", sa.JSON(), default=list),
        sa.Column("classes_json", sa.JSON(), default=list),
        sa.Column("raw_content", sa.Text(), default=""),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    # DataEdges
    op.create_table(
        "data_edges",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("analysis_id", sa.String(36),
                  sa.ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_file_id", sa.String(36),
                  sa.ForeignKey("file_nodes.id", ondelete="CASCADE"), nullable=True),
        sa.Column("to_file_id", sa.String(36),
                  sa.ForeignKey("file_nodes.id", ondelete="CASCADE"), nullable=True),
        sa.Column("from_port_name", sa.String(255), default=""),
        sa.Column("to_port_name", sa.String(255), default=""),
        sa.Column("variable_name", sa.String(255), nullable=False),
        sa.Column("data_type", sa.String(255), default="unknown"),
        sa.Column("edge_type", sa.String(20), default="import"),
        sa.Column("metadata_json", sa.JSON(), default=dict),
    )

    # FunctionPorts
    op.create_table(
        "function_ports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("file_node_id", sa.String(36),
                  sa.ForeignKey("file_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("params_json", sa.JSON(), default=list),
        sa.Column("return_type", sa.String(255), default="unknown"),
        sa.Column("is_exported", sa.Boolean(), default=False),
        sa.Column("is_imported", sa.Boolean(), default=False),
        sa.Column("position", sa.Integer(), default=0),
    )

    # ChatSessions
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("analysis_id", sa.String(36),
                  sa.ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), default="新对话"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    # ChatMessages
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36),
                  sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("referenced_nodes", sa.JSON(), default=list),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    # AnalysisReports
    op.create_table(
        "analysis_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("analysis_id", sa.String(36),
                  sa.ForeignKey("analyses.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("content_md", mysql.LONGTEXT(), default=""),
        sa.Column("architecture_summary", sa.Text(), default=""),
        sa.Column("issue_count", sa.Integer(), default=0),
        sa.Column("generated_at", sa.DateTime(timezone=True)),
    )

    # Indexes
    op.create_index("idx_file_nodes_analysis", "file_nodes", ["analysis_id"])
    op.create_index("idx_file_nodes_path", "file_nodes", ["analysis_id", "file_path"])
    op.create_index("idx_data_edges_analysis", "data_edges", ["analysis_id"])
    op.create_index("idx_data_edges_from", "data_edges", ["from_file_id"])
    op.create_index("idx_data_edges_to", "data_edges", ["to_file_id"])
    op.create_index("idx_function_ports_file", "function_ports", ["file_node_id"])
    op.create_index("idx_chat_messages_session", "chat_messages", ["session_id"])


def downgrade() -> None:
    op.drop_table("analysis_reports")
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
    op.drop_table("function_ports")
    op.drop_table("data_edges")
    op.drop_table("file_nodes")
    op.drop_table("analyses")
    op.drop_table("projects")
