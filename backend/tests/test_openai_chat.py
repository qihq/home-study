import json
from io import BytesIO
from socket import timeout as SocketTimeout
from urllib.error import HTTPError, URLError


def test_openai_chat_uses_bearer_key_and_json_response_format(monkeypatch) -> None:
    from app.services.openai_chat import OpenAiChatClient

    captured = {}

    def fake_urlopen(request, timeout):
        captured['url'] = request.full_url
        captured['headers'] = {key.casefold(): value for key, value in request.header_items()}
        captured['payload'] = json.loads(request.data)

        class Response:
            def read(self):
                return b'{"choices":[{"message":{"content":"{\\\"ok\\\":true}"}}]}'

            def __enter__(self): return self
            def __exit__(self, *_): return False

        return Response()

    monkeypatch.setattr('app.services.openai_chat.urlopen', fake_urlopen)

    response = OpenAiChatClient('ai-secret-abcd', 'https://provider.example/v1', 'custom-model').complete([
        {'role': 'user', 'content': 'apple'},
    ])

    assert response == '{"ok":true}'
    assert captured['url'] == 'https://provider.example/v1/chat/completions'
    assert captured['headers']['authorization'] == 'Bearer ai-secret-abcd'
    assert captured['payload']['response_format'] == {'type': 'json_object'}


def test_openai_chat_sends_a_user_agent_for_provider_edge_proxies(monkeypatch) -> None:
    from app.services.openai_chat import OpenAiChatClient

    captured = {}

    def fake_urlopen(request, timeout):
        captured['headers'] = {key.casefold(): value for key, value in request.header_items()}

        class Response:
            def read(self):
                return b'{"choices":[{"message":{"content":"{\\"ok\\":true}"}}]}'

            def __enter__(self): return self
            def __exit__(self, *_): return False

        return Response()

    monkeypatch.setattr('app.services.openai_chat.urlopen', fake_urlopen)

    OpenAiChatClient('ai-secret-abcd', 'https://provider.example/v1', 'custom-model').complete([
        {'role': 'user', 'content': 'apple'},
    ])

    assert captured['headers']['user-agent'] == 'family-learning/0.1'


def test_openai_chat_accepts_a_full_chat_completions_endpoint(monkeypatch) -> None:
    from app.services.openai_chat import OpenAiChatClient

    captured = {}

    def fake_urlopen(request, timeout):
        captured['url'] = request.full_url

        class Response:
            def read(self):
                return b'{"choices":[{"message":{"content":"{\\"ok\\":true}"}}]}'

            def __enter__(self): return self
            def __exit__(self, *_): return False

        return Response()

    monkeypatch.setattr('app.services.openai_chat.urlopen', fake_urlopen)

    OpenAiChatClient(
        'ai-secret-abcd', 'https://provider.example/v1/chat/completions', 'custom-model',
    ).complete([{'role': 'user', 'content': 'apple'}])

    assert captured['url'] == 'https://provider.example/v1/chat/completions'


def test_openai_chat_error_does_not_include_api_key(monkeypatch) -> None:
    from app.services.openai_chat import OpenAiChatClient, OpenAiChatError

    monkeypatch.setattr('app.services.openai_chat.urlopen', lambda *_args, **_kwargs: (_ for _ in ()).throw(URLError('offline')))

    try:
        OpenAiChatClient('ai-secret-abcd', 'https://provider.example/v1', 'custom-model').complete([])
    except OpenAiChatError as error:
        assert 'ai-secret-abcd' not in str(error)
    else:
        raise AssertionError('expected OpenAiChatError')


def test_openai_chat_maps_auth_timeout_and_forbidden_to_stable_codes(monkeypatch) -> None:
    from app.services.openai_chat import OpenAiChatClient, OpenAiChatError

    client = OpenAiChatClient('ai-secret-abcd', 'https://provider.example/v1', 'custom-model')
    monkeypatch.setattr(
        'app.services.openai_chat.urlopen',
        lambda *_args, **_kwargs: (_ for _ in ()).throw(HTTPError('https://provider.example/v1/chat/completions', 401, 'unauthorized', {}, None)),
    )
    try:
        client.complete([])
    except OpenAiChatError as error:
        assert str(error) == 'AI_AUTH_FAILED'
    else:
        raise AssertionError('expected OpenAiChatError')

    monkeypatch.setattr(
        'app.services.openai_chat.urlopen',
        lambda *_args, **_kwargs: (_ for _ in ()).throw(HTTPError('https://provider.example/v1/chat/completions', 403, 'forbidden', {}, None)),
    )
    try:
        client.complete([])
    except OpenAiChatError as error:
        assert str(error) == 'AI_REQUEST_FAILED'
    else:
        raise AssertionError('expected OpenAiChatError')

    monkeypatch.setattr('app.services.openai_chat.urlopen', lambda *_args, **_kwargs: (_ for _ in ()).throw(SocketTimeout()))
    try:
        client.complete([])
    except OpenAiChatError as error:
        assert str(error) == 'AI_TIMEOUT'
    else:
        raise AssertionError('expected OpenAiChatError')


