"""Customer lifecycle navigation helpers."""

import re

from app.automation.pages.customer_lifecycle_page import (
    NEW_MENU_MARKERS,
    QUEUES_HEADER_PATTERN,
    QUEUES_LAUNCHER_ITEMS,
    QUEUES_LAUNCHER_PRIMARY,
    QUEUES_TAB_NAMES,
)


def test_queues_tab_names_include_pipe_variant():
    assert "Customer Life Cycle | Queue" in QUEUES_TAB_NAMES


def test_queues_tab_regex_matches_scratch_org_tab():
    pattern = re.compile(r"Customer\s*Life\s*Cycle\s*\|\s*Queue", re.I)
    assert pattern.search("Customer Life Cycle | Queue")
    assert pattern.search("Customer Life Cycle | Queues")


def test_queues_launcher_items_prefer_pipe_queue_label():
    assert QUEUES_LAUNCHER_ITEMS[0] == "Customer Life Cycle | Queue"
    assert QUEUES_LAUNCHER_PRIMARY == "Customer Life Cycle | Queue"


def test_queues_header_pattern_matches_list_title():
    assert QUEUES_HEADER_PATTERN.search("Customer Life Cycle | Queue")
    assert QUEUES_HEADER_PATTERN.search("Customer Life Cycle Queues")
    assert not QUEUES_HEADER_PATTERN.search("Opportunities")


def test_new_menu_markers_include_data_change():
    assert "NEW DATA CHANGE" in NEW_MENU_MARKERS
