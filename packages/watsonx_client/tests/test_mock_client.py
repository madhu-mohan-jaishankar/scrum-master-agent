"""Unit tests for MockWatsonxClient."""

from scrumagent_watsonx.mock_client import MockWatsonxClient


def test_classify_blocking_keyword() -> None:
    client = MockWatsonxClient()
    result = client.classify("This will break production — needs fixing.")
    assert result == "blocking"


def test_classify_nit_keyword() -> None:
    client = MockWatsonxClient()
    result = client.classify("nit: trailing whitespace on line 42.")
    assert result == "nit"


def test_classify_fallback() -> None:
    client = MockWatsonxClient()
    result = client.classify("LGTM, nice work!")
    assert result == "suggestion"  # default fallback


def test_generate_standup() -> None:
    client = MockWatsonxClient()
    result = client.generate("Write a standup update for alice based on recent activity.")
    assert "Completed" in result or "completed" in result.lower()


def test_generate_pre_standup_brief() -> None:
    client = MockWatsonxClient()
    result = client.generate("Write a pre-standup sprint health brief.")
    assert "Sprint Health" in result


def test_generate_retro() -> None:
    client = MockWatsonxClient()
    result = client.generate("Facilitate a retrospective for the sprint.")
    assert "Went Well" in result or "Improve" in result


def test_generate_release_notes() -> None:
    client = MockWatsonxClient()
    result = client.generate("Generate sprint release notes from merged PRs.")
    assert "Release Notes" in result or "Features" in result


def test_classify_commit_feature() -> None:
    client = MockWatsonxClient()
    result = client.classify("Classify this commit: feat: add user authentication")
    assert result == "feature"
