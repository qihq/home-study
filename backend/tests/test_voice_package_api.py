def test_voice_package_import_inspect_requires_authentication(client) -> None:
    response = client.post('/api/speaker-profiles/import/inspect')

    assert response.status_code == 401


def test_voice_package_export_is_owner_scoped_and_contains_no_api_key(client, admin_user, tmp_path) -> None:
    from app.db.session import get_session_factory
    from app.models.speaker import SpeakerProfile, VoiceVersion
    from app.models.user import User

    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    audio = tmp_path / 'reference.wav'
    audio.write_bytes(b'normalized-wav')
    with get_session_factory()() as session:
        owner = session.query(User).filter_by(username='parent').one()
        speaker = SpeakerProfile(display_name='妈妈', owner_user_id=owner.id)
        session.add(speaker)
        session.flush()
        voice = VoiceVersion(speaker_profile_id=speaker.id, display_name='清晰美音', status='ready', reference_audio_path=str(audio), reference_sha256=__import__('hashlib').sha256(audio.read_bytes()).hexdigest())
        session.add(voice)
        session.commit()
        speaker_id, voice_id = speaker.id, voice.id

    exported = client.post(f'/api/speaker-profiles/{speaker_id}/export', headers=headers, json={'password': 'correct password', 'voice_version_ids': [voice_id]})

    assert exported.status_code == 200
    assert exported.headers['content-type'] == 'application/octet-stream'
    from app.services.voice_packages import decrypt_voice_package
    assert b'api_key' not in decrypt_voice_package(exported.content, 'correct password')


def test_voice_package_inspect_only_stages_preview_until_explicit_commit(client, admin_user) -> None:
    from app.services.voice_packages import create_voice_package

    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    package = create_voice_package(
        {
            'format_version': 1,
            'speaker_profile_id': 'imported-speaker',
            'display_name': '爸爸',
            'note': None,
            'voice_versions': [],
        }, {}, 'correct password',
    )

    inspected = client.post(
        '/api/speaker-profiles/import/inspect', headers=headers,
        files={'file': ('dad.flvoice', package, 'application/octet-stream')}, data={'password': 'correct password'},
    )

    assert inspected.status_code == 200
    assert inspected.json()['speaker_profile_id'] == 'imported-speaker'
    staged_profiles = client.get('/api/speaker-profiles', headers=headers).json()
    assert all(profile['display_name'] != '爸爸' for profile in staged_profiles)

    committed = client.post(
        '/api/speaker-profiles/import/commit', headers=headers,
        json={'import_id': inspected.json()['import_id'], 'strategy': 'create_new'},
    )
    assert committed.status_code == 201
    assert committed.json()['display_name'] == '爸爸（导入）'


def test_voice_package_commit_requires_supported_conflict_strategy(client, admin_user) -> None:
    from app.services.voice_packages import create_voice_package

    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    package = create_voice_package(
        {'format_version': 1, 'speaker_profile_id': 'speaker-id', 'display_name': '妈妈', 'voice_versions': []},
        {}, 'correct password',
    )
    inspected = client.post(
        '/api/speaker-profiles/import/inspect', headers=headers,
        files={'file': ('mom.flvoice', package, 'application/octet-stream')}, data={'password': 'correct password'},
    ).json()

    committed = client.post(
        '/api/speaker-profiles/import/commit', headers=headers,
        json={'import_id': inspected['import_id'], 'strategy': 'merge'},
    )

    assert committed.status_code == 201
    assert committed.json()['display_name'] == '妈妈'


def test_voice_package_commit_imports_reference_wav(client, admin_user) -> None:
    import hashlib

    from app.services.voice_packages import create_voice_package

    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    wav = b'normalized-wav'
    package = create_voice_package(
        {
            'format_version': 1, 'speaker_profile_id': 'imported-speaker', 'display_name': '爸爸', 'voice_versions': [{
                'id': 'imported-voice', 'display_name': '原声', 'provider': 'mimo',
                'model': 'mimo-v2.5-tts-voiceclone', 'reference_sha256': hashlib.sha256(wav).hexdigest(),
            }],
        }, {'audio/imported-voice.wav': wav}, 'correct password',
    )
    inspected = client.post(
        '/api/speaker-profiles/import/inspect', headers=headers,
        files={'file': ('dad.flvoice', package, 'application/octet-stream')}, data={'password': 'correct password'},
    ).json()

    committed = client.post(
        '/api/speaker-profiles/import/commit', headers=headers,
        json={'import_id': inspected['import_id'], 'strategy': 'create_new'},
    )

    assert committed.status_code == 201
    assert committed.json()['voice_version_count'] == 1
