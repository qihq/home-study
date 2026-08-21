import json
from datetime import datetime, timedelta, timezone

import pytest


def _fake_get_json(responses: dict[str, object]):
    def fake(url: str, timeout: float):
        for prefix, payload in responses.items():
            if url.startswith(prefix):
                if isinstance(payload, Exception):
                    raise payload
                return payload
        raise AssertionError(f'unexpected url {url}')
    return fake


YOUDAO = {
    'ec': {'word': [{
        'usphone': "'æpl", 'ukphone': "'æpl",
        'trs': [{'tr': [{'pos': 'n', 'l': {'i': ['苹果', '苹果树']}}, {'pos': '', 'l': {'i': ['adj. 苹果的']}}]}],
    }]},
}

DICTAPI = [{
    'word': 'apple', 'phonetic': '/ˈæp.əl/',
    'phonetics': [
        {'text': '/ˈæp.əl/', 'audio': 'https://example.com/apple-uk.mp3'},
        {'text': '/ˈæp.əl/', 'audio': 'https://example.com/apple-us.mp3'},
    ],
    'meanings': [
        {'partOfSpeech': 'noun', 'definitions': [
            {'definition': 'a round fruit with red or green skin', 'example': 'She ate an apple.'},
            {'definition': 'the tree bearing apples', 'example': ''},
        ]},
        {'partOfSpeech': 'verb', 'definitions': [{'definition': 'to make apple-like', 'example': ''}]},
    ],
}]


def test_online_lookup_combines_youdao_translations_with_free_dictionary_details(monkeypatch) -> None:
    from app.services import online_dictionary as module

    monkeypatch.setattr(module, '_get_json', _fake_get_json({
        'https://dict.youdao.com': YOUDAO,
        'https://api.dictionaryapi.dev': DICTAPI,
    }))

    result = module.lookup_english_word('apple')

    assert result.source_language == 'en' and result.target_language == 'zh'
    assert result.item_type == 'word'
    assert result.primary_translation == '苹果'
    assert result.phonetic == '/ˈæp.əl/'
    assert result.phonetic_uk == '/ˈæp.əl/' and result.phonetic_us == '/ˈæp.əl/'
    assert [(part.part, part.meaning) for part in result.parts_of_speech[:2]] == [
        ('n.', '苹果'), ('n.', '苹果树'),
    ]
    assert ('adj.', '苹果的') in [(part.part, part.meaning) for part in result.parts_of_speech]
    assert result.examples[0].source == 'She ate an apple.'
    assert 'a round fruit with red or green skin' in (result.usage_note or '')
    assert result.result_source == 'youdao'


def test_online_lookup_uses_free_dictionary_alone(monkeypatch) -> None:
    from app.services import online_dictionary as module

    monkeypatch.setattr(module, '_get_json', _fake_get_json({
        'https://dict.youdao.com': json.loads('{"ec": {"word": []}}'),
        'https://api.dictionaryapi.dev': DICTAPI,
    }))

    result = module.lookup_english_word('apple')

    assert result.primary_translation == 'a round fruit with red or green skin'
    assert result.result_source == 'dictionaryapi'
    assert result.phonetic_us == '/ˈæp.əl/'


def test_online_lookup_raises_when_every_source_fails(monkeypatch) -> None:
    from app.services import online_dictionary as module
    from app.services.online_dictionary import OnlineDictionaryError

    monkeypatch.setattr(module, '_get_json', _fake_get_json({
        'https://dict.youdao.com': OnlineDictionaryError('offline'),
        'https://api.dictionaryapi.dev': OnlineDictionaryError('offline'),
    }))

    with pytest.raises(OnlineDictionaryError):
        module.lookup_english_word('apple')


def test_online_lookup_is_cached_for_ttl_and_refetches_when_stale(session, monkeypatch) -> None:
    from app.models.child import Child
    from app.models.dictionary import DictionaryEntry
    from app.services import online_dictionary as module

    child = Child(display_name='孩子', slug='online-child')
    session.add(child); session.commit()
    fetched = 0

    def fake_lookup(text: str, timeout: float = 10):
        nonlocal fetched
        fetched += 1
        from app.schemas.dictionary import DictionaryResult
        return DictionaryResult(
            source_language='en', target_language='zh', item_type='word', source_text=text,
            primary_translation=f'苹果（第{fetched}版）', phonetic=None, parts_of_speech=[],
            alternatives=[], examples=[], usage_note=None,
            result_source='youdao', source_attribution='在线词典 · 有道（公开接口）',
        )

    monkeypatch.setattr(module, 'lookup_english_word', fake_lookup)

    first = module.lookup_online_word(session, child.id, 'apple', 'user-1')
    second = module.lookup_online_word(session, child.id, 'apple', 'user-1')

    assert first is not None and first.cache_hit is False
    assert second is not None and second.cache_hit is True
    assert second.entry_id == first.entry_id
    assert fetched == 1

    entry = session.get(DictionaryEntry, first.entry_id)
    entry.created_at = datetime.now(timezone.utc) - timedelta(days=31)
    session.commit()

    refreshed = module.lookup_online_word(session, child.id, 'apple', 'user-1')

    assert refreshed is not None and refreshed.cache_hit is False
    assert refreshed.entry_id == first.entry_id
    assert '第2版' in refreshed.result.primary_translation
    assert fetched == 2


def test_online_lookup_returns_none_when_sources_fail(session, monkeypatch) -> None:
    from app.models.child import Child
    from app.services import online_dictionary as module
    from app.services.online_dictionary import OnlineDictionaryError

    child = Child(display_name='孩子', slug='online-none')
    session.add(child); session.commit()
    monkeypatch.setattr(module, 'lookup_english_word', lambda *_args, **_kwargs: (_ for _ in ()).throw(OnlineDictionaryError('ONLINE_DICTIONARY_NOT_FOUND')))

    assert module.lookup_online_word(session, child.id, 'apple', 'user-1') is None
