import json

import pytest


def _mp3(inner: bytes = b'fake') -> bytes:
    return b'ID3' + b'\x00' * 60 + inner


def _ogg(inner: bytes = b'fake') -> bytes:
    return b'OggS' + b'\x00' * 60 + inner


class _FakeHeaders:
    def __init__(self, content_type: str) -> None:
        self.content_type = content_type

    def get_content_type(self) -> str:
        return self.content_type


class _FakeResponse:
    def __init__(self, data: bytes, content_type: str = 'audio/mpeg') -> None:
        self.data = data
        self.headers = _FakeHeaders(content_type)

    def read(self):
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> bool:
        return False


def _install_settings(monkeypatch, tmp_path) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv('APP_DATA_DIR', str(tmp_path / 'data'))
    get_settings.cache_clear()


def _wiktionary_html(audio_paths: list[str]) -> bytes:
    audio_tags = ''.join(f'<audio src="{path}"></audio>' for path in audio_paths)
    return (
        '<html><h2><span class="mw-headline" id="English">English</span></h2>'
        '<h3><span id="Pronunciation">Pronunciation</span></h3>' + audio_tags +
        '<h2><span class="mw-headline" id="German">German</span></h2>'
        '<audio src="//upload.wikimedia.org/wikipedia/commons/0/00/De-fremd.ogg"></audio>'
        '</html>'
    ).encode()


def _free_dictionary_payload(word: str, audios: list[str]) -> bytes:
    return json.dumps([{'word': word, 'phonetics': [{'text': '/x/', 'audio': url} for url in audios]}]).encode()


def test_fetch_word_audio_prefers_human_recordings_for_english_and_caches_file(monkeypatch, tmp_path) -> None:
    from app.services import dictionary_audio as module

    _install_settings(monkeypatch, tmp_path)
    module._MISS_CACHE.clear()
    calls = []
    transcoded = 'https://upload.wikimedia.org/wikipedia/commons/transcoded/9/9a/En-us-apple.ogg/En-us-apple.ogg.mp3'

    def fake_urlopen(request, timeout):
        url = request.full_url
        calls.append(url)
        if url == 'https://en.wiktionary.org/wiki/apple':
            return _FakeResponse(_wiktionary_html([
                '//upload.wikimedia.org/wikipedia/commons/9/9a/En-uk-apple.ogg',
                transcoded.removeprefix('https:'),
            ]))
        if url == transcoded:
            return _FakeResponse(_mp3(b'human'))
        raise AssertionError(f'unexpected url {url}')

    monkeypatch.setattr(module, 'urlopen', fake_urlopen)

    path, source = module.fetch_word_audio('apple', 'en', 'us')

    assert source == 'wiktionary'
    assert path.is_file() and path.suffix == '.mp3'
    assert path.read_bytes() == _mp3(b'human')
    assert calls == ['https://en.wiktionary.org/wiki/apple', transcoded]
    # second call reuses the cached file without any network request
    path2, source2 = module.fetch_word_audio('apple', 'en', 'us')
    assert (path2, source2) == (path, 'cached')
    assert len(calls) == 2


def test_fetch_word_audio_falls_back_to_dictvoice_and_remembers_misses(monkeypatch, tmp_path) -> None:
    from app.services import dictionary_audio as module

    _install_settings(monkeypatch, tmp_path)
    module._MISS_CACHE.clear()
    calls = []

    def fake_urlopen(request, timeout):
        url = request.full_url
        calls.append(url)
        if 'wiktionary.org' in url or 'dictionaryapi.dev' in url:
            raise OSError('network down')
        if 'dictvoice' in url:
            return _FakeResponse(_mp3(b'dictvoice'))
        raise AssertionError(f'unexpected url {url}')

    monkeypatch.setattr(module, 'urlopen', fake_urlopen)

    path, source = module.fetch_word_audio('apple', 'en', 'us')

    assert source == 'dictvoice'
    assert path.read_bytes() == _mp3(b'dictvoice')
    assert module._miss_fresh('wiktionary', 'apple', 'us')
    assert module._miss_fresh('dictionaryapi.dev', 'apple', 'us')

    # regenerate bypasses both caches and retries the human source
    def fake_urlopen_retry(request, timeout):
        url = request.full_url
        calls.append(url)
        if url == 'https://en.wiktionary.org/wiki/apple':
            return _FakeResponse(_wiktionary_html(['//upload.wikimedia.org/wikipedia/commons/9/9a/En-us-apple.ogg']))
        if url == 'https://upload.wikimedia.org/wikipedia/commons/9/9a/En-us-apple.ogg':
            return _FakeResponse(_mp3(b'human'))
        raise AssertionError(f'unexpected url {url}')

    monkeypatch.setattr(module, 'urlopen', fake_urlopen_retry)

    path2, source2 = module.fetch_word_audio('apple', 'en', 'us', refresh=True)

    assert source2 == 'wiktionary'
    assert path2.read_bytes() == _mp3(b'human')


