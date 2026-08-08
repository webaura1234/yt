from utils.text import align_sentences_to_word_times, split_sentences


def test_split_sentences_basic_multi_sentence_script():
    script = "This is the hook. Here is the reveal. This is the impact."
    assert split_sentences(script) == [
        "This is the hook.",
        "Here is the reveal.",
        "This is the impact.",
    ]


def test_split_sentences_handles_exclamation_and_question_marks():
    script = "Did you know this? It's true! Nobody believed it."
    assert split_sentences(script) == [
        "Did you know this?",
        "It's true!",
        "Nobody believed it.",
    ]


def test_split_sentences_does_not_split_on_decimal_numbers():
    script = "It grew 3.5 times in a year. Nobody expected that."
    assert split_sentences(script) == [
        "It grew 3.5 times in a year.",
        "Nobody expected that.",
    ]


def test_split_sentences_drops_empty_fragments_from_double_punctuation():
    script = "Wait...  what?!  That's insane."
    sentences = split_sentences(script)
    assert all(s.strip() for s in sentences)
    assert "" not in sentences


def test_split_sentences_empty_script_returns_empty_list():
    assert split_sentences("") == []
    assert split_sentences("   ") == []


def _word(text, start, end):
    return {"text": text, "start": start, "end": end, "confidence": 1.0}


def test_align_sentences_to_word_times_happy_path_exact_word_count_match():
    sentences = ["This is one.", "Two words here now."]
    words = [
        _word("This", 0.0, 0.2),
        _word("is", 0.2, 0.4),
        _word("one.", 0.4, 0.8),
        _word("Two", 0.8, 1.0),
        _word("words", 1.0, 1.3),
        _word("here", 1.3, 1.5),
        _word("now.", 1.5, 1.9),
    ]

    times = align_sentences_to_word_times(sentences, words, total_duration=2.0)

    assert times == [(0.0, 0.8), (0.8, 1.9)]


def test_align_sentences_to_word_times_falls_back_on_word_count_mismatch():
    sentences = ["Short one.", "A much longer sentence goes here."]
    # Only 3 words total, but the sentences have 2 + 6 = 8 words combined -> mismatch.
    words = [_word("foo", 0.0, 1.0), _word("bar", 1.0, 2.0), _word("baz", 2.0, 4.0)]

    times = align_sentences_to_word_times(sentences, words, total_duration=4.0)

    assert len(times) == 2
    # Monotonic, contiguous, spans the full known word range.
    assert times[0][0] == 0.0
    assert times[0][1] == times[1][0]
    assert times[1][1] == 4.0
    # Proportional to character length: "Short one." (10 chars) vs the 34-char
    # second sentence - the first slice should be much shorter than the second.
    first_span = times[0][1] - times[0][0]
    second_span = times[1][1] - times[1][0]
    assert first_span < second_span


def test_align_sentences_to_word_times_falls_back_when_words_list_is_empty():
    sentences = ["One sentence.", "Another one here."]

    times = align_sentences_to_word_times(sentences, [], total_duration=10.0)

    assert len(times) == 2
    assert times[0][0] == 0.0
    assert times[-1][1] == 10.0


def test_align_sentences_to_word_times_empty_sentences_returns_empty_list():
    assert align_sentences_to_word_times([], [], total_duration=5.0) == []


def test_split_sentences_splits_telugu_narration():
    # Regression: the boundary used to require the next sentence to start with a
    # capital Latin letter. Telugu has no capitals, so an entire Telugu script
    # came back as one sentence - and since every visual stage is per-sentence,
    # the whole video collapsed to a single static image.
    script = (
        "అసలు వంకాయలు తయారవుతాయని మీకు తెలుసా. "
        "పిల్లి బామ్మ అడిగింది. "
        "తాతయ్య జ్ఞాని నవ్వారు."
    )

    assert len(split_sentences(script)) == 3


def test_split_sentences_handles_telugu_question_and_exclamation():
    script = "ఇది ఏమిటి? నాకు తెలియదు! సరే చూద్దాం."

    assert len(split_sentences(script)) == 3


def test_split_sentences_splits_on_the_danda_used_by_indic_scripts():
    assert len(split_sentences("पहला वाक्य। दूसरा वाक्य।")) == 2


def test_split_sentences_handles_blank_lines_between_sentences():
    # The script writer returns paragraphs separated by blank lines.
    script = "మొదటి వాక్యం.\n\nరెండవ వాక్యం.\n\nమూడవ వాక్యం."

    assert len(split_sentences(script)) == 3


def test_split_sentences_still_splits_english():
    assert len(split_sentences("This is one. This is two. This is three.")) == 3
