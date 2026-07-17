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

    learning_list = create_learning_list_from_unknown_items(session, child.id, [word.id, sentence.id])
    version = confirm_learning_list(session, learning_list.id)

    assert [(item.item_type, item.translation_text) for item in version.items] == [
        ('word', '苹果'), ('sentence', '我喜欢苹果。'),
    ]
    assert [session.get(type(word), item_id).status for item_id in (word.id, sentence.id)] == ['unknown', 'unknown']


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