def test_fetch_word_audio_reads_chinese_words_and_rejects_non_words(monkeypatch, tmp_path) -> None:
    from app.services import dictionary_audio as module

    _install_settings(monkeypatch, tmp_path)
    module._MISS_CACHE.clear()
    calls = []

    def fake_request(url, timeout, **_kwargs):
        calls.append(url)
        return _mp3(b'x')

    monkeypatch.setattr(module, '_request', fake_request)

    with pytest.raises(module.DictionaryAudioError):
        module.fetch_word_audio('two words', 'en', 'us')
    with pytest.raises(module.DictionaryAudioError):
        module.fetch_word_audio('I like apples', 'en', 'us')

    path, source = module.fetch_word_audio('苹果', 'zh', 'us')
    assert source == 'dictvoice'
    assert path.is_file()
    # Chinese words never probe the English-only sources
    assert all('dictvoice' in url for url in calls)


def test_fetch_word_audio_raises_when_all_sources_fail(monkeypatch, tmp_path) -> None:
    from app.services import dictionary_audio as module

    _install_settings(monkeypatch, tmp_path)
    module._MISS_CACHE.clear()

    def failing(request, timeout):
        raise OSError('network down')

    monkeypatch.setattr(module, 'urlopen', failing)
    with pytest.raises(module.DictionaryAudioError):
        module.fetch_word_audio('apple', 'en', 'us')


def test_pick_audio_url_prefers_accent_then_english_then_primary_reading_then_mp3() -> None:
    from app.services.dictionary_audio import _pick_audio_url

    assert _pick_audio_url(
        ['https://x/apple-uk.mp3', 'https://x/apple-us.mp3'], 'us',
    ) == 'https://x/apple-us.mp3'
    # a primary-reading ogg beats a secondary mp3 of the same accent
    assert _pick_audio_url(
        ['https://x/read-1-us.ogg', 'https://x/read-2-us.mp3'], 'us',
    ) == 'https://x/read-1-us.ogg'
    # mp3 breaks ties between readings of equal rank
    assert _pick_audio_url(
        ['https://x/read-1-us.ogg', 'https://x/read-1-us.mp3'], 'us',
    ) == 'https://x/read-1-us.mp3'
    # Wikimedia pre-transcoded mp3 outranks the original ogg
    assert _pick_audio_url(
        [
            'https://upload.wikimedia.org/wikipedia/commons/9/9a/En-us-apple.ogg',
            'https://upload.wikimedia.org/wikipedia/commons/transcoded/9/9a/En-us-apple.ogg/En-us-apple.ogg.mp3',
        ],
        'us', wikimedia=True,
    ) == 'https://upload.wikimedia.org/wikipedia/commons/transcoded/9/9a/En-us-apple.ogg/En-us-apple.ogg.mp3'
    # an English recording beats a foreign one; word-internal "-us" is not an accent marker
    assert _pick_audio_url(
        [
            'https://upload.wikimedia.org/wikipedia/commons/0/00/fr-bonus.ogg',
            'https://upload.wikimedia.org/wikipedia/commons/9/9a/En-uk-apple.ogg',
        ],
        'us', wikimedia=True,
    ) == 'https://upload.wikimedia.org/wikipedia/commons/9/9a/En-uk-apple.ogg'
    # no accent match: still returns a human recording rather than nothing
    assert _pick_audio_url(['https://x/schedule-au.mp3'], 'us') == 'https://x/schedule-au.mp3'
    assert _pick_audio_url([], 'us') is None


