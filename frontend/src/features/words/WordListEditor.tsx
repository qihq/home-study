import { ChangeEvent, useEffect, useState } from 'react'
import { api } from '../../api/client'
import { Button } from '../../ui/Button'

function parse(text: string) {
  const seen = new Set<string>()
  return text.split(/[\n,;]+/).map(value => value.trim().replace(/\s+/g, ' ')).filter(value => { const key = value.toLowerCase(); if (!value || seen.has(key)) return false; seen.add(key); return true })
}
function inferType(text: string): 'word' | 'phrase' | 'sentence' { return /[.!?。！？]$/.test(text) ? 'sentence' : text.includes(' ') ? 'phrase' : 'word' }
type TtsProgress = { total: number; ready: number; queued: number; running: number; failed: number; progress?: number }
type ItemDetail = { id: string; display_text: string; pronunciation_source: 'default' | 'configured' | 'custom'; audio_ready: boolean }
type SavedList = { id: string; title: string; status: string; source_type: 'paste' | 'image' | 'file'; word_list_version_id: string | null; items: string[]; item_details?: ItemDetail[]; tts_progress: TtsProgress | null }
const sourceLabels = { paste: '手动录入', image: '图片识别', file: '文件导入' }

export function WordListEditor({ onConfirm }: { onConfirm: (words: string[], versionId?: string) => void }) {
  const [text, setText] = useState('')
  const [title, setTitle] = useState('单词本')
  const [words, setWords] = useState<string[]>([])
  const [itemTypes, setItemTypes] = useState<Array<'word' | 'phrase' | 'sentence'>>([])
  const [translations, setTranslations] = useState<string[]>([])
  const [message, setMessage] = useState('')
  const [ttsProgress, setTtsProgress] = useState<TtsProgress | null>(null)
  const [confirmedVersionId, setConfirmedVersionId] = useState<string>()
  const [savedLists, setSavedLists] = useState<SavedList[]>([])
  const [editingId, setEditingId] = useState<string | null>(null)
  const [sourceType, setSourceType] = useState<'paste' | 'image' | 'file'>('paste')
  const [workerOnline, setWorkerOnline] = useState(true)
  const [ocrReady, setOcrReady] = useState(false)
  const applyWords = (items: string[]) => { setWords(items); setItemTypes(items.map(inferType)); setTranslations(items.map(() => '')) }
  const loadSavedLists = () => void api<SavedList[]>('/word-lists').then(value => setSavedLists(Array.isArray(value) ? value : [])).catch(() => setSavedLists([]))
  useEffect(() => { const refresh = () => { loadSavedLists(); void api<{ worker?: boolean }>('/health').then(value => setWorkerOnline(value.worker !== false)).catch(() => setWorkerOnline(false)) }; refresh(); const timer = window.setInterval(refresh, 3000); return () => window.clearInterval(timer) }, [])
  useEffect(() => { if (!confirmedVersionId) return; const refresh = () => void api<TtsProgress>(`/word-list-versions/${confirmedVersionId}/tts-progress`).then(setTtsProgress).catch(() => undefined); refresh(); const timer = window.setInterval(refresh, 3000); return () => window.clearInterval(timer) }, [confirmedVersionId])

  async function upload(event: ChangeEvent<HTMLInputElement>) { const file = event.target.files?.[0]; if (!file) return; setMessage('正在解析文件…'); try { const body = new FormData(); body.set('file', file); const parsed = await api<{ status: string; items: Array<{ display_text: string }>; warnings: string[] }>('/imports', { method: 'POST', body }); if (parsed.status !== 'parsed') { setMessage(parsed.warnings[0] ?? '文件暂时无法解析。'); return }; applyWords(parsed.items.map(item => item.display_text)); setSourceType('file'); setMessage(parsed.warnings.join(' ')) } catch { setMessage('上传或解析失败，请检查文件格式。') } }
  async function recognizeImage(event: ChangeEvent<HTMLInputElement>) { const file = event.target.files?.[0]; if (!file) return; setOcrReady(false); setMessage('正在识别图片中的拼写单词…'); try { const body = new FormData(); body.set('file', file); const result = await api<{ words: string[] }>('/word-lists/recognize-image', { method: 'POST', body }); applyWords(result.words); setSourceType('image'); setOcrReady(true); setMessage(`已识别 ${result.words.length} 个单词，请确认后保存。`) } catch { setMessage('图片识别失败。请检查识别 AI 配置，并确认所选模型支持图片。') } }
  const resetEditor = () => { setEditingId(null); setTitle('单词本'); setText(''); applyWords([]); setSourceType('paste'); setOcrReady(false) }
  async function save() {
    try {
      const pasted_text = words.join('\n')
      if (editingId) {
        const version = await api<{ word_list_version_id: string; tts_progress: TtsProgress }>(`/word-lists/${editingId}`, { method: 'PATCH', body: JSON.stringify({ title, pasted_text }) })
        setConfirmedVersionId(version.word_list_version_id); setTtsProgress(version.tts_progress); setMessage('学习本已更新，已创建新版本并开始生成新的本地发音。')
      } else {
        const created = await api<{ id: string }>('/word-lists', { method: 'POST', body: JSON.stringify({ title, pasted_text, source_type: sourceType }) })
        const version = await api<{ word_list_version_id: string; queued_item_count?: number; tts_progress?: TtsProgress }>(`/word-lists/${created.id}/confirm`, { method: 'POST' })
        setConfirmedVersionId(version.word_list_version_id); setTtsProgress(version.tts_progress ?? null); setMessage(version.queued_item_count ? `学习本已保存，正在后台生成 ${version.queued_item_count} 条本地发音。` : '学习本已保存。未配置语音服务时，之后配置完成会自动补生成。'); onConfirm(words, version.word_list_version_id)
      }
      loadSavedLists(); resetEditor()
    } catch { setMessage('保存学习本失败，请稍后重试。') }
  }
  const edit = (list: SavedList) => { setEditingId(list.id); setTitle(list.title); setText(list.items.join('\n')); applyWords(list.items); setSourceType(list.source_type); setMessage(`正在编辑“${list.title}”。保存后会生成新的版本。`) }
  const remove = async (list: SavedList) => { if (!window.confirm(`确定删除学习本“${list.title}”吗？`)) return; try { await api(`/word-lists/${list.id}`, { method: 'DELETE' }); setSavedLists(current => current.filter(item => item.id !== list.id)); setMessage(`学习本“${list.title}”已删除。`); if (editingId === list.id) resetEditor() } catch { setMessage('删除学习本失败，请稍后重试。') } }
  const changePronunciation = async (detail: ItemDetail, pronunciation_source: ItemDetail['pronunciation_source']) => { await api(`/word-items/${detail.id}/pronunciation`, { method: 'PATCH', body: JSON.stringify({ pronunciation_source }) }); setSavedLists(current => current.map(list => ({ ...list, item_details: list.item_details?.map(item => item.id === detail.id ? { ...item, pronunciation_source, audio_ready: false } : item) }))); setMessage(`“${detail.display_text}”正在重新生成发音。`) }
  const workerWarning = !workerOnline && savedLists.some(list => list.tts_progress && list.tts_progress.queued + list.tts_progress.running > 0)
  return <section className="word-editor"><h1>学习本</h1>{workerWarning && <p role="alert">后台处理服务离线，本地发音生成已暂停。重启最新容器后会继续。</p>}{savedLists.length > 0 && <section className="saved-learning-lists"><h2>已保存的学习本</h2>{savedLists.map(list => <article key={list.id}><strong>{list.title} · {sourceLabels[list.source_type]}</strong><p>{list.items.length} 条：{list.items.slice(0, 5).join('、')}{list.items.length > 5 ? '…' : ''}</p>{list.item_details?.map(detail => <label key={detail.id}>{detail.display_text} 发音来源<select aria-label={`${detail.display_text} 发音来源`} value={detail.pronunciation_source} onChange={event => void changePronunciation(detail, event.target.value as ItemDetail["pronunciation_source"])}><option value="default">跟随系统默认</option><option value="configured">原生发音</option><option value="custom">自定义声音</option></select>{!detail.audio_ready && <small>重新生成中</small>}</label>)}{list.tts_progress && <><progress max="100" value={list.tts_progress.progress ?? 0} aria-label={`${list.title} 本地发音进度`} /><p>本地发音：{list.tts_progress.progress ?? 0}%，已完成 {list.tts_progress.ready}/{list.tts_progress.total}，生成中 {list.tts_progress.queued + list.tts_progress.running}，失败 {list.tts_progress.failed}</p></>}<div className="list-actions">{list.word_list_version_id && <Button onClick={() => onConfirm(list.items, list.word_list_version_id!)}>开始默写</Button>}<Button variant="secondary" onClick={() => edit(list)}>编辑</Button><Button variant="danger" onClick={() => void remove(list)}>删除</Button></div></article>)}</section>}<h2>{editingId ? '编辑学习本' : '创建学习本'}</h2><label>学习本名称<input aria-label="学习本名称" value={title} onChange={event => setTitle(event.target.value)} /></label><label htmlFor="word-text">粘贴单词</label><textarea id="word-text" value={text} onChange={event => { setText(event.target.value); setSourceType('paste') }} placeholder={'每行一个单词\n或用逗号分隔'} /><Button onClick={() => applyWords(parse(text))}>整理单词</Button><label htmlFor="spelling-camera">拍照识别拼写测试</label><input id="spelling-camera" aria-label="拍照识别拼写测试" type="file" accept="image/*" capture="environment" onChange={event => void recognizeImage(event)} /><label htmlFor="spelling-library">从照片库选择拼写测试</label><input id="spelling-library" aria-label="从照片库选择拼写测试" type="file" accept="image/*" onChange={event => void recognizeImage(event)} />{ocrReady && <section className="ocr-confirm"><strong>识别结果：{words.length} 个单词</strong><Button onClick={() => void save()}>确认并保存识别结果</Button></section>}<label htmlFor="word-file">上传单词表</label><input id="word-file" type="file" accept=".txt,.csv,.xlsx,.docx,.pdf" onChange={upload} />{message && <p className="import-message" role="status">{message}</p>}{ttsProgress && <p role="status">本地发音：已完成 {ttsProgress.ready}/{ttsProgress.total}，生成中 {ttsProgress.queued + ttsProgress.running}，失败 {ttsProgress.failed}</p>}{words.length > 0 && <div className="word-preview"><h2>确认清单（{words.length}）</h2>{words.map((word, index) => <div className="learning-item-editor" key={`${word}-${index}`}><input aria-label={`单词 ${index + 1}`} value={word} onChange={event => setWords(current => current.map((item, itemIndex) => itemIndex === index ? event.target.value : item))} /><label>条目类型 {index + 1}<select aria-label={`条目类型 ${index + 1}`} value={itemTypes[index] ?? 'word'} onChange={event => setItemTypes(current => current.map((item, itemIndex) => itemIndex === index ? event.target.value as typeof item : item))}><option value="word">单词</option><option value="phrase">短语</option><option value="sentence">句子</option></select></label><label>翻译 {index + 1}<input aria-label={`翻译 ${index + 1}`} value={translations[index] ?? ''} onChange={event => setTranslations(current => current.map((item, itemIndex) => itemIndex === index ? event.target.value : item))} /></label></div>)}<div className="list-actions"><Button onClick={() => void save()}>{editingId ? '保存新版本' : '确认学习本'}</Button>{editingId && <Button variant="secondary" onClick={resetEditor}>取消编辑</Button>}</div></div>}</section>
}
