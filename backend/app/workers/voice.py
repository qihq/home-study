from pathlib import Path
from hashlib import sha256

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.speaker import VoiceVersion
from app.services.mimo_voice_clone import MimoVoiceCloneClient, MimoVoiceCloneError
from app.services.voice_samples import VoiceSampleError, normalize_voice_sample
from app.services.jobs import enqueue_once
from app.services.tts_config import api_key, get_tts_config

VOICE_AUDIO_VERSION = 3


def _mimo_credentials(session: Session) -> tuple[str, str] | None:
    config = get_tts_config(session)
    if config is not None and config.protocol == 'mimo' and config.api_key_encrypted:
        return api_key(config), config.base_url
    settings = get_settings()
    if settings.mimo_api_key and settings.mimo_api_base_url:
        return settings.mimo_api_key, settings.mimo_api_base_url
    return None


def process_normalize_voice_sample(session: Session, voice_version_id: str, report_progress=lambda _value: None) -> None:
    voice = session.get(VoiceVersion, voice_version_id)
    if voice is None or not voice.reference_audio_path:
        return
    source = Path(voice.reference_audio_path)
    target = get_settings().data_dir / 'voice-samples' / f'{voice.id}.wav'
    try:
        report_progress(20)
        metadata = normalize_voice_sample(source, target)
        report_progress(45)
    except VoiceSampleError as error:
        voice.status = 'failed'
        voice.failure_code = str(error)
        session.commit()
        return
    voice.reference_audio_path = str(target)
    voice.reference_mime_type = 'audio/wav'
    voice.reference_sha256 = sha256(target.read_bytes()).hexdigest()
    voice.duration_ms = metadata.duration_ms
    voice.size_bytes = metadata.size_bytes
    voice.status = 'processing'
    enqueue_once(session, 'voice_preview', voice.id)
    session.commit()


def process_voice_preview(session: Session, voice_version_id: str, report_progress=lambda _value: None) -> None:
    voice = session.get(VoiceVersion, voice_version_id)
    if voice is None or not voice.reference_audio_path:
        return
    settings = get_settings()
    credentials = _mimo_credentials(session)
    if credentials is None:
        voice.status = 'failed'
        voice.failure_code = 'VOICE_CLONE_FAILED'
        session.commit()
        return
    target = settings.tts_dir / 'voice-previews' / f'{voice.id}.wav'
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix('.wav.part')
    try:
        report_progress(60)
        audio = MimoVoiceCloneClient(*credentials).synthesize(
            'This is a voice preview for family learning.', Path(voice.reference_audio_path), voice.style_instruction,
        )
        report_progress(85)
        partial.write_bytes(audio)
        partial.replace(target)
    except (MimoVoiceCloneError, OSError):
        partial.unlink(missing_ok=True)
        voice.status = 'failed'
        voice.failure_code = 'VOICE_CLONE_FAILED'
    else:
        voice.status = 'ready'
        voice.failure_code = None
    session.commit()


def generate_text_with_voice(session: Session, voice_version_id: str, text: str, force: bool = False) -> Path:
    voice = session.get(VoiceVersion, voice_version_id)
    if voice is None or voice.status != 'ready' or not voice.reference_audio_path:
        raise ValueError('VOICE_VERSION_NOT_READY')
    settings = get_settings()
    credentials = _mimo_credentials(session)
    if credentials is None:
        raise ValueError('VOICE_CLONE_FAILED')
    filename = sha256(f'v{VOICE_AUDIO_VERSION}\n{voice.id}\n{text}'.encode()).hexdigest()
    target = settings.tts_dir / 'voice-text' / voice.id / f'{filename}.wav'
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not force:
        return target
    partial = target.with_suffix('.wav.part')
    try:
        partial.write_bytes(MimoVoiceCloneClient(*credentials).synthesize(
            text, Path(voice.reference_audio_path), voice.style_instruction,
        ))
        partial.replace(target)
    except (MimoVoiceCloneError, OSError) as error:
        partial.unlink(missing_ok=True)
        raise ValueError('VOICE_CLONE_FAILED') from error
    return target
