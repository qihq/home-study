import pytest


def test_spoken_messages_keep_control_text_out_of_assistant_content() -> None:
    from app.services.mimo_speech import spoken_messages

    messages = spoken_messages('  apple  ', 'Read clearly')

    assert messages[-1] == {'role': 'assistant', 'content': 'apple'}
    assert 'Read clearly' not in messages[-1]['content']
    assert 'apple' not in messages[0]['content']


def test_spoken_messages_reject_empty_text() -> None:
    from app.services.mimo_speech import spoken_messages

    with pytest.raises(ValueError, match='TTS_TEXT_EMPTY'):
        spoken_messages('\n\t')


def test_spoken_messages_use_scenario_specific_instruction() -> None:
    from app.services.mimo_speech import SENTENCE_INSTRUCTION, WORD_INSTRUCTION, spoken_messages

    word = spoken_messages('apple', scenario='word')
    sentence = spoken_messages('I like apples.', scenario='sentence')

    assert word[0]['content'] == WORD_INSTRUCTION
    assert sentence[0]['content'] == SENTENCE_INSTRUCTION


def test_spoken_messages_clone_scenario_keeps_only_style_instruction() -> None:
    from app.services.mimo_speech import spoken_messages

    styled = spoken_messages('apple', '温柔的女声', scenario='clone')
    unstyled = spoken_messages('apple', scenario='clone')

    assert styled[0] == {'role': 'user', 'content': '温柔的女声'}
    assert unstyled[0] == {'role': 'user', 'content': ''}


def test_speed_phrase_mapping() -> None:
    from app.services.mimo_speech import speed_phrase

    assert speed_phrase(0.5) == '语速明显放慢。'
    assert speed_phrase(0.8) == '语速稍慢。'
    assert speed_phrase(1.0) == ''
    assert speed_phrase(1.2) == '语速稍快。'
    assert speed_phrase(1.6) == '语速明显加快。'


def test_detect_language_and_word_shape() -> None:
    from app.services.mimo_speech import detect_language, is_word_text

    assert detect_language('apple') == 'en'
    assert detect_language('I like apples') == 'en'
    assert detect_language('苹果') == 'zh'
    assert detect_language('我喜欢苹果。') == 'zh'

    assert is_word_text('apple') is True
    assert is_word_text("don't") is True
    assert is_word_text('苹果') is True
    assert is_word_text('I like apples') is False
    assert is_word_text('two words') is False


def test_resolve_voice_picks_language_specific_voice() -> None:
    from app.services.mimo_speech import DEFAULT_EN_VOICE, DEFAULT_ZH_VOICE, resolve_voice

    assert resolve_voice('Chloe', '冰糖', 'en') == 'Chloe'
    assert resolve_voice('Chloe', '冰糖', 'zh') == '冰糖'
    assert resolve_voice('', '', 'en') == DEFAULT_EN_VOICE
    assert resolve_voice('', '', 'zh') == DEFAULT_ZH_VOICE
