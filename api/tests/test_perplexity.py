"""Citation extraction and the upstream serialization repair."""

from types import SimpleNamespace

from app.clients.perplexity import extract_citations, repair_search_result_schema


class _Msg:
    def __init__(self, response_metadata=None, additional_kwargs=None):
        self.response_metadata = response_metadata or {}
        self.additional_kwargs = additional_kwargs or {}


def test_citations_come_from_additional_kwargs():
    """Verified live shape: response_metadata carries no citations."""
    msg = _Msg(
        response_metadata={"model_name": "sonar-pro", "search_context_size": "low"},
        additional_kwargs={"citations": ["https://a.example", "https://b.example"]},
    )
    assert extract_citations(msg) == ["https://a.example", "https://b.example"]


def test_search_results_are_sdk_objects_not_dicts():
    """`search_results` items are `APIPublicSearchResult`, not dicts.

    The original implementation gated this branch on `isinstance(r, dict)`, so it
    silently never matched and extraction only worked via the `citations`
    fallback. That made the richer branch dead code — and would have returned
    zero citations outright had Perplexity ever dropped the flat list.
    """
    msg = _Msg(
        additional_kwargs={
            "search_results": [
                SimpleNamespace(url="https://x.example", title="X"),
                SimpleNamespace(url="https://y.example", title="Y"),
            ]
        }
    )
    assert extract_citations(msg) == ["https://x.example", "https://y.example"]


def test_search_results_preferred_over_flat_citations():
    msg = _Msg(
        additional_kwargs={
            "search_results": [SimpleNamespace(url="https://rich.example")],
            "citations": ["https://flat.example"],
        }
    )
    assert extract_citations(msg) == ["https://rich.example"]


def test_no_citations_is_empty_not_an_error():
    assert extract_citations(_Msg()) == []


def test_repair_search_result_schema_completes_the_sdk_model():
    """The `perplexityai` SDK ships this model with an unbuilt schema.

    Left alone, its serializer is a `MockValSer`, LangSmith's `on_llm_end` raises
    while serializing it, and every ChatPerplexity span stays `pending` with no
    outputs — tracing that looks enabled but records nothing useful.
    """
    from perplexity.types.shared.api_public_search_result import APIPublicSearchResult

    assert repair_search_result_schema() is True
    assert APIPublicSearchResult.__pydantic_complete__
    assert type(APIPublicSearchResult.__pydantic_serializer__).__name__ == "SchemaSerializer"
