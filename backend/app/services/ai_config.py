from pathlib import Path

from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.ai_provider_config import AiProviderConfig, SpellingOcrConfig
from app.services.tts_config import mask_key


def _key_path() -> Path:
    path = get_settings().data_dir / 'ai-settings.key'
    if not path.exists():
        path.write_bytes(Fernet.generate_key())
    return path


def _cipher() -> Fernet:
    return Fernet(_key_path().read_bytes())


def get_ai_config(session: Session) -> AiProviderConfig | None:
    return session.get(AiProviderConfig, 1)


def ai_api_key(config: AiProviderConfig) -> str | None:
    return _cipher().decrypt(config.api_key_encrypted.encode()).decode() if config.api_key_encrypted else None


def present_ai_config(config: AiProviderConfig | None) -> dict:
    if config is None:
        return {
            'protocol': 'openai_chat_compatible', 'display_name': 'OpenCode Go', 'base_url': None,
            'model': None, 'temperature': 0.1, 'timeout_seconds': 45, 'enabled': False,
            'api_key_configured': False, 'api_key_mask': None,
        }
    return {
        'protocol': config.protocol, 'display_name': config.display_name, 'base_url': config.base_url,
        'model': config.model, 'temperature': config.temperature, 'timeout_seconds': config.timeout_seconds,
        'enabled': config.enabled, 'api_key_configured': bool(config.api_key_encrypted),
        'api_key_mask': mask_key(ai_api_key(config)),
    }


def save_ai_config(
    session: Session, *, protocol: str, display_name: str, base_url: str, api_key_value: str | None,
    model: str, temperature: float, timeout_seconds: int, enabled: bool,
) -> AiProviderConfig:
    config = get_ai_config(session)
    if config is None:
        config = AiProviderConfig(
            id=1, protocol=protocol, display_name=display_name, base_url=base_url, model=model,
            temperature=temperature, timeout_seconds=timeout_seconds, enabled=enabled,
        )
        session.add(config)
    else:
        config.protocol = protocol
        config.display_name = display_name
        config.base_url = base_url
        config.model = model
        config.temperature = temperature
        config.timeout_seconds = timeout_seconds
        config.enabled = enabled
    if api_key_value:
        config.api_key_encrypted = _cipher().encrypt(api_key_value.encode()).decode()
    session.commit()
    session.refresh(config)
    return config


def get_spelling_ocr_config(session: Session) -> SpellingOcrConfig | None:
    return session.get(SpellingOcrConfig, 1)


def present_spelling_ocr_config(config: SpellingOcrConfig | None) -> dict:
    if config is None:
        return {
            'source': 'dictionary', 'protocol': 'openai_chat_compatible', 'display_name': 'Spelling OCR AI',
            'base_url': None, 'model': None, 'temperature': 0.0, 'timeout_seconds': 45, 'enabled': True,
            'api_key_configured': False, 'api_key_mask': None,
        }
    return {
        'source': config.source, 'protocol': config.protocol, 'display_name': config.display_name,
        'base_url': config.base_url, 'model': config.model, 'temperature': config.temperature,
        'timeout_seconds': config.timeout_seconds, 'enabled': config.enabled,
        'api_key_configured': bool(config.api_key_encrypted),
        'api_key_mask': mask_key(_cipher().decrypt(config.api_key_encrypted.encode()).decode()) if config.api_key_encrypted else None,
    }


def save_spelling_ocr_config(
    session: Session, *, source: str, protocol: str, display_name: str, base_url: str | None,
    api_key_value: str | None, model: str | None, temperature: float, timeout_seconds: int, enabled: bool,
) -> SpellingOcrConfig:
    config = get_spelling_ocr_config(session)
    if config is None:
        config = SpellingOcrConfig(id=1)
        session.add(config)
    config.source = source
    config.protocol = protocol
    config.display_name = display_name
    config.base_url = base_url
    config.model = model
    config.temperature = temperature
    config.timeout_seconds = timeout_seconds
    config.enabled = enabled
    if api_key_value:
        config.api_key_encrypted = _cipher().encrypt(api_key_value.encode()).decode()
    session.commit()
    session.refresh(config)
    return config


def spelling_ocr_provider(session: Session) -> tuple[str, str, str, int, float]:
    config = get_spelling_ocr_config(session)
    if config is None or config.source == 'dictionary':
        dictionary = get_ai_config(session)
        if dictionary is None or not dictionary.enabled or not dictionary.api_key_encrypted:
            raise ValueError('OCR_AI_NOT_CONFIGURED')
        return ai_api_key(dictionary) or '', dictionary.base_url, dictionary.model, dictionary.timeout_seconds, dictionary.temperature
    if not config.enabled or not config.api_key_encrypted or not config.base_url or not config.model:
        raise ValueError('OCR_AI_NOT_CONFIGURED')
    return _cipher().decrypt(config.api_key_encrypted.encode()).decode(), config.base_url, config.model, config.timeout_seconds, config.temperature
