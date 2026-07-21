import { useCallback, useEffect, useState } from "react";
import { api, apiAudio, apiBlob } from "./api/client";
import { LoginPage } from "./features/auth/LoginPage";
import { DashboardPage } from "./features/dashboard/DashboardPage";
import { RecordingPage } from "./features/recording/RecordingPage";
import { DictationPage } from "./features/dictation/DictationPage";
import { WordListEditor } from "./features/words/WordListEditor";
import {
  ReadingStats,
  ReadingStatsPage,
} from "./features/stats/ReadingStatsPage";
import { RecordingItem, VideoLibrary } from "./features/recording/VideoLibrary";
import { VideoDownloadItem, VideoDownloadPage } from "./features/recording/VideoDownloadPage";
import {
  FailedTask,
  SettingsPage,
  TtsConfig,
} from "./features/settings/SettingsPage";
import { AiConfig } from "./features/settings/AiSettingsPanel";
import { SpellingOcrConfig } from "./features/settings/SpellingOcrSettingsPanel";
import { DictionaryPage } from "./features/dictionary/DictionaryPage";
import { DictionaryResult } from "./features/dictionary/DictionaryResultCard";
import {
  UnknownItem,
  UnknownItemsPage,
} from "./features/dictionary/UnknownItemsPage";
import {
  SpeakerProfileView,
  SpeakerProfilesPage,
  VoiceVersionView,
} from "./features/voices/SpeakerProfilesPage";
import { VoicePackageDialog } from "./features/voices/VoicePackageDialog";
import {
  DictationStats,
  DictationStatsPage,
  Mistake,
} from "./features/stats/DictationStatsPage";
import { AppShell } from "./ui/AppShell";
import {
  RecordingSession,
  createIndexedDbRecordingStore,
} from "./lib/recordingStore";

const recordingStore = createIndexedDbRecordingStore();

function useWorkerHealth() {
  const [online, setOnline] = useState(true);
  useEffect(() => {
    const refresh = () =>
      void api<{ worker?: boolean }>("/health")
        .then((value) => setOnline(value.worker !== false))
        .catch(() => setOnline(false));
    refresh();
    const timer = window.setInterval(refresh, 5000);
    return () => window.clearInterval(timer);
  }, []);
  return online;
}

