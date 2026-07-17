import json
from socket import timeout as SocketTimeout
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OpenAiChatError(Exception):
    pass


class OpenAiChatClient:
    def __init__(self, api_key: str, base_url: str, model: str, timeout_seconds: int = 45) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.timeout_seconds = timeout_seconds

    @property
    def chat_completions_url(self) -> str:
        if self.base_url.endswith('/chat/completions'):
            return self.base_url
        return f'{self.base_url}/chat/completions'

    def complete(self, messages: list[dict]) -> str:
        request = Request(
            self.chat_completions_url,
            data=json.dumps({
                'model': self.model,
                'messages': messages,
                'response_format': {'type': 'json_object'},
            }, separators=(',', ':')).encode(),
            headers={
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
                'User-Agent': 'family-learning/0.1',
            },
            method='POST',
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read())
        except HTTPError as error:
            if error.code == 401:
                raise OpenAiChatError('AI_AUTH_FAILED') from error
            raise OpenAiChatError('AI_REQUEST_FAILED') from error
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
