import { useCallback, useEffect, useState } from "react";
import { api, apiAudio, apiBlob, ApiError } from "./api/client";
import { LoginPage } from "./features/auth/LoginPage";
import { DashboardPage, DashboardSummary } from "./features/dashboard/DashboardPage";
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
  RecordingLanguage,
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
    | "skating"
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
          } catch (error) {
            // 服务端已没有这条录制（被删除或从未创建成功）：清除残留会话，避免永远卡在「继续录制」
            if (error instanceof ApiError && error.status === 404) {
              await recordingStore.removeSession(item.recordingId);
              return null;
            }
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
                          : item === "花滑录制"
                            ? "skating"
                            : "home",
    );
  const recordingDestinations: Record<string, string> = {
    chinese: "中文阅读",
    english: "英文阅读",
    skating: "花滑录制",
  };
  if (screen === "chinese" || screen === "english" || screen === "skating")
    return (
      <AppShell onNavigate={navigate} activeDestination={recordingDestinations[screen]}>
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
    return <UnknownItemsScreen onNavigate={navigate} onStartDictation={(items, versionId) => { setWords(items); setWordListVersionId(versionId); setScreen("dictation"); }} />;
  if (screen === "voices") return <VoicesScreen onNavigate={navigate} />;
  if (screen === "stats") return <StatsScreen onNavigate={navigate} />;
  if (screen === "videos") return <VideosScreen onNavigate={navigate} onDownload={(item) => { setVideoDownload(item); setScreen("download") }} />;
  if (screen === "download" && videoDownload) return <AppShell onNavigate={navigate} activeDestination="视频库"><VideoDownloadPage item={videoDownload} onBackToVideos={() => setScreen("videos")} onHome={() => setScreen("home")} /></AppShell>;
  if (screen === "settings") return <SettingsScreen onNavigate={navigate} />;
  return (
    <HomeScreen
      onNavigate={navigate}
      onRecord={setScreen}
      recoveries={recoveries}
    />
  );
}

const localDate = () => {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
};

function dualStreak(calendar: ReadingStats["calendar"]) {
  // 连续打卡按“中英文都完成”的日子计算；今天还没完成时从昨天起算
  let start = calendar.length - 1;
  const todayKey = localDate();
  if (start < 0) return 0;
  if (calendar[start]?.date === todayKey && !(calendar[start].chinese && calendar[start].english)) start -= 1;
  let streak = 0;
  for (let index = start; index >= 0; index -= 1) {
    if (calendar[index].chinese && calendar[index].english) streak += 1;
    else break;
  }
  return streak;
}

function HomeScreen({
  onNavigate,
  onRecord,
  recoveries,
}: {
  onNavigate: (item: string) => void;
  onRecord: (screen: "chinese" | "english" | "skating") => void;
  recoveries: RecordingSession[];
}) {
  const [summary, setSummary] = useState<DashboardSummary>({
    chinese: "pending",
    english: "pending",
    skating: "pending",
    streak: 0,
    weeklyRate: 0,
  });
  useEffect(() => {
    const load = async () => {
      const recordings = await Promise.resolve(api<RecordingItem[]>("/recordings"))
        .then((value) => (Array.isArray(value) ? value : []))
        .catch(() => []);
      const stats = await Promise.resolve(api<ReadingStats>("/stats/reading?period=week"))
        .then((value) => value ?? null)
        .catch(() => null);
      const today = localDate();
      const stateFor = (language: RecordingLanguage): DashboardSummary["chinese"] => {
        const todays = recordings.filter((item) => item.reading_date === today && item.language_type === language);
        if (todays.some((item) => item.status === "ready")) return "complete";
        if (todays.some((item) => ["recording", "assembling", "transcoding"].includes(item.status))) return "processing";
        return "pending";
      };
      setSummary({
        chinese: stateFor("chinese"),
        english: stateFor("english"),
        skating: stateFor("skating"),
        streak: stats ? dualStreak(stats.calendar) : 0,
        weeklyRate: stats ? Math.round((stats.combined_rate ?? 0) * 100) : 0,
      });
    };
    void load();
  }, []);
  return (
    <AppShell onNavigate={onNavigate} activeDestination="今天">
      <DashboardPage
        summary={summary}
        recoveryLanguage={recoveries[0]?.language}
        onRecord={onRecord}
        onDictation={() => onNavigate("单词本")}
        onOpenVideos={() => onNavigate("视频库")}
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
  const play = async (
    entryId: string,
    options: {
      source: "standard" | "human" | "configured" | "custom";
      voice_version_id?: string;
      regenerate: boolean;
      accent: "uk" | "us";
    },
  ) => {
    const data = await api<{ asset_id: string; source: string }>(
      `/dictionary/entries/${entryId}/audio`,
      {
        method: "POST",
        body: JSON.stringify(options),
      },
    );
    const source = URL.createObjectURL(
      await apiAudio(`/tts-assets/${data.asset_id}/audio`),
    );
    let released = false;
    const release = () => {
      if (released) return;
      released = true;
      URL.revokeObjectURL(source);
    };
    try {
      const audio = new Audio(source);
      audio.addEventListener("ended", release, { once: true });
      await audio.play();
    } catch (error) {
      release();
      throw error;
    }
    return data.source as
      | "standard_audio"
      | "human_recording"
      | "configured_tts"
      | "voice_clone";
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
        onStreamPlay={(text) =>
          new Audio(`/api/tts/stream?text=${encodeURIComponent(text)}`).play()
        }
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
  onStartDictation,
}: {
  onNavigate: (item: string) => void;
  onStartDictation: (items: string[], versionId: string) => void;
}) {
  const load = ({
    status,
    item_type,
    sort = "recent",
  }: {
    status: "unknown" | "mastered";
    item_type: "all" | UnknownItem["item_type"];
    sort?: "recent" | "importance";
  }) => {
    const params = new URLSearchParams({ status });
    if (item_type !== "all") params.set("item_type", item_type);
    params.set("sort", sort);
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
        onCreateLearningList={(unknown_item_ids, title) =>
          api("/learning-lists/from-unknown-items", {
            method: "POST",
            body: JSON.stringify({ unknown_item_ids, title }),
          })
        }
        onLoadLearningLists={() => api("/word-lists?source_type=unknown_items")}
        onConfirmLearningList={async (id) => {
          const result = await api<{ learning_list_version_id: string }>(`/learning-lists/${id}/confirm`, { method: "POST" });
          return { word_list_version_id: result.learning_list_version_id };
        }}
        onStartDictation={onStartDictation}
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
        onTestTts={(value) => api("/settings/tts/test", {
          method: "POST",
          body: JSON.stringify(value),
        })}
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
        onUpload={async ({ file, readingDate, languageType }) => {
          const body = new FormData();
          body.set("file", file);
          body.set("reading_date", readingDate);
          body.set("language_type", languageType);
          await api("/recordings/upload", { method: "POST", body });
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