def test_fetch_word_audio_saves_ogg_and_uses_transcode_when_available(monkeypatch, tmp_path) -> None:
    from app.services import dictionary_audio as module

    _install_settings(monkeypatch, tmp_path)
    module._MISS_CACHE.clear()

    def fake_urlopen(request, timeout):
        url = request.full_url
        if url == 'https://en.wiktionary.org/wiki/read':
            return _FakeResponse(_wiktionary_html(['//upload.wikimedia.org/wikipedia/commons/5/50/En-us-read.ogg']))
        if url == 'https://upload.wikimedia.org/wikipedia/commons/5/50/En-us-read.ogg':
            return _FakeResponse(_ogg(b'vorbis'), content_type='audio/ogg')
        raise AssertionError(f'unexpected url {url}')

    monkeypatch.setattr(module, 'urlopen', fake_urlopen)

    # no ffmpeg path: keep the ogg file with a truthful extension
    monkeypatch.setattr(module, '_transcode_to_mp3', lambda data: None)
    path, source = module.fetch_word_audio('read', 'en', 'us')
    assert source == 'wiktionary'
    assert path.suffix == '.ogg'
    assert path.read_bytes() == _ogg(b'vorbis')

    # ffmpeg path: transcoded bytes are stored as mp3
    def fake_urlopen_water(request, timeout):
        url = request.full_url
        if url == 'https://en.wiktionary.org/wiki/water':
            return _FakeResponse(_wiktionary_html(['//upload.wikimedia.org/wikipedia/commons/9/9a/En-us-water.ogg']))
        if url == 'https://upload.wikimedia.org/wikipedia/commons/9/9a/En-us-water.ogg':
            return _FakeResponse(_ogg(b'vorbis'), content_type='audio/ogg')
        raise AssertionError(f'unexpected url {url}')

    monkeypatch.setattr(module, 'urlopen', fake_urlopen_water)
    monkeypatch.setattr(module, '_transcode_to_mp3', lambda data: _mp3(b'transcoded'))

    path2, source2 = module.fetch_word_audio('water', 'en', 'us')
    assert source2 == 'wiktionary'
    assert path2.suffix == '.mp3'
    assert path2.read_bytes() == _mp3(b'transcoded')


def test_ensure_word_audio_asset_creates_and_reuses(session, monkeypatch, tmp_path) -> None:
    from app.models.tts_asset import TtsAsset
    from app.services import dictionary_audio as module

    path = tmp_path / 'apple.mp3'
    path.write_bytes(_mp3())
    monkeypatch.setattr(module, 'fetch_word_audio', lambda *_args, **_kwargs: (path, 'wiktionary'))

    first = module.ensure_word_audio_asset(session, 'apple', 'en', owner_user_id='user-1')
    second = module.ensure_word_audio_asset(session, 'apple', 'en', owner_user_id='user-1')

    assert first is not None and first.id == second.id
    assert first.provider == 'dictionary_audio'
    assert first.model == 'wiktionary'
    assert first.voice == 'us'
    assert first.locale == 'en-US'
    assert first.owner_user_id == 'user-1'
    assert session.query(TtsAsset).filter_by(provider='dictionary_audio').count() == 1


def test_ensure_word_audio_asset_returns_none_on_failure_and_non_words(session, monkeypatch) -> None:
    from app.models.tts_asset import TtsAsset
    from app.services import dictionary_audio as module
    from app.services.dictionary_audio import DictionaryAudioError

    def fail(*_args, **_kwargs):
        raise DictionaryAudioError('DICTIONARY_AUDIO_NOT_FOUND')

    monkeypatch.setattr(module, 'fetch_word_audio', fail)

    assert module.ensure_word_audio_asset(session, 'apple', 'en') is None
    assert module.ensure_word_audio_asset(session, 'two words', 'en') is None
    assert session.query(TtsAsset).count() == 0


def test_circuit_breaker_skips_failing_sources_until_refresh(monkeypatch, tmp_path) -> None:
    from app.services import dictionary_audio as module

    _install_settings(monkeypatch, tmp_path)
    module._MISS_CACHE.clear()
    module._BREAKER_UNTIL.clear()
    module._FAILURE_TIMES.clear()
    module._BREAKER_STATE_LOADED = False
    calls = []

    def failing(request, timeout):
        calls.append(request.full_url)
        raise OSError('network down')

    monkeypatch.setattr(module, 'urlopen', failing)

    for word in ('apple', 'pear', 'plum'):
        with pytest.raises(module.DictionaryAudioError):
            module.fetch_word_audio(word, 'en', 'us')

    # apple: 4 sources tried (dictvoice/baidu retried once each = 2 calls);
    # pear: 4 more (breakers open on 2nd failure); plum: all breakers open,
    # nothing is fetched anymore.
    assert len(calls) == 12
    assert module._breaker_open('wiktionary')
    assert module._breaker_open('dictionaryapi.dev')
    assert module._breaker_open('dictvoice')
    assert module._breaker_open('baidu')

    # breaker state is persisted so a restart keeps skipping the dead sources
    from app.core.config import get_settings
    state_file = get_settings().tts_dir / 'dictionary-audio-breaker.json'
    assert state_file.is_file()

    # an explicit refresh bypasses the breaker and retries for real
    with pytest.raises(module.DictionaryAudioError):
        module.fetch_word_audio('plum', 'en', 'us', refresh=True)
    assert len(calls) == 18