export function App() {
  const [authenticated, setAuthenticated] = useState(false);
  const [firstRun, setFirstRun] = useState<boolean | null>(null);
  const [screen, setScreen] = useState<
    | "home"
    | "chinese"
    | "english"
    | "words"
    | "dictation"
    | "stats"
    | "videos"
    | "download"
    | "settings"
    | "dictionary"
    | "unknown-items"
    | "voices"
  >("home");
  const [words, setWords] = useState<string[]>([]);
  const [wordListVersionId, setWordListVersionId] = useState<
    string | undefined
  >();
  const [recoveries, setRecoveries] = useState<RecordingSession[]>([]);
  const [videoDownload, setVideoDownload] = useState<VideoDownloadItem | null>(null);
  useEffect(() => {
    void api<{ needs_initial_admin: boolean }>("/setup/status")
      .then((state) => setFirstRun(state.needs_initial_admin))
      .catch(() => setFirstRun(false));
  }, []);
  useEffect(() => {
    if (!authenticated) return;
    void recordingStore.listSessions().then(async (sessions) => {
      const active = await Promise.all(
        sessions.map(async (item) => {
          try {
            const status = await api<{ status: string }>(
              `/recordings/${item.recordingId}/chunks`,
            );
            if (
              ["assembling", "transcoding", "ready", "abandoned"].includes(
                status.status,
              )
            ) {
              await recordingStore.removeSession(item.recordingId);
              return null;
            }
          } catch {
            return item;
          }
          return item;
        }),
      );
      setRecoveries(
        active.filter((item): item is RecordingSession => item !== null),
      );
    });
  }, [authenticated]);
  if (!authenticated)
    return firstRun === null ? (
      <main className="login-page">正在连接家庭学习助手…</main>
    ) : (
      <LoginPage
        firstRun={firstRun}
        onLoggedIn={() => setAuthenticated(true)}
      />
    );
  const navigate = (item: string) =>
    setScreen(
      item === "统计"
        ? "stats"
        : item === "单词默写"
          ? "dictation"
          : item === "单词本" || item === "学习本"
            ? "words"
            : item === "生词本"
              ? "unknown-items"
              : item === "我的声音"
                ? "voices"
                : item === "辞典"
                  ? "dictionary"
                  : item === "视频库"
                    ? "videos"
                    : item === "设置"
                      ? "settings"
                      : item === "中文阅读"
                        ? "chinese"
                        : item === "英文阅读"
                          ? "english"
                          : "home",
    );
  if (screen === "chinese" || screen === "english")
    return (
      <AppShell onNavigate={navigate} activeDestination={screen === "chinese" ? "中文阅读" : "英文阅读"}>
        <RecordingPage
          language={screen}
          recovery={recoveries.find((item) => item.language === screen)}
          onHome={() => setScreen("home")}
          onOpenVideos={() => setScreen("videos")}
          onBack={() => {
            void recordingStore.listSessions().then(setRecoveries);
            setScreen("home");
          }}
        />
      </AppShell>
    );
  if (screen === "words")
    return (
      <AppShell onNavigate={navigate} activeDestination="学习本">
        <WordListEditor
          onConfirm={(items, versionId) => {
            setWords(items);
            setWordListVersionId(versionId);
            setScreen("dictation");
          }}
        />
      </AppShell>
    );
  if (screen === "dictation")
    return (
      <DictationScreen
        onNavigate={navigate}
        words={words}
        wordListVersionId={wordListVersionId}
      />
    );
  if (screen === "dictionary")
    return <DictionaryScreen onNavigate={navigate} />;
  if (screen === "unknown-items")
    return <UnknownItemsScreen onNavigate={navigate} />;
  if (screen === "voices") return <VoicesScreen onNavigate={navigate} />;
  if (screen === "stats") return <StatsScreen onNavigate={navigate} />;
  if (screen === "videos") return <VideosScreen onNavigate={navigate} onDownload={(item) => { setVideoDownload(item); setScreen("download") }} />;
  if (screen === "download" && videoDownload) return <AppShell onNavigate={navigate} activeDestination="视频库"><VideoDownloadPage item={videoDownload} onBackToVideos={() => setScreen("videos")} onHome={() => setScreen("home")} /></AppShell>;
  if (screen === "settings") return <SettingsScreen onNavigate={navigate} />;
  return (
    <AppShell onNavigate={navigate} activeDestination="今天">
      <DashboardPage
        summary={{
          chinese: "pending",
          english: "pending",
          streak: 0,
          weeklyRate: 0,
        }}
        recoveryLanguage={recoveries[0]?.language}
        onRecord={setScreen}
        onDictation={() => setScreen("words")}
      />
    </AppShell>
  );
}

