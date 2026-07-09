from tableau_graphql_mcp.examples import CATEGORIES, EXAMPLES, SCHEMA_CHEATSHEET


def test_examples_well_formed():
    assert len(EXAMPLES) >= 24
    for e in EXAMPLES:
        assert {"category", "question", "graphql", "variables", "notes"} <= set(e)
        assert e["category"] in CATEGORIES
        assert e["graphql"].strip().startswith(("query", "{"))
        assert "{" in e["graphql"]


def test_every_category_has_examples():
    assert {e["category"] for e in EXAMPLES} == set(CATEGORIES)


def test_cheatsheet_mentions_key_rules():
    assert "nameWithin" in SCHEMA_CHEATSHEET
    assert "Connection" in SCHEMA_CHEATSHEET