def test_breaker_state_is_loaded_from_disk_after_restart(monkeypatch, tmp_path) -> None:
    import json
    import time
    from app.core.config import get_settings
    from app.services import dictionary_audio as module

    _install_settings(monkeypatch, tmp_path)
    module._MISS_CACHE.clear()
    module._BREAKER_UNTIL.clear()
    module._FAILURE_TIMES.clear()
    module._BREAKER_STATE_LOADED = False
    state_file = get_settings().tts_dir / 'dictionary-audio-breaker.json'
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps({
        'wiktionary': {'open_until': time.time() + 3600, 'failure_count': 2},
    }))

    assert module._breaker_open('wiktionary') is True
    assert module._breaker_open('dictvoice') is False


def test_chinese_words_fall_back_to_baidu_when_youdao_fails(monkeypatch, tmp_path) -> None:
    from app.services import dictionary_audio as module

    _install_settings(monkeypatch, tmp_path)
    module._MISS_CACHE.clear()
    module._BREAKER_UNTIL.clear()
    module._FAILURE_TIMES.clear()
    calls = []

    def fake_urlopen(request, timeout):
        url = request.full_url
        calls.append(url)
        if 'dictvoice' in url:
            raise OSError('HTTP 500')
        if 'fanyi.baidu.com' in url:
            return _FakeResponse(_mp3(b'baidu'))
        raise AssertionError(f'unexpected url {url}')

    monkeypatch.setattr(module, 'urlopen', fake_urlopen)

    path, source = module.fetch_word_audio('地球', 'zh', 'us')

    assert source == 'baidu'
    assert path.read_bytes() == _mp3(b'baidu')
    assert any('fanyi.baidu.com' in url for url in calls)


def test_dictvoice_transient_failure_is_retried_before_falling_back(monkeypatch, tmp_path) -> None:
    from app.services import dictionary_audio as module

    _install_settings(monkeypatch, tmp_path)
    module._MISS_CACHE.clear()
    module._BREAKER_UNTIL.clear()
    module._FAILURE_TIMES.clear()
    calls = []

    def flaky(request, timeout):
        url = request.full_url
        calls.append(url)
        if 'dictvoice' in url and len([c for c in calls if 'dictvoice' in c]) == 1:
            raise OSError('transient 500')
        if 'dictvoice' in url:
            return _FakeResponse(_mp3(b'youdao-retry'))
        raise AssertionError(f'unexpected url {url}')

    monkeypatch.setattr(module, 'urlopen', flaky)

    path, source = module.fetch_word_audio('海洋', 'zh', 'us')

    assert source == 'dictvoice'
    assert path.read_bytes() == _mp3(b'youdao-retry')
    assert sum('dictvoice' in url for url in calls) == 2


def test_prefetch_word_audio_fills_both_accents_and_never_raises(monkeypatch, tmp_path) -> None:
    from app.services import dictionary_audio as module

    _install_settings(monkeypatch, tmp_path)
    module._MISS_CACHE.clear()
    module._BREAKER_UNTIL.clear()
    module._FAILURE_TIMES.clear()
    calls = []

    def fake_urlopen(request, timeout):
        url = request.full_url
        calls.append(url)
        if url == 'https://en.wiktionary.org/wiki/apple':
            return _FakeResponse(_wiktionary_html([
                '//upload.wikimedia.org/wikipedia/commons/9/9a/En-us-apple.ogg',
                '//upload.wikimedia.org/wikipedia/commons/c/c8/En-uk-apple.ogg',
            ]))
        if url.endswith('En-us-apple.ogg'):
            return _FakeResponse(_mp3(b'us'))
        if url.endswith('En-uk-apple.ogg'):
            return _FakeResponse(_mp3(b'uk'))
        raise AssertionError(f'unexpected url {url}')

    monkeypatch.setattr(module, 'urlopen', fake_urlopen)

    assert module.prefetch_word_audio('apple', 'en') == {'us': 'wiktionary', 'uk': 'wiktionary'}

    # the play path now hits the disk cache with zero network requests
    before = len(calls)
    path, source = module.fetch_word_audio('apple', 'en', 'us')
    assert (source, len(calls)) == ('cached', before)
    assert path.read_bytes() == _mp3(b'us')

    # failures stay silent and leave the cache untouched
    monkeypatch.setattr(module, 'urlopen', lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError('down')))
    assert module.prefetch_word_audio('pear', 'en') == {}
