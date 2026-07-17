import { createMemoryRecordingStore } from './recordingStore'

it('removes a blob only after matching server acknowledgement', async () => {
  const store = createMemoryRecordingStore()
  await store.put('r1', 0, new Blob(['chunk']))
  await store.acknowledge('r1', 0)
  await expect(store.get('r1', 0)).resolves.toBeUndefined()
})

it('keeps recording session metadata after all acknowledged chunks are removed', async () => {
  const store = createMemoryRecordingStore()
  await store.putSession({ recordingId: 'r1', language: 'english', nextSequence: 2, ended: true })
  await store.put('r1', 0, new Blob(['chunk']))
  await store.acknowledge('r1', 0)

  await expect(store.listSessions()).resolves.toEqual([
    { recordingId: 'r1', language: 'english', nextSequence: 2, ended: true },
  ])
})
