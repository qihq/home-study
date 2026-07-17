from datetime import datetime, timezone


def test_dictation_trend_aggregates_items_not_session_percentages(session) -> None:
    from app.models.child import Child
    from app.models.dictation import DictationResult, DictationSession
    from app.models.word_list import WordItem, WordList, WordListVersion
    from app.services.dictation_stats import build_dictation_stats

    child = Child(display_name='孩子', slug='stats-child')
    session.add(child); session.flush()
    word_list = WordList(child_id=child.id, title='test', status='confirmed', current_version=1)
    session.add(word_list); session.flush()
    version = WordListVersion(word_list_id=word_list.id, version=1)
    session.add(version); session.flush()
    item = WordItem(word_list_version_id=version.id, position=0, display_text='apple', normalized_text='apple')
    session.add(item); session.flush()
    one = DictationSession(child_id=child.id, word_list_version_id=version.id, mode='ordered', ordered_item_ids_json='[]')
    two = DictationSession(child_id=child.id, word_list_version_id=version.id, mode='ordered', ordered_item_ids_json='[]')
    session.add_all([one, two]); session.flush()
    now = datetime(2026, 7, 1, tzinfo=timezone.utc)
    session.add_all([*(DictationResult(session_id=one.id, word_item_id=item.id, sequence=index, result='correct', scored_at=now) for index in range(9)), DictationResult(session_id=one.id, word_item_id=item.id, sequence=9, result='incorrect', scored_at=now), DictationResult(session_id=two.id, word_item_id=item.id, sequence=0, result='incorrect', scored_at=now)])
    session.commit()

    stats = build_dictation_stats(session, child.id)

    assert stats['daily'][0]['accuracy'] == 9 / 11
    assert stats['word_accuracy'] == 9 / 11
    assert stats['phrase_accuracy'] is None
    assert stats['sentence_accuracy'] is None


def test_mistakes_group_by_normalized_word_and_keep_error_count(session) -> None:
    from app.models.child import Child
    from app.models.dictation import DictationResult, DictationSession
    from app.models.word_list import WordItem, WordList, WordListVersion
    from app.services.dictation_stats import build_mistakes

    child = Child(display_name='孩子', slug='mistakes-child'); session.add(child); session.flush()
    word_list = WordList(child_id=child.id, title='test', status='confirmed', current_version=1); session.add(word_list); session.flush()
    version = WordListVersion(word_list_id=word_list.id, version=1); session.add(version); session.flush()
    item = WordItem(word_list_version_id=version.id, position=0, display_text='Apple', normalized_text='apple'); session.add(item); session.flush()
    record = DictationSession(child_id=child.id, word_list_version_id=version.id, mode='ordered', ordered_item_ids_json='[]'); session.add(record); session.flush()
    now = datetime.now(timezone.utc)
    session.add_all([DictationResult(session_id=record.id, word_item_id=item.id, sequence=0, result='incorrect', scored_at=now), DictationResult(session_id=record.id, word_item_id=item.id, sequence=1, result='incorrect', scored_at=now)])
    session.commit()

    mistakes = build_mistakes(session, child.id)

    assert mistakes == [{'word': 'Apple', 'normalized_text': 'apple', 'incorrect_count': 2, 'correct_count': 0}]
