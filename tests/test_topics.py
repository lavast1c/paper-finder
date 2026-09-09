from paper_finder.topics import BY_CODE, CODES, TOPICS


def test_taxonomy_is_the_eleven_syllabus_sections():
    assert len(TOPICS) == 11
    assert [t.code for t in TOPICS] == [f"s{n:02d}" for n in range(1, 12)]
    assert [t.number for t in TOPICS] == list(range(1, 12))


def test_every_topic_has_a_name_blurb_and_subsections():
    for t in TOPICS:
        assert t.name.strip()
        assert len(t.blurb) > 80, f"{t.code} blurb is too thin to classify against"
        assert t.subsections, t.code
        assert all(s.strip() for s in t.subsections)


def test_lookup_tables_agree_with_the_tuple():
    assert set(CODES) == {t.code for t in TOPICS}
    assert BY_CODE["s07"].name == "Waves"
    assert all(BY_CODE[t.code] is t for t in TOPICS)


def test_topic_is_frozen():
    import dataclasses

    import pytest

    with pytest.raises(dataclasses.FrozenInstanceError):
        TOPICS[0].name = "changed"  # type: ignore[misc]
