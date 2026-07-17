import { render, screen } from '@testing-library/react'
import { DictationStatsPage } from './DictationStatsPage'

it('renders accuracy and grouped mistakes', () => {
  render(<DictationStatsPage stats={{ daily: [{ date: '2026-07-12', correct: 8, incorrect: 2, accuracy: 0.8 }], accuracy: 0.8, word_accuracy: 0.8, phrase_accuracy: null, sentence_accuracy: null, unknown_items: { added_this_week: 0, mastered_this_week: 0 }, dictionary_cache_hits: 0 }} mistakes={[{ word: 'Apple', normalized_text: 'apple', incorrect_count: 2, correct_count: 0 }]} />)
  expect(screen.getAllByText('80%')).not.toHaveLength(0)
  expect(screen.getByText('Apple')).toBeVisible()
})
