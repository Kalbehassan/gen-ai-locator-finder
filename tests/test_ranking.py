# SPDX-License-Identifier: MIT

from app.ml.ranking import LocatorRanker


def test_testid_out_ranks_opaque_xpath() -> None:
    ranker = LocatorRanker()
    test_id = ranker.score_candidate(
        strategy="test_id", value="save-button", explanation="Stable test ID"
    )
    xpath = ranker.score_candidate(
        strategy="xpath", value="//div/span/button[2]", explanation="Opaque fallback"
    )
    assert test_id.confidence > xpath.confidence


def test_rank_attaches_positions() -> None:
    ranker = LocatorRanker()
    candidates = [
        ranker.score_candidate(strategy="text", value="Save", explanation="Text"),
        ranker.score_candidate(strategy="role", value="button[name='Save']", explanation="Role"),
    ]
    ranked = ranker.rank(candidates)
    assert ranked[0].rank == 1