def test_openai_chat_sends_the_configured_temperature_only_when_set(monkeypatch) -> None:
    """The settings page exposes 温度; it must reach the provider, and stay omitted otherwise
    because a few providers reject an explicit temperature outright."""
    from app.services.openai_chat import OpenAiChatClient

    captured: dict = {}

    def fake_urlopen(request, timeout):
        captured['payload'] = json.loads(request.data)

        class Response:
            def read(self):
                return b'{"choices":[{"message":{"content":"{}"}}]}'

            def __enter__(self): return self
            def __exit__(self, *_): return False

        return Response()

    monkeypatch.setattr('app.services.openai_chat.urlopen', fake_urlopen)

    OpenAiChatClient('ai-secret-abcd', 'https://provider.example/v1', 'custom-model', temperature=0.1).complete([])
    assert captured['payload']['temperature'] == 0.1

    OpenAiChatClient('ai-secret-abcd', 'https://provider.example/v1', 'custom-model').complete([])
    assert 'temperature' not in captured['payload']


def test_openai_chat_sends_a_stable_session_id_per_conversation(monkeypatch) -> None:
    """OpenCode Go returns HTTP 400 MissingSessionID without a per-conversation session id."""
    from app.services.openai_chat import OpenAiChatClient

    seen: list[str] = []

    def fake_urlopen(request, timeout):
        headers = {key.casefold(): value for key, value in request.header_items()}
        seen.append(headers.get('x-opencode-session', ''))

        class Response:
            def read(self):
                return b'{"choices":[{"message":{"content":"{}"}}]}'

            def __enter__(self): return self
            def __exit__(self, *_): return False

        return Response()

    monkeypatch.setattr('app.services.openai_chat.urlopen', fake_urlopen)

    client = OpenAiChatClient('ai-secret-abcd', 'https://provider.example/v1', 'custom-model')
    client.complete([{'role': 'user', 'content': 'apple'}])
    client.complete([{'role': 'user', 'content': 'repair'}])
    OpenAiChatClient('ai-secret-abcd', 'https://provider.example/v1', 'custom-model').complete([])

    assert seen[0], 'the session header must be present'
    assert seen[0] == seen[1], 'a retry inside one conversation keeps the same session id'
    assert seen[2] != seen[0], 'a new conversation gets a new session id'


def test_openai_chat_surfaces_the_provider_error_detail(monkeypatch) -> None:
    """A 403 "subscription required" must be visible instead of a bare gateway failure."""
    from app.services.openai_chat import OpenAiChatClient, OpenAiChatError

    body = b'{"error":{"type":"FreeTierError","message":"An active OpenCode Go subscription is required."}}'
    monkeypatch.setattr(
        'app.services.openai_chat.urlopen',
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            HTTPError('https://provider.example/v1/chat/completions', 403, 'forbidden', {}, BytesIO(body))
        ),
    )

    try:
        OpenAiChatClient('ai-secret-abcd', 'https://provider.example/v1', 'custom-model').complete([])
    except OpenAiChatError as error:
        assert str(error) == 'AI_REQUEST_FAILED'
        assert error.detail == 'An active OpenCode Go subscription is required.'
    else:
        raise AssertionError('expected OpenAiChatError')


def test_openai_chat_redacts_the_api_key_from_provider_detail(monkeypatch) -> None:
    from app.services.openai_chat import OpenAiChatClient, OpenAiChatError

    body = b'{"error":{"message":"key ai-secret-abcd was rejected"}}'
    monkeypatch.setattr(
        'app.services.openai_chat.urlopen',
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            HTTPError('https://provider.example/v1/chat/completions', 401, 'unauthorized', {}, BytesIO(body))
        ),
    )

    try:
        OpenAiChatClient('ai-secret-abcd', 'https://provider.example/v1', 'custom-model').complete([])
    except OpenAiChatError as error:
        assert 'ai-secret-abcd' not in error.detail
        assert '***' in error.detail
    else:
        raise AssertionError('expected OpenAiChatError')
