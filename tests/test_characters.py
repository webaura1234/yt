from utils.characters import (
    GUIDES,
    SIDEKICKS,
    cast_for_topic,
    describe_appearance,
    describe_cast,
    voice_for_speaker,
)
from utils.safety import is_safe


def test_cast_is_one_guide_and_one_sidekick():
    cast = cast_for_topic("Fun Mathematics and Number Tricks")

    assert len(cast) == 2
    assert cast[0] in GUIDES
    assert cast[1] in SIDEKICKS


def test_casting_is_stable_for_the_same_topic():
    # The whole point of a recurring cast is that a child meets the same
    # characters again. random.choice, or anything keyed on Python's salted
    # hash(), would re-cast the same topic differently on every run.
    first = cast_for_topic("Space, Planets and Stars")
    second = cast_for_topic("Space, Planets and Stars")

    assert [c.name for c in first] == [c.name for c in second]


def test_different_topics_can_draw_different_casts():
    names = {
        tuple(c.name for c in cast_for_topic(topic))
        for topic in (
            "Fun Mathematics and Number Tricks",
            "Space, Planets and Stars",
            "Moral Values and Good Behaviour",
            "Amazing Animals and Their Habits",
        )
    }

    assert len(names) > 1, "every topic drew the identical pair"


def test_every_character_is_described_in_telugu_with_a_look_and_a_voice():
    for character in GUIDES + SIDEKICKS:
        assert character.name, "character needs a name"
        # Telugu script lives in U+0C00-U+0C7F.
        assert any("ఀ" <= ch <= "౿" for ch in character.name)
        assert character.catchphrase
        assert character.voice
        assert len(character.appearance) > 40, "illustrator needs a real description"


def test_no_character_trips_the_kid_safety_gate():
    for character in GUIDES + SIDEKICKS:
        assert is_safe(character.personality), character.name
        assert is_safe(character.appearance), character.name
        assert is_safe(character.catchphrase), character.name


def test_describe_cast_names_every_character_for_the_writer():
    cast = cast_for_topic("Telugu Festivals and Traditions")
    described = describe_cast(cast)

    for character in cast:
        assert character.name in described
        assert character.catchphrase in described


def test_describe_appearance_carries_the_look_to_the_illustrator():
    cast = cast_for_topic("Our Body and Staying Healthy")
    described = describe_appearance(cast)

    for character in cast:
        assert character.appearance in described


def test_voice_for_speaker_maps_a_character_to_their_own_voice():
    cast = cast_for_topic("Nature, Plants and the Weather")
    speaker = cast[1]

    assert voice_for_speaker(speaker.name, cast, "Default") == speaker.voice
    # Tolerate the label formatting a script might use.
    assert voice_for_speaker(f"  {speaker.name}: ", cast, "Default") == speaker.voice


def test_voice_for_speaker_falls_back_for_narration_or_invented_speakers():
    cast = cast_for_topic("Nature, Plants and the Weather")

    assert voice_for_speaker("Narrator", cast, "Default") == "Default"
    assert voice_for_speaker("", cast, "Default") == "Default"
