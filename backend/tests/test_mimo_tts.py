import base64
import json
import pytest


def _synthesize(monkeypatch, client, text: str) -> tuple[bytes, dict]:
    captured = {}

    def fake_urlopen(request, timeout):
        captured['payload'] = request.data
        class Response:
            def read(self):
                return ('{"choices":[{"message":{"audio":{"data":"' + base64.b64encode(b'wav-bytes').decode() + '"}}}]}').encode()
            def __enter__(self): return self
            def __exit__(self, *_): return False
        return Response()

    import app.services.mimo_tts as module
    monkeypatch.setattr(module, 'urlopen', fake_urlopen)
    audio = client.synthesize(text)
    return audio, json.loads(captured['payload'])


def test_mimo_tts_uses_official_chat_completion_payload(monkeypatch) -> None:
    from app.services.mimo_tts import MimoTtsClient

    captured = {}
    def fake_urlopen(request, timeout):
        captured['url'] = request.full_url
        captured['headers'] = {key.casefold(): value for key, value in request.header_items()}
        captured['payload'] = request.data
        class Response:
            def read(self):
                return ('{"choices":[{"message":{"audio":{"data":"' + base64.b64encode(b'wav-bytes').decode() + '"}}}]}').encode()
            def __enter__(self): return self
            def __exit__(self, *_): return False
        return Response()
    monkeypatch.setattr('app.services.mimo_tts.urlopen', fake_urlopen)

    audio = MimoTtsClient('test-key', 'https://api.xiaomimimo.com/v1', 'mimo-v2.5-tts', 'Chloe').synthesize('apple')

    assert audio == b'wav-bytes'
    assert captured['url'] == 'https://api.xiaomimimo.com/v1/chat/completions'
    assert captured['headers']['api-key'] == 'test-key'
    assert b'"model":"mimo-v2.5-tts"' in captured['payload']
    assert b'"voice":"Chloe"' in captured['payload']
    payload = json.loads(captured['payload'])
    assert payload['messages'][0]['role'] == 'user'
    assert payload['messages'][1] == {'role': 'assistant', 'content': 'apple'}
    assert 'apple' not in payload['messages'][0]['content']
    assert 'translate' not in str(payload['messages']).lower()


def test_mimo_tts_uses_word_instruction_for_single_words(monkeypatch) -> None:
    from app.services.mimo_speech import WORD_INSTRUCTION
    from app.services.mimo_tts import MimoTtsClient

    audio, payload = _synthesize(monkeypatch, MimoTtsClient('test-key', 'https://api.example/v1', 'mimo-v2.5-tts', 'Chloe'), 'apple')

    assert audio == b'wav-bytes'
    assert payload['messages'] == [
        {'role': 'user', 'content': WORD_INSTRUCTION},
        {'role': 'assistant', 'content': 'apple'},
    ]
    assert payload['audio'] == {'format': 'wav', 'voice': 'Chloe'}


def test_mimo_tts_uses_sentence_instruction_and_speed_phrase(monkeypatch) -> None:
    from app.services.mimo_speech import SENTENCE_INSTRUCTION
    from app.services.mimo_tts import MimoTtsClient

    _audio, payload = _synthesize(
        monkeypatch,
        MimoTtsClient('test-key', 'https://api.example/v1', 'mimo-v2.5-tts', 'Chloe', speed=0.6),
        'I like apples.',
    )

    instruction = payload['messages'][0]['content']
    assert SENTENCE_INSTRUCTION in instruction
    assert '语速明显放慢。' in instruction
    assert payload['messages'][1] == {'role': 'assistant', 'content': 'I like apples.'}


def test_mimo_tts_omits_speed_phrase_at_neutral_speed(monkeypatch) -> None:
    from app.services.mimo_tts import MimoTtsClient

    _audio, payload = _synthesize(
        monkeypatch,
        MimoTtsClient('test-key', 'https://api.example/v1', 'mimo-v2.5-tts', 'Chloe', speed=1.0),
        'hello there',
    )

    instruction = payload['messages'][0]['content']
    assert '语速' not in instruction


def test_mimo_tts_rejects_empty_spoken_text() -> None:
    from app.services.mimo_tts import MimoTtsClient

    with pytest.raises(ValueError, match='TTS_TEXT_EMPTY'):
        MimoTtsClient('test-key', 'https://api.example/v1', 'model', 'voice').synthesize('   ')


def test_mimo_tts_stream_yields_pcm16_chunks(monkeypatch) -> None:
    from app.services.mimo_tts import MimoTtsClient

    captured = {}

    class Response:
        def __init__(self, lines) -> None:
            self.lines = lines

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> bool:
            return False

        def __iter__(self):
            return iter(self.lines)

    def sse_line(payload: str) -> bytes:
        return f'data: {payload}\n'.encode()

    chunk1 = base64.b64encode(b'chunk-1').decode()
    chunk2 = base64.b64encode(b'chunk-2').decode()
    lines = [
        sse_line('{"choices":[{"delta":{"audio":{"data":"' + chunk1 + '"}}}]}'),
        sse_line('{"choices":[{"delta":{"audio":{"data":"' + chunk2 + '"}}}]}'),
        b'data: [DONE]\n',
    ]

    def fake_urlopen(request, timeout):
        captured['payload'] = request.data
        return Response(lines)

    monkeypatch.setattr('app.services.mimo_tts.urlopen', fake_urlopen)

    chunks = list(MimoTtsClient('test-key', 'https://api.example/v1', 'mimo-v2.5-tts', 'Chloe').stream('I like apples.'))

    assert chunks == [b'chunk-1', b'chunk-2']
    payload = json.loads(captured['payload'])
    assert payload['stream'] is True
    assert payload['audio'] == {'format': 'pcm16', 'voice': 'Chloe'}
