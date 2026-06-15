"""Workflow templates and field registry

Revision ID: 003
Revises: 002
Create Date: 2026-06-13
"""
from typing import Sequence, Union
import json
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DATA_CHANGE_STEPS = [
    {"seq": 1, "action": "login", "name": "Open Salesforce", "params": {}},
    {"seq": 2, "action": "open_app_launcher", "name": "Open App Launcher", "params": {}, "optional": True},
    {"seq": 3, "action": "open_app", "name": "Open Onboarding Application", "params": {"app": "Onboarding"}, "optional": True},
    {"seq": 4, "action": "open_queues", "name": "Open Customer Lifecycle Queues", "params": {}},
    {"seq": 5, "action": "click_new_button", "name": "Click New", "params": {"button_label": "New"}},
    {
        "seq": 6,
        "action": "select_request_module",
        "name": "Select Request Module",
        "params": {"module_option": "{RequestModule}"},
    },
    {
        "seq": 7,
        "action": "select_sales_office",
        "name": "Enter Sales Office",
        "params": {"office": "{SalesOffice}", "field": "Sales Office"},
    },
    {
        "seq": 8,
        "action": "open_customer_search",
        "name": "Open Customer Search",
        "params": {"field": "Customer Number"},
        "skip_if_input": "CustomerNumber",
    },
    {
        "seq": 9,
        "action": "enter_customer_number",
        "name": "Enter Customer Number",
        "params": {"customer_number": "{CustomerNumber}", "field": "Customer Number"},
        "require_input": "CustomerNumber",
    },
    {"seq": 10, "action": "wait_for_customer_dropdown", "name": "Wait For Customer Dropdown", "params": {}},
    {
        "seq": 11,
        "action": "select_first_customer",
        "name": "Select First Customer From Dropdown",
        "params": {"field": "Customer Number"},
    },
    {"seq": 12, "action": "search", "name": "Click Search", "params": {}},
    {"seq": 13, "action": "wait_for_data", "name": "Wait For Customer Data To Load", "params": {}},
]

DATA_CHANGE_INPUTS = {
    "RequestModule": {"type": "menu_item", "default": "NEW DATA CHANGE", "label": "Request Module"},
    "SalesOffice": {"type": "combobox", "default": "__any__", "label": "Sales Office"},
    "CustomerNumber": {"type": "lookup", "default": "__first__", "label": "Customer Number"},
}

def _stub_steps(module: str) -> list:
    return [
        {"seq": 1, "action": "login", "name": "Open Salesforce", "params": {}},
        {"seq": 2, "action": "open_queues", "name": "Open Customer Lifecycle Queues", "params": {}},
        {"seq": 3, "action": "click_new_button", "name": "Click New", "params": {"button_label": "New"}},
        {
            "seq": 4,
            "action": "select_request_module",
            "name": "Select Request Module",
            "params": {"module_option": "{RequestModule}"},
        },
    ]


def _stub_inputs(module_default: str) -> dict:
    return {
        "RequestModule": {"type": "menu_item", "default": module_default, "label": "Request Module"},
    }


TEMPLATES = [
    {
        "key": "DATA_CHANGE_REQUEST",
        "name": "Data Change Request",
        "description": "Navigate to Data Change request form and prepare customer search",
        "steps": DATA_CHANGE_STEPS,
        "input_schema": DATA_CHANGE_INPUTS,
    },
    {
        "key": "NEW_CUSTOMER_REQUEST",
        "name": "New Customer Request",
        "description": "Create a new customer request from the New menu",
        "steps": _stub_steps("NEW DSD CUSTOMER"),
        "input_schema": _stub_inputs("NEW DSD CUSTOMER"),
    },
    {
        "key": "NEW_FSV_CUSTOMER",
        "name": "New FSV Customer",
        "description": "Create a new FSV customer request",
        "steps": _stub_steps("NEW FSV CUSTOMER"),
        "input_schema": _stub_inputs("NEW FSV CUSTOMER"),
    },
    {
        "key": "NEW_DSD_CUSTOMER",
        "name": "New DSD Customer",
        "description": "Create a new DSD customer request",
        "steps": _stub_steps("NEW DSD CUSTOMER"),
        "input_schema": _stub_inputs("NEW DSD CUSTOMER"),
    },
    {
        "key": "ACCOUNT_RECEIVABLE",
        "name": "Account Receivable",
        "description": "Account receivable workflow stub",
        "steps": _stub_steps("NEW PAYER"),
        "input_schema": _stub_inputs("NEW PAYER"),
    },
    {
        "key": "CONTACT_UPDATE",
        "name": "Contact Update",
        "description": "Contact update workflow stub",
        "steps": _stub_steps("CUSTOMER SUPPRESSION"),
        "input_schema": _stub_inputs("CUSTOMER SUPPRESSION"),
    },
]


def upgrade() -> None:
    op.create_table(
        "workflow_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("steps", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("input_schema", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_workflow_templates_key", "workflow_templates", ["key"])

    op.create_table(
        "workflow_field_registry",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "template_key",
            sa.String(100),
            sa.ForeignKey("workflow_templates.key"),
            nullable=False,
        ),
        sa.Column("field_name", sa.String(255), nullable=False),
        sa.Column("field_type", sa.String(50), nullable=False),
        sa.Column("locator_hints", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("template_key", "field_name", name="uq_template_field"),
    )
    op.create_index("ix_workflow_field_registry_template_key", "workflow_field_registry", ["template_key"])

    op.add_column("scenarios", sa.Column("template_key", sa.String(100), nullable=True))
    op.add_column(
        "scenarios",
        sa.Column("inputs", postgresql.JSONB(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "scenarios",
        sa.Column("business_actions", postgresql.JSONB(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "scenarios",
        sa.Column("expected_results", postgresql.JSONB(), nullable=False, server_default="[]"),
    )
    op.create_foreign_key(
        "fk_scenarios_template_key",
        "scenarios",
        "workflow_templates",
        ["template_key"],
        ["key"],
    )

    conn = op.get_bind()
    for tpl in TEMPLATES:
        conn.execute(
            sa.text(
                """
                INSERT INTO workflow_templates (id, key, name, description, steps, input_schema, is_active)
                VALUES (:id, :key, :name, :description, CAST(:steps AS jsonb), CAST(:input_schema AS jsonb), true)
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "key": tpl["key"],
                "name": tpl["name"],
                "description": tpl["description"],
                "steps": json.dumps(tpl["steps"]),
                "input_schema": json.dumps(tpl["input_schema"]),
            },
        )


def downgrade() -> None:
    op.drop_constraint("fk_scenarios_template_key", "scenarios", type_="foreignkey")
    op.drop_column("scenarios", "expected_results")
    op.drop_column("scenarios", "business_actions")
    op.drop_column("scenarios", "inputs")
    op.drop_column("scenarios", "template_key")
    op.drop_table("workflow_field_registry")
    op.drop_table("workflow_templates")
