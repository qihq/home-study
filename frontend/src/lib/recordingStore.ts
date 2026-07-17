export type PendingChunk = { recordingId: string; sequence: number; blob: Blob }
export type RecordingSession = {
  recordingId: string
  language: 'chinese' | 'english'
  nextSequence: number
  ended: boolean
}

export interface RecordingStore {
  put(recordingId: string, sequence: number, blob: Blob): Promise<void>
  get(recordingId: string, sequence: number): Promise<Blob | undefined>
  acknowledge(recordingId: string, sequence: number): Promise<void>
  list(recordingId: string): Promise<PendingChunk[]>
  putSession(session: RecordingSession): Promise<void>
  getSession(recordingId: string): Promise<RecordingSession | undefined>
  listSessions(): Promise<RecordingSession[]>
  removeSession(recordingId: string): Promise<void>
}

export function createMemoryRecordingStore(): RecordingStore {
  const values = new Map<string, Blob>()
  const sessions = new Map<string, RecordingSession>()
  const key = (recordingId: string, sequence: number) => `${recordingId}:${sequence}`
  return {
    async put(recordingId, sequence, blob) { values.set(key(recordingId, sequence), blob) },
    async get(recordingId, sequence) { return values.get(key(recordingId, sequence)) },
    async acknowledge(recordingId, sequence) { values.delete(key(recordingId, sequence)) },
    async list(recordingId) {
      return [...values.entries()].flatMap(([entry, blob]) => {
        const [id, sequence] = entry.split(':')
        return id === recordingId ? [{ recordingId: id, sequence: Number(sequence), blob }] : []
      })
    },
    async putSession(session) { sessions.set(session.recordingId, { ...session }) },
    async getSession(recordingId) { return sessions.get(recordingId) },
    async listSessions() { return [...sessions.values()] },
    async removeSession(recordingId) { sessions.delete(recordingId) },
  }
}

export function createIndexedDbRecordingStore(databaseName = 'family-learning-recordings'): RecordingStore {
  const open = () => new Promise<IDBDatabase>((resolve, reject) => {
    const request = indexedDB.open(databaseName, 2)
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains('chunks')) request.result.createObjectStore('chunks', { keyPath: ['recordingId', 'sequence'] })
      if (!request.result.objectStoreNames.contains('sessions')) request.result.createObjectStore('sessions', { keyPath: 'recordingId' })
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
  const transaction = async <T>(mode: IDBTransactionMode, run: (store: IDBObjectStore) => IDBRequest<T>) => {
    const database = await open()
    return new Promise<T | undefined>((resolve, reject) => {
      const request = run(database.transaction('chunks', mode).objectStore('chunks'))
      request.onsuccess = () => resolve(request.result)
      request.onerror = () => reject(request.error)
    }).finally(() => database.close())
  }
  return {
    async put(recordingId, sequence, blob) { await transaction('readwrite', store => store.put({ recordingId, sequence, blob })) },
    async get(recordingId, sequence) { return transaction<PendingChunk>('readonly', store => store.get([recordingId, sequence])).then(item => item?.blob) },
    async acknowledge(recordingId, sequence) { await transaction('readwrite', store => store.delete([recordingId, sequence])) },
    async list(recordingId) {
      const database = await open()
      return new Promise<PendingChunk[]>((resolve, reject) => {
        const request = database.transaction('chunks', 'readonly').objectStore('chunks').getAll()
        request.onsuccess = () => resolve((request.result as PendingChunk[]).filter(item => item.recordingId === recordingId).sort((a, b) => a.sequence - b.sequence))
        request.onerror = () => reject(request.error)
      }).finally(() => database.close())
    },
    async putSession(session) {
      const database = await open()
      await new Promise<void>((resolve, reject) => {
        const request = database.transaction('sessions', 'readwrite').objectStore('sessions').put(session)
        request.onsuccess = () => resolve()
        request.onerror = () => reject(request.error)
      }).finally(() => database.close())
    },
    async getSession(recordingId) {
      const database = await open()
      return new Promise<RecordingSession | undefined>((resolve, reject) => {
        const request = database.transaction('sessions', 'readonly').objectStore('sessions').get(recordingId)
        request.onsuccess = () => resolve(request.result as RecordingSession | undefined)
        request.onerror = () => reject(request.error)
      }).finally(() => database.close())
    },
    async listSessions() {
      const database = await open()
      return new Promise<RecordingSession[]>((resolve, reject) => {
        const request = database.transaction('sessions', 'readonly').objectStore('sessions').getAll()
        request.onsuccess = () => resolve(request.result as RecordingSession[])
        request.onerror = () => reject(request.error)
      }).finally(() => database.close())
    },
    async removeSession(recordingId) {
      const database = await open()
      await new Promise<void>((resolve, reject) => {
        const request = database.transaction('sessions', 'readwrite').objectStore('sessions').delete(recordingId)
        request.onsuccess = () => resolve()
        request.onerror = () => reject(request.error)
      }).finally(() => database.close())
    },
  }
}
