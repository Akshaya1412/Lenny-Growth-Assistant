from app.services.retrieval import retrieve_documents


def test_retrieval_returns_sources_for_growth_question():
    matches = retrieve_documents("How should we think about product-market fit and distribution?", top_k=3)
    assert matches
    assert any(match.source for match in matches)
    assert len(matches) <= 3
