"""Backward-compatible names for the unified learning-item models."""

from app.models.learning_item import LearningItem, LearningList, LearningListVersion

WordList = LearningList
WordListVersion = LearningListVersion
WordItem = LearningItem

__all__ = ['LearningItem', 'LearningList', 'LearningListVersion', 'WordItem', 'WordList', 'WordListVersion']
