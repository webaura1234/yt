import pytest

from utils.safety import (
    UnsafeContentError,
    assert_safe,
    filter_safe,
    find_unsafe,
    is_safe,
    safe_or_none,
)


# Content that must pass. A gate that fires on ordinary children's material is
# worse than useless: it blocks every good script and trains you to disable it.
@pytest.mark.parametrize(
    "text",
    [
        "సూర్యుడు ఎందుకు వేడిగా ఉంటాడు?",
        "Why is the sun hot? Fun science for kids",
        "చిట్టి మామిడి పండ్లు లెక్కపెట్టింది",
        "Gopi learned to wash his hands before eating",
        "A classic grape juice recipe from Grandma",
        "పండుగ రోజు అమ్మ పాయసం చేసింది",
        "The elephant is the largest land animal",
        "పిల్లి బామ్మ నిద్రపోతోంది",
    ],
)
def test_ordinary_kids_content_passes(text):
    assert is_safe(text), f"false positive: {find_unsafe(text)}"


@pytest.mark.parametrize(
    "text",
    [
        "The king killed his brother in a war",
        "This scary ghost haunted the old house",
        "A controversial politician was arrested",
        "They celebrated with beer and cigarettes",
        "రాజకీయ నాయకుడి వివాదం",
        "ఆ యుద్ధంలో చాలా మంది చనిపోయారు",
        "భయంకరమైన దెయ్యం కథ",
        "మద్యం తాగడం అలవాటు",
    ],
)
def test_unsuitable_content_is_blocked(text):
    assert not is_safe(text)
    assert find_unsafe(text)


def test_telugu_matching_survives_agglutinative_suffixes():
    # Telugu glues case and postposition endings onto the stem, so a word
    # boundary match would miss most real occurrences: "యుద్ధం" appears as
    # "యుద్ధంలో" in a real sentence.
    assert find_unsafe("యుద్ధంలో") == ["యుద్ధ"]
    assert find_unsafe("చనిపోయారు") == ["చనిపో"]


def test_english_matching_respects_word_boundaries():
    # Substring matching would flag "grape" for "rape" and "classic" for "ass";
    # both are ordinary words in children's content.
    assert is_safe("grape")
    assert is_safe("classic")
    assert is_safe("assignment")
    assert is_safe("Wardrobe")


def test_assert_safe_returns_text_unchanged_when_clean():
    text = "పిల్లలు ఆడుకుంటున్నారు"
    assert assert_safe(text) == text


def test_assert_safe_raises_with_the_matched_terms_and_location():
    with pytest.raises(UnsafeContentError) as excinfo:
        assert_safe("a violent war story", where="script")

    assert "script" in str(excinfo.value)
    assert set(excinfo.value.matches) >= {"violent", "war"}


def test_safe_or_none_returns_none_instead_of_raising():
    assert safe_or_none("a happy song") == "a happy song"
    assert safe_or_none("a murder mystery") is None


def test_filter_safe_keeps_only_the_clean_entries():
    titles = ["సూర్యుడి కథ", "a scary ghost", "counting mangoes"]

    assert filter_safe(titles) == ["సూర్యుడి కథ", "counting mangoes"]


def test_empty_text_is_safe():
    assert is_safe("")
    assert find_unsafe("") == []
