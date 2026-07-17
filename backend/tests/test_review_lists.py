def test_review_list_creation_copies_mistakes_without_mutating_history(session) -> None:
    from app.models.child import Child
    from app.models.dictation import DictationResult, DictationSession
    from app.models.word_list import WordItem, WordList, WordListVersion
    from app.services.dictation_stats import create_review_list

    child = Child(display_name='孩子', slug='review-child'); session.add(child); session.flush()
    original = WordList(child_id=child.id, title='第一周', status='confirmed', current_version=1); session.add(original); session.flush()
    version = WordListVersion(word_list_id=original.id, version=1); session.add(version); session.flush()
    item = WordItem(word_list_version_id=version.id, position=0, display_text='Apple', normalized_text='apple'); session.add(item); session.flush()
    dictation = DictationSession(child_id=child.id, word_list_version_id=version.id, mode='ordered', ordered_item_ids_json='[]'); session.add(dictation); session.flush()
    session.add(DictationResult(session_id=dictation.id, word_item_id=item.id, sequence=0, result='incorrect'))
    session.commit()

    review = create_review_list(session, child.id, ['apple'])

    assert review.status == 'draft'
    assert review.title == '错词复习'
    assert original.status == 'confirmed'
