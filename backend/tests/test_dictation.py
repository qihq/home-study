import random


def test_random_session_order_is_persisted(session) -> None:
    from app.models.child import Child
    from app.models.word_list import WordItem, WordList, WordListVersion
    from app.services.dictation import start_dictation

    child = Child(display_name='孩子', slug='dictation-child')
    session.add(child); session.flush()
    word_list = WordList(child_id=child.id, title='test', status='confirmed', current_version=1)
    session.add(word_list); session.flush()
    version = WordListVersion(word_list_id=word_list.id, version=1)
    session.add(version); session.flush()
    for index, word in enumerate(['apple', 'banana', 'cherry']):
        session.add(WordItem(word_list_version_id=version.id, position=index, display_text=word, normalized_text=word))
    session.commit()

    result = start_dictation(session, child.id, version.id, 'random', random.Random(2))

    assert len(result.ordered_item_ids) == 3
    assert len(set(result.ordered_item_ids)) == 3
    assert result.ordered_item_ids != [item.id for item in session.query(WordItem).order_by(WordItem.position)]


def test_scoring_updates_existing_result(session) -> None:
    from app.models.child import Child
    from app.models.word_list import WordItem, WordList, WordListVersion
    from app.services.dictation import score_result, start_dictation

    child = Child(display_name='孩子', slug='score-child'); session.add(child); session.flush()
    word_list = WordList(child_id=child.id, title='test', status='confirmed', current_version=1); session.add(word_list); session.flush()
    version = WordListVersion(word_list_id=word_list.id, version=1); session.add(version); session.flush()
    item = WordItem(word_list_version_id=version.id, position=0, display_text='apple', normalized_text='apple'); session.add(item); session.commit()
    dictation = start_dictation(session, child.id, version.id, 'ordered', random.Random(1))

    scored = score_result(session, dictation.id, dictation.results[0].id, 'incorrect')

    assert scored.result == 'incorrect'
