"""Import every model so migrations and startup share complete metadata."""

from app.models.child import Child
from app.models.job import Job
from app.models.recording import Recording, RecordingChunk
from app.models.user import User, UserSession
from app.models.learning_item import LearningItem, LearningList, LearningListVersion
from app.models.word_list import WordItem, WordList, WordListVersion
from app.models.dictation import DictationResult, DictationSession
from app.models.tts_asset import TtsAsset
from app.models.tts_provider_config import TtsProviderConfig
from app.models.ai_provider_config import AiProviderConfig, SpellingOcrConfig
from app.models.dictionary import DictionaryEntry, DictionaryHistory
from app.models.unknown_item import UnknownItem
from app.models.speaker import SpeakerProfile, VoiceVersion
from app.models.learning_item_audio import LearningItemAudio

__all__ = ['Child', 'Job', 'Recording', 'RecordingChunk', 'User', 'UserSession', 'LearningItem', 'LearningList', 'LearningListVersion', 'WordItem', 'WordList', 'WordListVersion', 'DictationResult', 'DictationSession', 'TtsAsset', 'TtsProviderConfig', 'AiProviderConfig', 'SpellingOcrConfig', 'DictionaryEntry', 'DictionaryHistory', 'UnknownItem', 'SpeakerProfile', 'VoiceVersion', 'LearningItemAudio']
