from datetime import date, datetime, timezone


def test_dictation_stats_aggregate_scored_items_across_sessions_and_include_type_accuracies(session) -> None:
    from app.models.child import Child
    from app.models.dictation import DictationResult, DictationSession
    from app.models.word_list import WordItem, WordList, WordListVersion
    from app.services.dictation_stats import build_dictation_stats

    child = Child(display_name='Child', slug='extended-dictation-stats')
    session.add(child)
    session.flush()
    word_list = WordList(child_id=child.id, title='Mixed list', status='confirmed', current_version=1)
    session.add(word_list)
    session.flush()
    version = WordListVersion(word_list_id=word_list.id, version=1)
    session.add(version)
    session.flush()
    word = WordItem(word_list_version_id=version.id, position=0, item_type='word', display_text='apple', normalized_text='apple')
    phrase = WordItem(word_list_version_id=version.id, position=1, item_type='phrase', display_text='red apple', normalized_text='red apple')
    sentence = WordItem(word_list_version_id=version.id, position=2, item_type='sentence', display_text='I eat apples.', normalized_text='i eat apples.')
    session.add_all([word, phrase, sentence])
    session.flush()
    first_session = DictationSession(child_id=child.id, word_list_version_id=version.id, mode='ordered', ordered_item_ids_json='[]')
    second_session = DictationSession(child_id=child.id, word_list_version_id=version.id, mode='ordered', ordered_item_ids_json='[]')
    session.add_all([first_session, second_session])
    session.flush()
    scored_at = datetime(2026, 7, 14, tzinfo=timezone.utc)
    session.add_all([
        *(DictationResult(session_id=first_session.id, word_item_id=word.id, sequence=index, result='correct', scored_at=scored_at, item_type_snapshot='word') for index in range(9)),
        DictationResult(session_id=first_session.id, word_item_id=phrase.id, sequence=9, result='correct', scored_at=scored_at, item_type_snapshot='phrase'),
        DictationResult(session_id=second_session.id, word_item_id=word.id, sequence=0, result='incorrect', scored_at=scored_at, item_type_snapshot='word'),
        DictationResult(session_id=second_session.id, word_item_id=sentence.id, sequence=1, result='incorrect', scored_at=scored_at, item_type_snapshot='sentence'),
    ])
    session.commit()

    stats = build_dictation_stats(session, child.id)

    # 10/12 scored items, rather than the 50% average of the two sessions.
    assert stats['accuracy'] == 10 / 12
    assert stats['word_accuracy'] == 9 / 10
    assert stats['phrase_accuracy'] == 1
    assert stats['sentence_accuracy'] == 0


def test_dictation_stats_report_unknown_items_added_and_mastered_this_week(session) -> None:
    from app.models.child import Child
    from app.models.unknown_item import UnknownItem
    from app.services.dictation_stats import build_dictation_stats

    child = Child(display_name='Child', slug='extended-unknown-stats')
    other_child = Child(display_name='Other child', slug='extended-unknown-stats-other')
    session.add_all([child, other_child])
    session.flush()
    current_week = datetime(2026, 7, 13, tzinfo=timezone.utc)
    previous_week = datetime(2026, 7, 12, tzinfo=timezone.utc)
    session.add_all([
        UnknownItem(child_id=child.id, item_type='word', source_text='new', normalized_text='new', source_language='en', target_language='zh', translation_text='new', marked_at=current_week),
        UnknownItem(child_id=child.id, item_type='word', source_text='new-mastered', normalized_text='new-mastered', source_language='en', target_language='zh', translation_text='new-mastered', status='mastered', marked_at=current_week, mastered_at=current_week),
        UnknownItem(child_id=child.id, item_type='word', source_text='old-mastered', normalized_text='old-mastered', source_language='en', target_language='zh', translation_text='old-mastered', status='mastered', marked_at=previous_week, mastered_at=current_week),
        UnknownItem(child_id=child.id, item_type='word', source_text='old', normalized_text='old', source_language='en', target_language='zh', translation_text='old', marked_at=previous_week),
        UnknownItem(child_id=other_child.id, item_type='word', source_text='other', normalized_text='other', source_language='en', target_language='zh', translation_text='other', status='mastered', marked_at=current_week, mastered_at=current_week),
    ])
    session.commit()

    stats = build_dictation_stats(session, child.id, reference_date=date(2026, 7, 15))

    assert stats['unknown_items'] == {'added_this_week': 2, 'mastered_this_week': 2}


def test_dictation_stats_report_total_dictionary_cache_hits(session) -> None:
    from app.models.child import Child
    from app.models.dictionary import DictionaryEntry
    from app.services.dictation_stats import build_dictation_stats

    child = Child(display_name='Child', slug='extended-cache-stats')
    session.add_all([
        child,
        DictionaryEntry(query_hash='a' * 64, result_json='{}', hit_count=0),
        DictionaryEntry(query_hash='b' * 64, result_json='{}', hit_count=3),
        DictionaryEntry(query_hash='c' * 64, result_json='{}', hit_count=5),
    ])
    session.commit()

    stats = build_dictation_stats(session, child.id)

    assert stats['dictionary_cache_hits'] == 8


def test_dictation_stats_use_the_requested_reference_date_for_weekly_counts(session) -> None:
    from app.models.child import Child
    from app.services.dictation_stats import build_dictation_stats

    child = Child(display_name='Child', slug='stats-reference-date')
    session.add(child)
    session.commit()

    stats = build_dictation_stats(session, child.id, reference_date=date(2026, 7, 15))

    assert stats['unknown_items'] == {'added_this_week': 0, 'mastered_this_week': 0}
