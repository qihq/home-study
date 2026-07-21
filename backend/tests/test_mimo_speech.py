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
