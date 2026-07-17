from datetime import date, datetime


def test_make_official_switches_same_day_language_without_deleting_other(client, admin_user):
    from app.db.session import get_session_factory
    from app.models.child import Child
    from app.models.recording import Recording

    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    with get_session_factory()() as session:
        child = Child(display_name='孩子', slug='official-child')
        session.add(child); session.flush()
        first = Recording(child_id=child.id, reading_date=date.today(), language_type='chinese', status='ready', is_official=True, source_validated_at=datetime.now())
        second = Recording(child_id=child.id, reading_date=date.today(), language_type='chinese', status='ready', source_validated_at=datetime.now())
        session.add_all([first, second]); session.commit()
        first_id, second_id = first.id, second.id

    response = client.post(f'/api/recordings/{second_id}/make-official', headers=headers)

    assert response.status_code == 200
    with get_session_factory()() as session:
        assert session.get(Recording, first_id).is_official is False
        assert session.get(Recording, second_id).is_official is True
