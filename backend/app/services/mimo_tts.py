import base64
import json
from collections.abc import Iterator
from urllib.request import Request, urlopen

from app.services.mimo_speech import is_word_text, spoken_messages


class MimoTtsError(Exception):
    pass


class MimoTtsClient:
    def __init__(self, api_key: str, base_url: str, model: str, voice: str, speed: float = 1.0) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.voice = voice
        self.speed = speed

    def _scenario(self, text: str) -> str:
        return 'word' if is_word_text(text) else 'sentence'

    def synthesize(self, text: str) -> bytes:
        # The official API has no numeric speed parameter; speed is compiled
        # into the style instruction instead (see app.services.mimo_speech).
        payload = {
            'model': self.model,
            'messages': spoken_messages(text, speed=self.speed, scenario=self._scenario(text)),
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

    def stream(self, text: str) -> Iterator[bytes]:
        """Yield 24kHz PCM16LE mono chunks from the low-latency streaming API.

        Official docs require ``format: pcm16`` with ``stream: true``; chunks
        arrive as server-sent ``data:`` lines carrying base64 audio deltas.
        """
        payload = {
            'model': self.model,
            'messages': spoken_messages(text, speed=self.speed, scenario=self._scenario(text)),
            'audio': {'format': 'pcm16', 'voice': self.voice},
            'stream': True,
        }
        request = Request(
            f'{self.base_url}/chat/completions',
            data=json.dumps(payload, separators=(',', ':')).encode(),
            headers={'api-key': self.api_key, 'Content-Type': 'application/json'},
            method='POST',
        )
        try:
            with urlopen(request, timeout=60) as response:
                for line in response:
                    line = line.strip()
                    if not line.startswith(b'data:'):
                        continue
                    block = line[5:].strip()
                    if block == b'[DONE]':
                        break
                    try:
                        body = json.loads(block)
                    except ValueError:
                        continue
                    audio = (body.get('choices') or [{}])[0].get('delta', {}).get('audio') or {}
                    data = audio.get('data')
                    if data:
                        yield base64.b64decode(data)
        except (KeyError, IndexError, ValueError, OSError) as error:
            raise MimoTtsError('MIMO_TTS_STREAM_FAILED') from error

