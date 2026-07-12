"""Property-based tests for the read-only guard, the security-critical parser.

`_is_write` decides whether a GraphQL document is a mutation/subscription and must
be rejected. It has to hold up against adversarial input: the word "mutation" hiding
inside a string literal or a comment must NOT trip it, and a real write op must always
be caught regardless of leading whitespace or case.
"""

from hypothesis import given
from hypothesis import strategies as st

from tableau_graphql_mcp.server import _is_write


@given(st.text())
def test_never_crashes(doc):
    assert isinstance(_is_write(doc), bool)


@given(
    op=st.sampled_from(["mutation", "subscription", "MUTATION", "Subscription"]),
    ws=st.text(alphabet=" \t\n", max_size=6),
)
def test_write_ops_always_detected(op, ws):
    assert _is_write(f"{ws}{op} Foo {{ x }}") is True


@given(payload=st.text(alphabet=st.characters(blacklist_characters='"\\'), max_size=40))
def test_word_inside_string_literal_is_not_a_write(payload):
    # The token appears only as data inside a string argument, never as an operation.
    doc = f'query {{ field(note: "{payload} mutation subscription") }}'
    assert _is_write(doc) is False


def test_word_in_comment_is_not_a_write():
    assert _is_write("# this mutation is only a comment\nquery { f }") is False


def test_plain_read_query_is_not_a_write():
    assert _is_write("{ workbooks { name } }") is False
    assert _is_write("query GetIt { columns { name } }") is False
