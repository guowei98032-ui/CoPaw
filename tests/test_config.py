# -*- coding: utf-8 -*-
"""Shared test configuration and constants.

Provides real agent IDs that must exist in the system for tests to work.
Update these values to match your actual agent configuration.

To get available agents:
    curl http://127.0.0.1:8088/api/agents
"""

# REAL agents in the system - MUST match actual agent IDs
# Update these to match your actual agent IDs from /api/agents
REAL_LEAD_AGENT = "Ls9Gr3"
REAL_WORKER_1 = "ztNTTm"
REAL_WORKER_2 = "default"
REAL_WORKER_3 = "CoPaw_QA_Agent_0.1beta1"

# Convenient groupings
REAL_WORKER_AGENTS = [REAL_WORKER_1, REAL_WORKER_2, REAL_WORKER_3]
REAL_ALL_AGENTS = [REAL_LEAD_AGENT] + REAL_WORKER_AGENTS

# API endpoints
BASE_URL = "http://127.0.0.1:8088/api"
CHATROOM_URL = f"{BASE_URL}/chatroom"
CONSOLE_URL = f"{BASE_URL}/console"


def get_real_agents():
    """Return list of real agent IDs."""
    return REAL_ALL_AGENTS


def get_lead_agent():
    """Return the lead agent ID."""
    return REAL_LEAD_AGENT


def get_worker_agents(count: int = 3) -> list:
    """Return worker agent IDs.

    Args:
        count: Number of workers to return (1-3)

    Returns:
        List of worker agent IDs
    """
    return REAL_WORKER_AGENTS[:max(1, min(count, len(REAL_WORKER_AGENTS)))]