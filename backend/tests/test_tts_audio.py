from pathlib import Path


def test_tts_audio_is_not_public(client, admin_user, tmp_path: Path) -> None:
    from app.db.session import get_session_factory
    from app.models.tts_asset import TtsAsset

    with get_session_factory()() as session:
        audio = tmp_path / 'word.wav'; audio.write_bytes(b'wav')
        asset = TtsAsset(cache_key='x', voice='Chloe', locale='en-US', speed=1.0, normalized_text='apple', path=str(audio))
        session.add(asset); session.commit(); asset_id = asset.id

    assert client.get(f'/api/tts-assets/{asset_id}/audio').status_code == 401
