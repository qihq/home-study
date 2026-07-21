SPEAK_ONLY_INSTRUCTION = 'Speak only the assistant content once.'


def spoken_messages(text: str, style_instruction: str = '') -> list[dict[str, str]]:
    spoken_text = text.strip()
    if not spoken_text:
        raise ValueError('TTS_TEXT_EMPTY')
    control = style_instruction.strip()
    instruction = f'{control}\n{SPEAK_ONLY_INSTRUCTION}' if control else SPEAK_ONLY_INSTRUCTION
    return [
        {'role': 'system', 'content': instruction},
        {'role': 'assistant', 'content': spoken_text},
    ]
