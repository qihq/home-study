def test_confirmed_list_preserves_word_and_sentence_types(session) -> None:
    from app.models.child import Child
    from app.services.learning_items import confirm_learning_list, create_learning_list

    child = Child(display_name='孩子', slug='learning-list-child')
    session.add(child)
    session.commit()

    draft = create_learning_list(session, child.id, 'Week 1', [
        {'display_text': 'apple', 'item_type': 'word', 'source_language': 'en', 'target_language': 'zh'},
        {'display_text': 'I like apples.', 'item_type': 'sentence', 'source_language': 'en', 'target_language': 'zh'},
    ])

    version = confirm_learning_list(session, draft.id)

    assert [item.item_type for item in version.items] == ['word', 'sentence']
