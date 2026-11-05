import json
import uuid
from socket import timeout as SocketTimeout
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Providers behind an edge proxy (OpenCode Zen) reject generic SDK/library user agents,
# so identify this client explicitly.
USER_AGENT = 'family-learning/0.1'

# DeepSeek (and a few gateways that route to it) reject `response_format: json_object`
# with 400 InvalidParameter unless the prompt itself mentions JSON. The dictionary prompt
# already says so, but short prompts such as the settings-page connection test ('apple')
# do not, which made that button fail for every DeepSeek model.
JSON_HINT = 'Respond with a single JSON object only.'


def _ensure_json_hint(messages: list[dict]) -> list[dict]:
    if any('json' in str(message.get('content', '')).lower() for message in messages):
        return messages
    prepared = list(messages)
    if prepared and prepared[0].get('role') == 'system' and isinstance(prepared[0].get('content'), str):
        prepared[0] = {**prepared[0], 'content': f"{prepared[0]['content']}\n{JSON_HINT}"}
    else:
        prepared.insert(0, {'role': 'system', 'content': JSON_HINT})
    return prepared


# Upstreams that reject JSON mode in their own words. Retrying without response_format keeps
# one flaky route in a gateway from failing the whole lookup.
JSON_MODE_REJECTIONS = ('json_object', 'response_format', 'must contain', 'not yet supported')


def _rejects_json_mode(detail: str) -> bool:
    text = (detail or '').lower()
    return any(token in text for token in JSON_MODE_REJECTIONS)


class OpenAiChatError(Exception):
    """A stable error code, plus the provider's own explanation when it sent one.

    ``str(error)`` stays the stable code so callers keep mapping codes to messages;
    ``detail`` carries what the upstream actually said (for example that a subscription
    is required) instead of collapsing every failure into one opaque gateway error.
    """

    def __init__(self, code: str, detail: str = '') -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


def _upstream_detail(error: HTTPError, secret: str) -> str:
    try:
        body = error.read().decode('utf-8', errors='replace').strip()
    except Exception:  # noqa: BLE001 - a broken error body must not mask the real failure
        return ''
    if not body:
        return ''
    detail = body
    try:
        payload = json.loads(body)
    except ValueError:
        pass
    else:
        if isinstance(payload, dict):
            inner = payload.get('error', payload)
            if isinstance(inner, dict) and isinstance(inner.get('message'), str):
                detail = inner['message']
            elif isinstance(inner, str):
                detail = inner
    detail = detail.strip()[:200]
    if secret and secret in detail:
        detail = detail.replace(secret, '***')
    return detail


class OpenAiChatClient:
    def __init__(
        self, api_key: str, base_url: str, model: str, timeout_seconds: int = 45,
        session_id: str | None = None, temperature: float | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        # OpenCode Go routes and caches on a stable per-conversation id. One client instance
        # is one conversation, so a retry inside the same client keeps the same id while a new
        # lookup starts a new one.
        self.session_id = session_id or str(uuid.uuid4())

    @property
    def chat_completions_url(self) -> str:
        if self.base_url.endswith('/chat/completions'):
            return self.base_url
        return f'{self.base_url}/chat/completions'

    def complete(self, messages: list[dict]) -> str:
        prepared = _ensure_json_hint(list(messages))
        try:
            return self._post(prepared, json_mode=True)
        except OpenAiChatError as error:
            # Some upstreams behind a gateway (OpenCode Go routes to several) answer 400
            # "this feature is not yet supported" for response_format. The prompts already
            # demand JSON, so retry once without the parameter instead of failing the lookup.
            if error.code == 'AI_REQUEST_FAILED' and _rejects_json_mode(error.detail):
                return self._post(prepared, json_mode=False)
            raise

    def _post(self, messages: list[dict], json_mode: bool) -> str:
        payload: dict = {
            'model': self.model,
            'messages': messages,
        }
        if json_mode:
            payload['response_format'] = {'type': 'json_object'}
        if self.temperature is not None:
            # Only send it when the caller configured one: a few providers reject an explicit
            # temperature outright, and the dictionary wants a low value for stable JSON.
            payload['temperature'] = self.temperature
        request = Request(
            self.chat_completions_url,
            data=json.dumps(payload, separators=(',', ':')).encode(),
            headers={
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
                'User-Agent': USER_AGENT,
                'x-opencode-session': self.session_id,
            },
            method='POST',
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read())
        except HTTPError as error:
            detail = _upstream_detail(error, self.api_key)
            if error.code == 401:
                raise OpenAiChatError('AI_AUTH_FAILED', detail) from error
            raise OpenAiChatError('AI_REQUEST_FAILED', detail or f'HTTP {error.code}') from error
        except (SocketTimeout, TimeoutError) as error:
            raise OpenAiChatError('AI_TIMEOUT') from error
        except URLError as error:
            if isinstance(error.reason, (SocketTimeout, TimeoutError)):
                raise OpenAiChatError('AI_TIMEOUT') from error
            raise OpenAiChatError('AI_REQUEST_FAILED') from error
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise OpenAiChatError('AI_REQUEST_FAILED') from error

        try:
            return payload['choices'][0]['message']['content']
        except (KeyError, IndexError, TypeError) as error:
            raise OpenAiChatError('AI_RESPONSE_INVALID') from error
