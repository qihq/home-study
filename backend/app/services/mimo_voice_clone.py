import base64
import json
from pathlib import Path
from urllib.request import Request, urlopen

from app.services.mimo_speech import spoken_messages


class MimoVoiceCloneError(Exception):
    pass


class MimoVoiceCloneClient:
    def __init__(self, api_key: str, base_url: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')

    def synthesize(self, text: str, reference_wav: Path, instruction: str) -> bytes:
        payload = {
            'model': 'mimo-v2.5-tts-voiceclone',
            'messages': spoken_messages(text, instruction),
            'audio': {'format': 'wav', 'voice': f'data:audio/wav;base64,{base64.b64encode(reference_wav.read_bytes()).decode()}'},
        }
        request = Request(
            f'{self.base_url}/chat/completions', data=json.dumps(payload, separators=(',', ':')).encode(),
            headers={'api-key': self.api_key, 'Content-Type': 'application/json'}, method='POST',
        )
        try:
            with urlopen(request, timeout=45) as response:
                body = json.loads(response.read())
            return base64.b64decode(body['choices'][0]['message']['audio']['data'])
        except (KeyError, IndexError, ValueError, OSError) as error:
            raise MimoVoiceCloneError('VOICE_CLONE_FAILED') from error