function DictationScreen({
  onNavigate,
  words,
  wordListVersionId,
}: {
  onNavigate: (item: string) => void;
  words: string[];
  wordListVersionId?: string;
}) {
  const [speakers, setSpeakers] = useState<
    Array<{ id: string; display_name: string }>
  >([]);
  const [voices, setVoices] = useState<
    Array<{
      id: string;
      speaker_profile_id: string;
      display_name: string;
      status: string;
    }>
  >([]);
  useEffect(() => {
    void Promise.all([
      api<Array<{ id: string; display_name: string }>>("/speaker-profiles"),
      api<
        Array<{
          id: string;
          speaker_profile_id: string;
          display_name: string;
          status: string;
        }>
      >("/voice-versions?ready=true&include_selection_metadata=true"),
    ])
      .then(([loadedSpeakers, loadedVoices]) => {
        setSpeakers(loadedSpeakers);
        setVoices(loadedVoices);
      })
      .catch(() => {
        setSpeakers([]);
        setVoices([]);
      });
  }, []);
  const [savedLists, setSavedLists] = useState<
    Array<{
      title: string;
      items: string[];
      word_list_version_id: string | null;
    }>
  >([]);
  const [resume, setResume] = useState<{
    id: string;
    words: string[];
    word_list_version_id: string;
  } | null>(null);
  useEffect(() => {
    void api<
      Array<{
        title: string;
        items: string[];
        word_list_version_id: string | null;
      }>
    >("/word-lists")
      .then((value) => setSavedLists(Array.isArray(value) ? value : []))
      .catch(() => setSavedLists([]));
    void api<{
      id: string;
      words: string[];
      word_list_version_id: string;
    } | null>("/dictation/latest-in-progress")
      .then(setResume)
      .catch(() => setResume(null));
  }, []);
  const [selected, setSelected] = useState<{
    words: string[];
    version?: string;
    sessionId?: string;
  }>({ words, version: wordListVersionId });
  return (
    <AppShell onNavigate={onNavigate} activeDestination="单词默写">
      <section className="dictation-picker">
        <h1>单词默写</h1>
        <label>
          选择学习本
          <select
            aria-label="选择学习本"
            value={selected.version ?? ""}
            onChange={(event) => {
              const list = savedLists.find(
                (item) => item.word_list_version_id === event.target.value,
              );
              if (list?.word_list_version_id)
                setSelected({
                  words: list.items,
                  version: list.word_list_version_id,
                });
            }}
          >
            <option value="">选择已保存学习本</option>
            {savedLists
              .filter((item) => item.word_list_version_id)
              .map((list) => (
                <option
                  key={list.word_list_version_id}
                  value={list.word_list_version_id!}
                >
                  {list.title}
                </option>
              ))}
          </select>
        </label>
        {resume && (
          <button
            onClick={() =>
              setSelected({
                words: resume.words,
                version: resume.word_list_version_id,
                sessionId: resume.id,
              })
            }
          >
            返回上次未完成默写
          </button>
        )}
      </section>
      {selected.version && (
        <DictationPage
          key={selected.sessionId ?? selected.version}
          words={selected.words}
          wordListVersionId={selected.version}
          resumeSessionId={selected.sessionId}
          onScore={() => undefined}
          speakers={speakers}
          voices={voices}
        />
      )}
    </AppShell>
  );
}

function DictionaryScreen({
  onNavigate,
}: {
  onNavigate: (item: string) => void;
}) {
  const [voices, setVoices] = useState<
    Array<{ id: string; display_name: string }>
  >([]);
  useEffect(() => {
    void api<Array<{ id: string; display_name: string }>>(
      "/voice-versions?ready=true",
    )
      .then(setVoices)
      .catch(() => setVoices([]));
  }, []);
  const play = async (entryId: string, voiceVersionId?: string, regenerate = false) => {
    const { asset_id } = await api<{ asset_id: string }>(
      `/dictionary/entries/${entryId}/audio`,
      {
        method: "POST",
        body: JSON.stringify(regenerate ? { voice_version_id: voiceVersionId || null, regenerate: true } : { voice_version_id: voiceVersionId || null }),
      },
    );
    const source = URL.createObjectURL(
      await apiAudio(`/tts-assets/${asset_id}/audio`),
    );
    const audio = new Audio(source);
    audio.addEventListener("ended", () => URL.revokeObjectURL(source), {
      once: true,
    });
    await audio.play();
  };
  return (
    <AppShell onNavigate={onNavigate} activeDestination="辞典">
      <DictionaryPage
        voices={voices}
        onLookup={(request) =>
          api<DictionaryResult>("/dictionary/lookup", {
            method: "POST",
            body: JSON.stringify(request),
          })
        }
        onPlay={play}
        onMarkUnknown={(entryId) =>
          api(`/dictionary/entries/${entryId}/mark-unknown`, { method: "POST" })
        }
        onOpenUnknownItems={() => onNavigate("生词本")}
      />
    </AppShell>
  );
}

