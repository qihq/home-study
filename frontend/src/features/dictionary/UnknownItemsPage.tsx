import { useEffect, useState } from 'react'

export type UnknownItem = {
  id: string
  item_type: 'word' | 'phrase' | 'sentence'
  source_text: string
  translation_text: string
  status: 'unknown' | 'mastered'
}

type Filters = { status: 'unknown' | 'mastered'; item_type: 'all' | UnknownItem['item_type'] }

export function UnknownItemsPage({ onLoad, onUpdateStatus, onCreateLearningList, onDelete }: {
  onLoad: (filters: Filters) => Promise<UnknownItem[]>
  onUpdateStatus: (id: string, status: UnknownItem['status']) => Promise<void>
  onCreateLearningList: (ids: string[]) => Promise<{ id: string; status: string }>
  onDelete?: (id: string) => Promise<void>
}) {
  const [filters, setFilters] = useState<Filters>({ status: 'unknown', item_type: 'all' })
  const [items, setItems] = useState<UnknownItem[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [message, setMessage] = useState('')
  const load = async () => {
    try { setItems(await onLoad(filters)) }
    catch { setMessage('加载生词本失败，请稍后重试。') }
  }
  useEffect(() => { void load() }, [filters.status, filters.item_type])
  const setFilter = <K extends keyof Filters>(key: K, value: Filters[K]) => setFilters(current => ({ ...current, [key]: value }))
  const updateStatus = async (item: UnknownItem) => {
    const status = item.status === 'unknown' ? 'mastered' : 'unknown'
    try { await onUpdateStatus(item.id, status); await load() }
    catch { setMessage('更新状态失败，请稍后重试。') }
  }
  const toggle = (id: string) => setSelected(current => current.includes(id) ? current.filter(value => value !== id) : [...current, id])
  const createList = async () => {
    if (!selected.length) return
    try { await onCreateLearningList(selected); setSelected([]); setMessage('已创建草稿学习列表。') }
    catch { setMessage('创建学习列表失败，请稍后重试。') }
  }
  const remove = async (item: UnknownItem) => { if (!window.confirm(`确定删除生词“${item.source_text}”吗？`)) return; try { await onDelete?.(item.id); setItems(current => current.filter(value => value.id !== item.id)); setSelected(current => current.filter(id => id !== item.id)); setMessage('生词已删除。') } catch { setMessage('删除生词失败，请稍后重试。') } }
  return <section className="unknown-items-page"><header><h1>生词本</h1><p>选择不认识的单词、短语或句子，整理成新的学习列表。</p></header><div className="unknown-filters"><label>状态筛选<select aria-label="状态筛选" value={filters.status} onChange={event => setFilter('status', event.target.value as Filters['status'])}><option value="unknown">不认识</option><option value="mastered">已掌握</option></select></label><label>类型筛选<select aria-label="类型筛选" value={filters.item_type} onChange={event => setFilter('item_type', event.target.value as Filters['item_type'])}><option value="all">全部类型</option><option value="word">单词</option><option value="phrase">短语</option><option value="sentence">句子</option></select></label></div><div className="unknown-primary-action"><button disabled={!selected.length} onClick={() => void createList()}>创建学习列表（{selected.length}）</button></div>{message && <p role="status">{message}</p>}<div className="unknown-item-grid">{items.map(item => <article key={item.id}><label><input aria-label={`选择 ${item.source_text}`} type="checkbox" checked={selected.includes(item.id)} onChange={() => toggle(item.id)} /> 选择</label><p className="unknown-item-type">{item.item_type}</p><h2>{item.source_text}</h2><p>{item.translation_text}</p><button onClick={() => void updateStatus(item)}>{item.status === 'unknown' ? '标记已掌握' : '恢复不认识'}</button><button aria-label={`删除 ${item.source_text}`} onClick={() => void remove(item)}>删除</button></article>)}</div></section>
}
