import base64


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
    assert b'Read exactly the assistant text once' in captured['payload']
    assert b'"role":"assistant","content":"apple"' in captured['payload']
