import inspect

from app.agent import intake_agent
from app.tools import TOOLS

FOUR = {"create_lot", "get_quote", "escalate_to_human", "record_confirmation"}


def test_agent_name_and_exactly_four_tools():
    assert intake_agent.name == "intake_agent"
    assert {t.__name__ for t in TOOLS} == FOUR
    assert len(intake_agent.tools) == 4


def test_tools_take_no_identity_parameters():
    for tool in TOOLS:
        params = inspect.signature(tool).parameters
        assert not [p for p in params if "farmer" in p or "phone" in p or p == "call_id"]
