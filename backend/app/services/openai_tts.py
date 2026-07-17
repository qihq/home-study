import json
from urllib.request import Request, urlopen


class OpenAiTtsError(Exception):
    pass


class OpenAiTtsClient:
    def __init__(self, api_key: str, base_url: str, model: str, voice: str, speed: float) -> None:
        self.api_key, self.base_url, self.model, self.voice, self.speed = api_key, base_url.rstrip('/'), model, voice, speed

    def synthesize(self, text: str) -> bytes:
        request = Request(
            f'{self.base_url}/audio/speech',
            data=json.dumps({'model': self.model, 'input': text, 'voice': self.voice, 'speed': self.speed, 'response_format': 'wav'}, separators=(',', ':')).encode(),
            headers={'Authorization': f'Bearer {self.api_key}', 'Content-Type': 'application/json'},
            method='POST',
        )
        try:
            with urlopen(request, timeout=30) as response:
                return response.read()
        except OSError as error:
            raise OpenAiTtsError('OPENAI_TTS_REQUEST_FAILED') from error
