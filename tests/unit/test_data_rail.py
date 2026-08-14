from adaptive_agent.context.base import ContextDocument
from adaptive_agent.rails.data_rail import check_data_access


def test_check_data_access_is_currently_a_passthrough():
    docs = [
        ContextDocument(name="faq.md", content="Some FAQ content."),
        ContextDocument(name="menu.md", content="Some menu content."),
    ]
    result = check_data_access(docs, business_id="kampuscrave")
    assert result == docs
