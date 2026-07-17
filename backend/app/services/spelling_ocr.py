import base64
import json
import re

from app.services.openai_chat import OpenAiChatClient, OpenAiChatError


class SpellingOcrError(Exception):
    pass


def recognize_spelling_image(image: bytes, mime_type: str, *, api_key: str, base_url: str, model: str, timeout_seconds: int) -> list[str]:
    encoded = base64.b64encode(image).decode()
    prompt = (
        'Read the English spelling words in this image. Return JSON only in the form '
        '{"words":["word one","word two"]}. Keep original spelling, omit non-English text, and do not invent words.'
    )
    try:
        raw = OpenAiChatClient(api_key, base_url, model, timeout_seconds).complete([{
            'role': 'user', 'content': [
                {'type': 'text', 'text': prompt},
                {'type': 'image_url', 'image_url': {'url': f'data:{mime_type};base64,{encoded}'}},
            ],
        }])
    except OpenAiChatError:
        raise
    try:
        payload = json.loads(raw)
        source = payload['words']
        if not isinstance(source, list):
            raise ValueError
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        raise SpellingOcrError('OCR_RESPONSE_INVALID') from error
    words: list[str] = []
    seen: set[str] = set()
    for item in source:
        if not isinstance(item, str):
            continue
        value = re.sub(r'\s+', ' ', item).strip()
        if not value or len(value) > 120 or not re.fullmatch(r"[A-Za-z][A-Za-z' -]*", value):
            continue
        normalized = value.casefold()
        if normalized not in seen:
            seen.add(normalized)
            words.append(value)
    if not words:
        raise SpellingOcrError('OCR_NO_WORDS_FOUND')
    return words
