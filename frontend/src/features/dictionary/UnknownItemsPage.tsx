import { useEffect, useState } from 'react'
import { Button } from '../../ui/Button'

export type UnknownItem = {
  id: string
  item_type: 'word' | 'phrase' | 'sentence'
  source_text: string
  translation_text: string
  status: 'unknown' | 'mastered'
}

type Filters = { status: 'unknown' | 'mastered'; item_type: 'all' | UnknownItem['item_type'] }
type GeneratedItem = { display_text: string; item_type: UnknownItem['item_type']; translation_text?: string | null }
type GeneratedList = { id: string; title: string; status: string; created_at: string; items: GeneratedItem[]; word_list_version_id?: string | null }
type MainTab = 'items' | 'generated'

export function UnknownItemsPage({ onLoad, onUpdateStatus, onCreateLearningList, onLoadLearningLists, onConfirmLearningList, onStartDictation, onDelete }: {
  onLoad: (filters: Filters) => Promise<UnknownItem[]>
  onUpdateStatus: (id: string, status: UnknownItem['status']) => Promise<void>
  onCreateLearningList: (ids: string[], title?: string) => Promise<{ id: string; title?: string; status: string }>
  onLoadLearningLists?: () => Promise<GeneratedList[]>
  onConfirmLearningList?: (id: string) => Promise<{ word_list_version_id: string }>
  onStartDictation?: (items: string[], versionId: string) => void
  onDelete?: (id: string) => Promise<void>
}) {
  const [mainTab, setMainTab] = useState<MainTab>('items')
  const [filters, setFilters] = useState<Filters>({ status: 'unknown', item_type: 'all' })
  const [items, setItems] = useState<UnknownItem[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [title, setTitle] = useState(`生词复习 · ${new Date().toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })}`)
  const [generatedLists, setGeneratedLists] = useState<GeneratedList[]>([])
  const [activeGeneratedId, setActiveGeneratedId] = useState<string | null>(null)
  const [message, setMessage] = useState('')

  const load = async () => {
    try { setItems(await onLoad(filters)) }
    catch { setMessage('加载生词本失败，请稍后重试。') }
  }
  const loadGenerated = async () => {
    if (!onLoadLearningLists) return
    try {
      const lists = await onLoadLearningLists()
      setGeneratedLists(lists)
      setActiveGeneratedId(current => current && lists.some(list => list.id === current) ? current : lists[0]?.id ?? null)
    } catch { setMessage('加载生成的学习本失败，请稍后重试。') }
  }

  useEffect(() => { void load() }, [filters.status, filters.item_type])
  useEffect(() => { if (mainTab === 'generated') void loadGenerated() }, [mainTab])

  const setFilter = <K extends keyof Filters>(key: K, value: Filters[K]) => setFilters(current => ({ ...current, [key]: value }))
  const toggle = (id: string) => setSelected(current => current.includes(id) ? current.filter(value => value !== id) : [...current, id])
  const updateStatus = async (item: UnknownItem) => {
    const status = item.status === 'unknown' ? 'mastered' : 'unknown'
    try { await onUpdateStatus(item.id, status); await load() }
    catch { setMessage('更新状态失败，请稍后重试。') }
  }
  const createList = async () => {
    if (!selected.length) return
    try {
      const created = await onCreateLearningList(selected, title)
      setSelected([])
      setMainTab('generated')
      if (onLoadLearningLists) {
        const lists = await onLoadLearningLists()
        setGeneratedLists(lists)
        setActiveGeneratedId(created.id)
      }
      setMessage('学习本已生成，请确认内容后开始默写。')
    } catch { setMessage('创建学习本失败，请稍后重试。') }
  }
  const remove = async (item: UnknownItem) => {
    if (!window.confirm(`确定删除生词“${item.source_text}”吗？`)) return
    try {
      await onDelete?.(item.id)
      setItems(current => current.filter(value => value.id !== item.id))
      setSelected(current => current.filter(id => id !== item.id))
      setMessage('生词已删除。')
    } catch { setMessage('删除生词失败，请稍后重试。') }
  }
  const confirmGenerated = async (list: GeneratedList) => {
    if (!onConfirmLearningList || !onStartDictation) return
    try {
      const version = await onConfirmLearningList(list.id)
      onStartDictation(list.items.map(item => item.display_text), version.word_list_version_id)
    } catch { setMessage('确认学习本失败，请稍后重试。') }
  }
  const activeList = generatedLists.find(list => list.id === activeGeneratedId)

  return <section className="unknown-items-page">
    <header className="unknown-items-header"><div><p className="date">小岛设计台</p><h1>生词本</h1><p>挑选不认识的单词、短语或句子，整理成可练习的学习本。</p></div><img src="/animal-island/design.svg" alt="" /></header>
    <div className="island-tabs" role="tablist" aria-label="生词本功能"><button type="button" role="tab" aria-selected={mainTab === 'items'} onClick={() => setMainTab('items')}>生词</button><button type="button" role="tab" aria-selected={mainTab === 'generated'} onClick={() => setMainTab('generated')}>生成的学习本</button></div>
    {message && <p role="status">{message}</p>}
    {mainTab === 'items' && <section className="unknown-items-panel" role="tabpanel">
      <div className="unknown-filters"><label>状态筛选<select aria-label="状态筛选" value={filters.status} onChange={event => setFilter('status', event.target.value as Filters['status'])}><option value="unknown">不认识</option><option value="mastered">已掌握</option></select></label><label>类型筛选<select aria-label="类型筛选" value={filters.item_type} onChange={event => setFilter('item_type', event.target.value as Filters['item_type'])}><option value="all">全部类型</option><option value="word">单词</option><option value="phrase">短语</option><option value="sentence">句子</option></select></label><p>{items.length} 条结果</p></div>
      {selected.length > 0 && <div className="unknown-primary-action"><span>已选 {selected.length} 条</span><label>学习本名称<input aria-label="学习本名称" value={title} onChange={event => setTitle(event.target.value)} /></label><Button onClick={() => void createList()}>生成学习本（{selected.length}）</Button><Button variant="secondary" onClick={() => setSelected([])}>取消选择</Button></div>}
      <div className="unknown-item-grid">{items.map(item => <article key={item.id}><label className="unknown-select"><input aria-label={`选择 ${item.source_text}`} type="checkbox" checked={selected.includes(item.id)} onChange={() => toggle(item.id)} /> 选择</label><p className="unknown-item-type">{item.item_type}</p><h2>{item.source_text}</h2><p>{item.translation_text}</p><div className="unknown-card-actions"><button onClick={() => void updateStatus(item)}>{item.status === 'unknown' ? '标记已掌握' : '恢复不认识'}</button><button aria-label={`删除 ${item.source_text}`} onClick={() => void remove(item)}>删除</button></div></article>)}</div>
    </section>}
    {mainTab === 'generated' && <section className="generated-learning-panel" role="tabpanel">
      {generatedLists.length === 0 ? <div className="learning-book-empty"><img src="/animal-island/diy.svg" alt="" /><h2>还没有生成的学习本</h2><p>从生词里选择内容后就会出现在这里。</p><Button onClick={() => setMainTab('items')}>去选择生词</Button></div> : <><div className="generated-list-tabs" role="tablist" aria-label="生成的学习本列表">{generatedLists.map(list => <button key={list.id} type="button" role="tab" aria-selected={activeList?.id === list.id} onClick={() => setActiveGeneratedId(list.id)}>{list.title}<small>{list.items.length} 条</small></button>)}</div>{activeList && <article className="generated-learning-card"><div><p className="date">{new Date(activeList.created_at).toLocaleDateString('zh-CN')}</p><h2>{activeList.title}</h2><p>{activeList.status === 'draft' ? '草稿，确认后可开始默写。' : '已确认学习本。'}</p></div><div className="generated-learning-items">{activeList.items.map((item, index) => <div key={`${item.display_text}-${index}`}><strong>{item.display_text}</strong><span>{item.item_type === 'word' ? '单词' : item.item_type === 'phrase' ? '短语' : '句子'}</span>{item.translation_text && <p>{item.translation_text}</p>}</div>)}</div><div className="list-actions">{activeList.status === 'draft' ? <Button onClick={() => void confirmGenerated(activeList)}>确认并开始默写</Button> : activeList.word_list_version_id && onStartDictation ? <Button onClick={() => onStartDictation(activeList.items.map(item => item.display_text), activeList.word_list_version_id!)}>开始默写</Button> : null}<Button variant="secondary" onClick={() => setMainTab('items')}>返回生词</Button></div></article>}</>}
    </section>}
  </section>
}
