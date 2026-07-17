def test_making_voice_default_unsets_previous_default(session) -> None:
    from app.services.speakers import create_speaker, create_voice_version, get_speaker, make_default

    speaker = create_speaker(session, '爸爸')
    first = create_voice_version(session, speaker.id, '原声', status='ready')
    second = create_voice_version(session, speaker.id, '慢速清晰版', status='ready')

    make_default(session, speaker.id, first.id)
    make_default(session, speaker.id, second.id)

    assert get_speaker(session, speaker.id).default_voice_version_id == second.id


def test_history_referenced_voice_is_disabled_not_deleted(session) -> None:
    from app.models.child import Child
    from app.models.dictation import DictationSession
    from app.models.learning_item import LearningList, LearningListVersion
    from app.services.speakers import create_speaker, create_voice_version, delete_voice_version

    speaker = create_speaker(session, '妈妈')
    voice = create_voice_version(session, speaker.id, '原声', status='ready')
    child = Child(display_name='孩子', slug='speaker-history-child')
    session.add(child)
    session.flush()
    learning_list = LearningList(child_id=child.id, title='历史学习本')
    session.add(learning_list)
    session.flush()
    version = LearningListVersion(word_list_id=learning_list.id, version=1)
    session.add(version)
    session.flush()
    history = DictationSession(
        child_id=child.id, word_list_version_id=version.id, mode='ordered', ordered_item_ids_json='[]',
        voice_version_id=voice.id, voice_version_name_snapshot='原声',
    )
    session.add(history)
    session.commit()

    deleted = delete_voice_version(session, voice.id)

    assert deleted.status == 'disabled'
    assert session.get(type(voice), voice.id) is not None
    assert session.get(DictationSession, history.id).voice_version_name_snapshot == '原声'


def test_learning_item_audio_cache_uses_reference_audio_fingerprint(session) -> None:
    from app.models.learning_item import LearningItem, LearningList, LearningListVersion
    from app.services.speakers import audio_config_fingerprint, cache_learning_item_audio

    child = __import__('app.models.child', fromlist=['Child']).Child(display_name='孩子', slug='audio-cache-child')
    session.add(child)
    session.flush()
    learning_list = LearningList(child_id=child.id, title='声音学习本')
    session.add(learning_list)
    session.flush()
    version = LearningListVersion(word_list_id=learning_list.id, version=1)
    session.add(version)
    session.flush()
    item = LearningItem(word_list_version_id=version.id, position=0, display_text='apple', normalized_text='apple')
    session.add(item)
    session.commit()

    first = audio_config_fingerprint('mimo', 'model', 'https://tts.example/v1', 'voice', 1.0, 'a' * 64)
    second = audio_config_fingerprint('mimo', 'model', 'https://tts.example/v1', 'voice', 1.0, 'b' * 64)
    one = cache_learning_item_audio(session, item.id, first, 'asset-1')
    duplicate = cache_learning_item_audio(session, item.id, first, 'asset-2')
    changed_voice = cache_learning_item_audio(session, item.id, second, 'asset-3')

    assert first != second
    assert one.id == duplicate.id
    assert changed_voice.id != one.id
