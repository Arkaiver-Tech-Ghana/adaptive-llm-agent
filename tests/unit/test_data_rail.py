from adaptive_agent.context.base import ContextDocument
from adaptive_agent.rails.data_rail import check_data_access, check_tool_data_access


def test_check_data_access_is_currently_a_passthrough():
    docs = [
        ContextDocument(name="faq.md", content="Some FAQ content."),
        ContextDocument(name="menu.md", content="Some menu content."),
    ]
    result = check_data_access(docs, business_id="kampuscrave")
    assert result == docs


def test_check_tool_data_access_is_currently_a_passthrough():
    tool_result = {"found": True, "item_name": "Veggie Burger", "price": 6.0}
    result = check_tool_data_access(tool_result, business_id="kampuscrave")
    assert result == tool_result
