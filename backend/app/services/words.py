import re
import unicodedata

from sqlalchemy.orm import Session

from app.models.learning_item import LearningList, LearningListVersion
from app.services.learning_items import confirm_learning_list, create_learning_list


def normalize_word(text: str) -> str:
    return ' '.join(unicodedata.normalize('NFKC', text).strip().split()).casefold()


def parse_pasted_words(text: str) -> list[dict[str, str]]:
    candidates = re.split(r'[\n,;]+', text)
    seen: set[str] = set(); result: list[dict[str, str]] = []
    for candidate in candidates:
        display = ' '.join(candidate.strip().split())
        normalized = normalize_word(display)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append({'display_text': display, 'normalized_text': normalized})
    return result


def create_draft_word_list(session: Session, child_id: str, title: str, items: list[dict[str, str]]) -> LearningList:
    return create_learning_list(session, child_id, title, items)


def confirm_word_list(session: Session, word_list_id: str) -> LearningListVersion:
    try:
        return confirm_learning_list(session, word_list_id)
    except ValueError as error:
        if str(error) == 'LEARNING_LIST_NOT_FOUND':
            raise ValueError('WORD_LIST_NOT_FOUND') from error
        raise