function UnknownItemsScreen({
  onNavigate,
}: {
  onNavigate: (item: string) => void;
}) {
  const load = ({
    status,
    item_type,
  }: {
    status: "unknown" | "mastered";
    item_type: "all" | UnknownItem["item_type"];
  }) => {
    const params = new URLSearchParams({ status });
    if (item_type !== "all") params.set("item_type", item_type);
    return api<UnknownItem[]>(`/unknown-items?${params}`);
  };
  return (
    <AppShell onNavigate={onNavigate} activeDestination="生词本">
      <UnknownItemsPage
        onLoad={load}
        onUpdateStatus={(id, status) =>
          api(`/unknown-items/${id}`, {
            method: "PATCH",
            body: JSON.stringify({ status }),
          })
        }
        onCreateLearningList={(unknown_item_ids) =>
          api("/learning-lists/from-unknown-items", {
            method: "POST",
            body: JSON.stringify({ unknown_item_ids }),
          })
        }
        onDelete={(id) => api(`/unknown-items/${id}`, { method: "DELETE" })}
      />
    </AppShell>
  );
}

function SettingsScreen({
  onNavigate,
}: {
  onNavigate: (item: string) => void;
}) {
  const [config, setConfig] = useState<TtsConfig | null>(null);
  const [aiConfig, setAiConfig] = useState<AiConfig | null>(null);
  const [spellingOcrConfig, setSpellingOcrConfig] =
    useState<SpellingOcrConfig | null>(null);
  const [failedTasks, setFailedTasks] = useState<FailedTask[]>([]);
  const [readyVoices, setReadyVoices] = useState<
    Array<{ id: string; display_name: string }>
  >([]);
  useEffect(() => {
    void Promise.all([
      api<TtsConfig>("/settings/tts"),
      api<AiConfig>("/settings/ai"),
    ]).then(([tts, ai]) => {
      setConfig(tts);
      setAiConfig(ai);
    });
    void api<SpellingOcrConfig>("/settings/spelling-ocr")
      .then(setSpellingOcrConfig)
      .catch(() => setSpellingOcrConfig(null));
    void api<FailedTask[]>("/settings/failed-tasks")
      .then(setFailedTasks)
      .catch(() => setFailedTasks([]));
    void api<Array<{ id: string; display_name: string }>>(
      "/voice-versions?ready=true",
    )
      .then(setReadyVoices)
      .catch(() => setReadyVoices([]));
  }, []);
  if (!config)
    return (
      <AppShell onNavigate={onNavigate} activeDestination="设置">
        <p>正在加载设置…</p>
      </AppShell>
    );
  return (
    <AppShell onNavigate={onNavigate} activeDestination="设置">
      <SettingsPage
        config={config}
        readyVoices={readyVoices}
        onBackup={() => {
          void api("/settings/backup", { method: "POST" });
        }}
        onSave={async (value) => {
          const saved = await api<TtsConfig>("/settings/tts", {
            method: "PATCH",
            body: JSON.stringify(value),
          });
          setConfig(saved);
        }}
        aiConfig={aiConfig ?? undefined}
        onSaveAi={async (value) => {
          const saved = await api<AiConfig>("/settings/ai", {
            method: "PATCH",
            body: JSON.stringify(value),
          });
          setAiConfig(saved);
        }}
        onTestAi={() => api("/settings/ai/test", { method: "POST" })}
        spellingOcrConfig={spellingOcrConfig ?? undefined}
        onSaveSpellingOcr={async (value) => {
          const saved = await api<SpellingOcrConfig>("/settings/spelling-ocr", {
            method: "PATCH",
            body: JSON.stringify(value),
          });
          setSpellingOcrConfig(saved);
        }}
        onTestSpellingOcr={() =>
          api("/settings/spelling-ocr/test", { method: "POST" })
        }
        onOpenVoices={() => onNavigate("我的声音")}
        failedTasks={failedTasks}
        onRetryTask={async (id) => {
          await api(`/settings/failed-tasks/${id}/retry`, { method: "POST" });
          setFailedTasks((current) => current.filter((task) => task.id !== id));
        }}
      />
    </AppShell>
  );
}

