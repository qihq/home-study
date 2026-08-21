"""Message construction for MiMo TTS requests.

Official docs: https://mimo.mi.com/docs/zh-CN/api/audio/tts

- The target text MUST be placed in the assistant message.
- The user message holds style instructions and is never spoken.
- Speech rate has no numeric parameter: it is controlled by natural-language
  instruction or (style) tags, so the configured speed is compiled into the
  user instruction for the mimo protocol.
- Built-in voices are language specific (Chinese / English); choose the voice
  per target-text language via :func:`resolve_voice`.
"""

import re
from typing import Literal

ENGLISH_VOICES = ('Chloe', 'Mia', 'Milo', 'Dean')
CHINESE_VOICES = ('冰糖', '茉莉', '苏打', '白桦')
DEFAULT_VOICE = 'mimo_default'
DEFAULT_EN_VOICE = 'Chloe'
DEFAULT_ZH_VOICE = '冰糖'

SENTENCE_INSTRUCTION = '清晰、中性、自然的朗读风格。只朗读目标文本，不添加任何额外内容。'
WORD_INSTRUCTION = '标准词典发音，清晰自然地只朗读一遍目标单词，不添加任何额外内容。'

_CJK = re.compile(r'[\u3400-\u9fff]')
_ENGLISH_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")
_CHINESE_WORD = re.compile(r'[\u3400-\u9fff]{1,12}')

Scenario = Literal['sentence', 'word', 'clone']


def detect_language(text: str) -> str:
    return 'zh' if _CJK.search(text) else 'en'


def is_word_text(text: str) -> bool:
    normalized = ' '.join(text.split())
    return bool(_ENGLISH_WORD.fullmatch(normalized)) or bool(_CHINESE_WORD.fullmatch(normalized))


def speed_phrase(speed: float) -> str:
    if speed <= 0.7:
        return '语速明显放慢。'
    if speed <= 0.9:
        return '语速稍慢。'
    if speed <= 1.15:
        return ''
    if speed <= 1.4:
        return '语速稍快。'
    return '语速明显加快。'


def resolve_voice(voice: str, voice_zh: str, language: str) -> str:
    if language == 'zh':
        return voice_zh or DEFAULT_ZH_VOICE
    return voice or DEFAULT_EN_VOICE


def spoken_messages(
    text: str, style_instruction: str = '', speed: float | None = None, scenario: Scenario = 'sentence',
) -> list[dict[str, str]]:
    spoken_text = text.strip()
    if not spoken_text:
        raise ValueError('TTS_TEXT_EMPTY')
    if scenario == 'clone':
        instruction = style_instruction.strip()
    else:
        parts = []
        control = style_instruction.strip()
        if control:
            parts.append(control)
        parts.append(WORD_INSTRUCTION if scenario == 'word' else SENTENCE_INSTRUCTION)
        phrase = speed_phrase(speed) if speed is not None else ''
        if phrase:
            parts.append(phrase)
        instruction = '\n'.join(parts)
    return [
        {'role': 'user', 'content': instruction},
        {'role': 'assistant', 'content': spoken_text},
    ]
