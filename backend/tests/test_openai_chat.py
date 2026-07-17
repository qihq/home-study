import json
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