function VoicesScreen({ onNavigate }: { onNavigate: (item: string) => void }) {
  const [profiles, setProfiles] = useState<SpeakerProfileView[]>([]);
  const [packageSpeakerId, setPackageSpeakerId] = useState<string | null>(null);
  const workerOnline = useWorkerHealth();
  const load = async () => {
    const [speakers, versions] = await Promise.all([
      api<
        Array<{
          id: string;
          display_name: string;
          default_voice_version_id: string | null;
        }>
      >("/speaker-profiles"),
      api<Array<VoiceVersionView & { speaker_profile_id: string }>>(
        "/voice-versions?ready=false",
      ),
    ]);
    setProfiles(
      speakers.map((speaker) => ({
        ...speaker,
        versions: versions
          .filter((version) => version.speaker_profile_id === speaker.id)
          .map((version) => ({
            ...version,
            display_name:
              version.display_name.split(" / ").at(-1) ?? version.display_name,
            is_default: version.id === speaker.default_voice_version_id,
          })),
      })),
    );
  };
  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 5000);
    return () => window.clearInterval(timer);
  }, []);
  const preview = async (voiceId: string) => {
    const source = URL.createObjectURL(
      await apiAudio(`/voice-versions/${voiceId}/preview`),
    );
    const audio = new Audio(source);
    audio.addEventListener("ended", () => URL.revokeObjectURL(source), {
      once: true,
    });
    await audio.play();
  };
  const inspectPackage = (file: File, password: string) => {
    const body = new FormData();
    body.set("file", file);
    body.set("password", password);
    return api<{
      import_id: string;
      conflicts: Array<{ speaker_profile_id: string }>;
    }>("/speaker-profiles/import/inspect", { method: "POST", body });
  };
  const exportPackage = async (password: string) => {
    if (!packageSpeakerId) return;
    const profile = profiles.find((item) => item.id === packageSpeakerId);
    if (!profile) return;
    const archive = await apiBlob(`/speaker-profiles/${profile.id}/export`, {
      method: "POST",
      body: JSON.stringify({
        password,
        voice_version_ids: profile.versions
          .filter((version) => version.status === "ready")
          .map((version) => version.id),
      }),
    });
    const url = URL.createObjectURL(archive);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${profile.display_name}-voices.flvoice`;
    link.click();
    URL.revokeObjectURL(url);
  };
  const uploadRecorded = async (speakerId: string, audio: Blob) => {
    const body = new FormData();
    body.set(
      "file",
      new File([audio], "recording.webm", { type: audio.type || "audio/webm" }),
    );
    body.set("consent_confirmed", "true");
    await api(`/speaker-profiles/${speakerId}/voice-versions/upload`, {
      method: "POST",
      body,
    });
    await load();
  };
  return (
    <AppShell onNavigate={onNavigate} activeDestination="我的声音">
      <SpeakerProfilesPage
        profiles={profiles}
        workerOnline={workerOnline}
        onPreview={(voiceId) => {
          void preview(voiceId);
        }}
        onMakeDefault={async (voiceId) => {
          await api(`/voice-versions/${voiceId}/make-default`, {
            method: "POST",
          });
          await load();
        }}
        onRenameVoice={async (voiceId, display_name) => {
          await api(`/voice-versions/${voiceId}`, {
            method: "PATCH",
            body: JSON.stringify({ display_name }),
          });
          await load();
        }}
        onDeleteVoice={async (voiceId) => {
          await api(`/voice-versions/${voiceId}`, { method: "DELETE" });
          await load();
        }}
        onDeleteSpeaker={async (speakerId) => {
          await api(`/speaker-profiles/${speakerId}`, { method: "DELETE" });
          await load();
        }}
        onOpenPackage={setPackageSpeakerId}
        onRecorded={uploadRecorded}
      />
      {packageSpeakerId && (
        <VoicePackageDialog
          onExport={(password) => {
            void exportPackage(password);
          }}
          onInspect={inspectPackage}
          onCommit={(value) => {
            void api("/speaker-profiles/import/commit", {
              method: "POST",
              body: JSON.stringify(value),
            }).then(() => {
              setPackageSpeakerId(null);
              void load();
            });
          }}
        />
      )}
    </AppShell>
  );
}

function VideosScreen({ onNavigate, onDownload }: { onNavigate: (item: string) => void; onDownload: (item: VideoDownloadItem) => void }) {
  const [videos, setVideos] = useState<RecordingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const workerOnline = useWorkerHealth();
  const load = useCallback((background = false) => {
    if (!background) setLoading(true);
    setLoadError(null);
    return api<RecordingItem[]>("/recordings")
      .then(setVideos)
      .catch(() => setLoadError("请检查网络或稍后再试，已有视频没有被删除。"))
      .finally(() => { if (!background) setLoading(false) });
  }, []);
  useEffect(() => { void load() }, [load]);
  const hasPendingWork = videos.some(video => ["assembling", "transcoding"].includes(video.status));
  useEffect(() => {
    if (!hasPendingWork) return;
    const timer = window.setInterval(() => void load(true), 5000);
    return () => window.clearInterval(timer);
  }, [hasPendingWork, load]);
  return (
    <AppShell onNavigate={onNavigate} activeDestination="视频库">
      <VideoLibrary
        recordings={videos}
        loading={loading}
        loadError={loadError}
        onRetry={() => void load()}
        workerOnline={workerOnline}
        onMakeOfficial={(id) => {
          void api(`/recordings/${id}/make-official`, { method: "POST" }).then(
            () => load(),
          );
        }}
        onRename={async (id, title) => {
          await api(`/recordings/${id}`, {
            method: "PATCH",
            body: JSON.stringify({ title }),
          });
          load();
        }}
        onDelete={async (id) => {
          await api(`/recordings/${id}`, { method: "DELETE" });
          load();
        }}
        onRetryProcessing={async (id) => {
          await api(`/recordings/${id}/retry`, { method: "POST" });
          await load(true);
        }}
        onDownload={onDownload}
      />
    </AppShell>
  );
}

function StatsScreen({ onNavigate }: { onNavigate: (item: string) => void }) {
  const [stats, setStats] = useState<ReadingStats | null>(null);
  const [dictation, setDictation] = useState<DictationStats | null>(null);
  const [mistakes, setMistakes] = useState<Mistake[]>([]);
  useEffect(() => {
    void api<ReadingStats>("/stats/reading?period=month")
      .then(setStats)
      .catch(() =>
        setStats({
          combined_rate: 0,
          current_dual_streak: 0,
          chinese: { duration_ms: 0 },
          english: { duration_ms: 0 },
          calendar: [],
        }),
      );
  }, []);
  useEffect(() => {
    void api<DictationStats>("/stats/dictation").then(setDictation);
    void api<Mistake[]>("/stats/mistakes").then(setMistakes);
  }, []);
  return (
    <AppShell onNavigate={onNavigate} activeDestination="统计">
      {stats && dictation ? (
        <>
          <ReadingStatsPage stats={stats} />
          <DictationStatsPage
            stats={dictation}
            mistakes={mistakes}
            onReview={(words) => {
              void api("/review-lists/from-mistakes", {
                method: "POST",
                body: JSON.stringify({ normalized_words: words }),
              });
            }}
          />
        </>
      ) : (
        <p>正在加载统计…</p>
      )}
    </AppShell>
  );
}
