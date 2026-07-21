import base64
import json
from urllib.request import Request, urlopen

from app.services.mimo_speech import spoken_messages


class MimoTtsError(Exception):
    pass


class MimoTtsClient:
    def __init__(self, api_key: str, base_url: str, model: str, voice: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.voice = voice

    def synthesize(self, text: str) -> bytes:
        payload = {
            'model': self.model,
            'messages': spoken_messages(text),
            'audio': {'format': 'wav', 'voice': self.voice},
        }
        request = Request(
            f'{self.base_url}/chat/completions',
            data=json.dumps(payload, separators=(',', ':')).encode(),
            headers={'api-key': self.api_key, 'Content-Type': 'application/json'},
            method='POST',
        )
        try:
            with urlopen(request, timeout=30) as response:
                body = json.loads(response.read())
            encoded = body['choices'][0]['message']['audio']['data']
            return base64.b64decode(encoded)
        except (KeyError, IndexError, ValueError, OSError) as error:
            raise MimoTtsError('MIMO_TTS_REQUEST_FAILED') from error
