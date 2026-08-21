def test_marking_same_dictionary_entry_unknown_twice_is_idempotent(session) -> None:
    from app.models.child import Child
    from app.models.dictionary import DictionaryEntry
    from app.services.unknown_items import count_active_unknown, mark_unknown, update_unknown_status

    child = Child(display_name='孩子', slug='unknown-child')
    entry = DictionaryEntry(
        query_hash='a' * 64,
        result_json='''{
            "source_language": "en", "target_language": "zh", "item_type": "word",
            "source_text": "apple", "primary_translation": "苹果", "phonetic": null,
            "parts_of_speech": [], "alternatives": [], "examples": [], "usage_note": null
        }''',
    )
    session.add_all([child, entry])
    session.commit()

    first = mark_unknown(session, child.id, entry.id)
    second = mark_unknown(session, child.id, entry.id)
    mastered = update_unknown_status(session, child.id, first.id, 'mastered')
    mastered_status = mastered.status
    restored = update_unknown_status(session, child.id, first.id, 'unknown')

    assert first.id == second.id
    assert count_active_unknown(session, child.id, 'apple') == 1
    assert mastered_status == 'mastered'
    assert restored.status == 'unknown'


def test_unknown_items_create_mixed_learning_list_without_changing_status(session) -> None:
    from app.models.child import Child
    from app.services.learning_items import confirm_learning_list
    from app.services.unknown_items import create_learning_list_from_unknown_items, mark_unknown_text

    child = Child(display_name='孩子', slug='unknown-list-child')
    session.add(child)
    session.commit()
    word = mark_unknown_text(session, child.id, {
        'source_text': 'apple', 'item_type': 'word', 'source_language': 'en',
        'target_language': 'zh', 'translation_text': '苹果',
    })
    sentence = mark_unknown_text(session, child.id, {
        'source_text': 'I like apples.', 'item_type': 'sentence', 'source_language': 'en',
        'target_language': 'zh', 'translation_text': '我喜欢苹果。',
    })

    learning_list = create_learning_list_from_unknown_items(session, child.id, [word.id, sentence.id], '七月生词')
    version = confirm_learning_list(session, learning_list.id)

    assert [(item.item_type, item.translation_text) for item in version.items] == [
        ('word', '苹果'), ('sentence', '我喜欢苹果。'),
    ]
    assert [session.get(type(word), item_id).status for item_id in (word.id, sentence.id)] == ['unknown', 'unknown']
    assert learning_list.title == '七月生词'
    assert learning_list.source_type == 'unknown_items'


def test_unknown_item_can_be_permanently_deleted(session) -> None:
    from app.models.child import Child
    from app.models.unknown_item import UnknownItem
    from app.services.unknown_items import delete_unknown_item, mark_unknown_text

    child = Child(display_name='孩子', slug='delete-unknown-child')
    session.add(child); session.commit()
    item = mark_unknown_text(session, child.id, {
        'source_text': 'apple', 'item_type': 'word', 'source_language': 'en',
        'target_language': 'zh', 'translation_text': '苹果',
    })
    item_id = item.id

    delete_unknown_item(session, child.id, item_id)

    assert session.get(UnknownItem, item_id) is None


def test_unknown_items_sort_by_word_frequency_and_expose_tags(session, monkeypatch, tmp_path) -> None:
    import sqlite3
    from app.core.config import get_settings
    from app.models.child import Child
    from app.services.unknown_items import list_unknown_items, mark_unknown_text

    path = tmp_path / 'local-dictionary.sqlite3'
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE ecdict (word TEXT PRIMARY KEY, phonetic TEXT, translation TEXT, definition TEXT, pos TEXT, collins TEXT, oxford TEXT, tag TEXT, bnc TEXT, frq TEXT);
        CREATE TABLE ecdict_aliases (alias TEXT PRIMARY KEY, word TEXT NOT NULL);
        CREATE TABLE cedict (simplified TEXT, traditional TEXT, pinyin TEXT, definitions TEXT);
        INSERT INTO metadata VALUES ('version', 'unknown-fixture-v1');
        INSERT INTO ecdict VALUES ('apple', NULL, 'n. 苹果', NULL, '', '3', '1', 'zk', '2446', '2695');
        INSERT INTO ecdict VALUES ('quagga', NULL, 'n. 斑驴', NULL, '', '', '', '', '', '89060');
    """)
    connection.commit(); connection.close()
    monkeypatch.setenv('APP_LOCAL_DICTIONARY_PATH', str(path))
    get_settings.cache_clear()

    child = Child(display_name='孩子', slug='sort-child')
    session.add(child); session.commit()
    quagga = mark_unknown_text(session, child.id, {'source_text': 'quagga', 'item_type': 'word', 'source_language': 'en', 'target_language': 'zh', 'translation_text': '斑驴'})
    apple = mark_unknown_text(session, child.id, {'source_text': 'apple', 'item_type': 'word', 'source_language': 'en', 'target_language': 'zh', 'translation_text': '苹果'})
    sentence = mark_unknown_text(session, child.id, {'source_text': 'I like apples.', 'item_type': 'sentence', 'source_language': 'en', 'target_language': 'zh', 'translation_text': '我喜欢苹果。'})
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    quagga.marked_at, apple.marked_at, sentence.marked_at = now - timedelta(days=3), now - timedelta(days=2), now - timedelta(days=1)
    session.commit()

    by_frequency = list_unknown_items(session, child.id, sort='importance')
    by_recent = list_unknown_items(session, child.id, sort='recent')

    assert [item.source_text for item in by_frequency] == ['apple', 'quagga', 'I like apples.']
    assert [item.source_text for item in by_recent] == ['I like apples.', 'apple', 'quagga']


def test_unknown_items_api_exposes_word_tags(client, admin_user, monkeypatch, tmp_path) -> None:
    import sqlite3
    from app.core.config import get_settings
    from app.db.session import get_session_factory
    from app.models.child import Child
    from app.models.unknown_item import UnknownItem

    path = tmp_path / 'local-dictionary.sqlite3'
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE ecdict (word TEXT PRIMARY KEY, phonetic TEXT, translation TEXT, definition TEXT, pos TEXT, collins TEXT, oxford TEXT, tag TEXT, bnc TEXT, frq TEXT);
        CREATE TABLE ecdict_aliases (alias TEXT PRIMARY KEY, word TEXT NOT NULL);
        CREATE TABLE cedict (simplified TEXT, traditional TEXT, pinyin TEXT, definitions TEXT);
        INSERT INTO metadata VALUES ('version', 'unknown-api-v1');
        INSERT INTO ecdict VALUES ('apple', NULL, 'n. 苹果', NULL, '', '3', '1', 'zk gk', '2446', '2695');
    """)
    connection.commit(); connection.close()
    monkeypatch.setenv('APP_LOCAL_DICTIONARY_PATH', str(path))
    get_settings.cache_clear()

    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    with get_session_factory()() as session:
        child = Child(display_name='孩子', slug='api-child', active=True)
        session.add(child); session.flush()
        session.add(UnknownItem(child_id=child.id, item_type='word', source_text='apple', normalized_text='apple', source_language='en', target_language='zh', translation_text='苹果'))
        session.commit()

    response = client.get('/api/unknown-items?sort=importance', headers=headers)

    assert response.status_code == 200
    assert response.json()[0]['source_text'] == 'apple'
    assert response.json()[0]['word_tags'] == ['中考', '高考', '柯林斯3星', '牛津3000']
