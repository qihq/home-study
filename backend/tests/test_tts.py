def test_same_tts_request_reuses_cached_asset(session) -> None:
    from app.services.tts import ensure_tts_asset

    calls: list[str] = []
    def fake_synthesize(text: str) -> bytes:
        calls.append(text)
        return b'fake-mp3'

    first = ensure_tts_asset(session, fake_synthesize, text='apple', locale='en-US', voice='amy', speed=1.0)
    second = ensure_tts_asset(session, fake_synthesize, text='apple', locale='en-US', voice='amy', speed=1.0)

    assert first.id == second.id
    assert calls == ['apple']
