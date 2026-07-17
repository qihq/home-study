def test_pasted_text_preserves_display_text_but_normalizes_for_dedupe() -> None:
    from app.services.words import parse_pasted_words

    items = parse_pasted_words('  Apple\napple\nnice-to-meet you ')

    assert [item['display_text'] for item in items] == ['Apple', 'nice-to-meet you']
    assert [item['normalized_text'] for item in items] == ['apple', 'nice-to-meet you']


def test_confirming_list_creates_immutable_version(session) -> None:
    from app.models.child import Child
    from app.services.words import create_draft_word_list, confirm_word_list

    child = Child(display_name='孩子', slug='words-child')
    session.add(child); session.commit()
    word_list = create_draft_word_list(session, child.id, '第 1 周', [{'display_text': 'colour', 'normalized_text': 'colour'}])

    version = confirm_word_list(session, word_list.id)

    assert version.version == 1
    assert word_list.status == 'confirmed'
