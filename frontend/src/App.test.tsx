import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { api, apiAudio, apiBlob } from "./api/client";
import { App } from "./App";
import { AppShell } from "./ui/AppShell";

vi.mock("./api/client", () => ({
  api: vi.fn(),
  apiAudio: vi.fn(),
  apiBlob: vi.fn(),
}));
vi.mock("./features/auth/LoginPage", () => ({
  LoginPage: ({ onLoggedIn }: { onLoggedIn: () => void }) => (
    <button onClick={onLoggedIn}>登录</button>
  ),
}));
vi.mock("./lib/recordingStore", () => ({
  createIndexedDbRecordingStore: () => ({ listSessions: async () => [] }),
}));

class TestAudio {
  addEventListener() {}
  play = vi.fn().mockResolvedValue(undefined);
}

vi.stubGlobal("Audio", TestAudio);
vi.stubGlobal("URL", {
  createObjectURL: vi.fn(() => "blob:test"),
  revokeObjectURL: vi.fn(),
});

it("groups mobile navigation into four clear entries and keeps settings reachable", async () => {
  const user = userEvent.setup();
  const onNavigate = vi.fn();

  render(
    <AppShell onNavigate={onNavigate}>
      <p>内容</p>
    </AppShell>,
  );
  const mobileNavigation = screen
    .getAllByRole("navigation")
    .find((element) => element.classList.contains("bottom-nav"));

  expect(mobileNavigation).toBeDefined();
  expect(within(mobileNavigation!).getAllByRole("button")).toHaveLength(4);
  await user.click(
    within(mobileNavigation!).getByRole("button", { name: "我的" }),
  );
  const mobileMenu = screen.getByRole("region", { name: "我的功能" });
  await user.click(within(mobileMenu).getByRole("button", { name: "设置" }));

  expect(onNavigate).toHaveBeenCalledWith("设置");
});

const ttsConfig = {
  protocol: "mimo" as const,
  base_url: "https://tts.example/v1",
  model: "tts-model",
  voice: "voice",
  speed: 1,
  api_key_configured: false,
  api_key_mask: null,
};
const aiConfig = {
  protocol: "openai_chat_compatible" as const,
  display_name: "Dictionary AI",
  base_url: "https://ai.example/v1",
  model: "dictionary-model",
  temperature: 0.1,
  timeout_seconds: 45,
  enabled: true,
  api_key_configured: true,
  api_key_mask: "********abcd",
};

it("wires the dictionary and AI settings pages to their API endpoints", async () => {
  const user = userEvent.setup();
  const mockedApi = vi.mocked(api);
  const mockedApiAudio = vi.mocked(apiAudio);
  mockedApiAudio.mockResolvedValue(new Blob(["wav"], { type: "audio/wav" }));
  mockedApi.mockImplementation(async (path: string) => {
    if (path === "/setup/status") return { needs_initial_admin: false };
    if (path === "/settings/tts") return ttsConfig;
    if (path === "/settings/ai") return aiConfig;
    if (path === "/dictionary/lookup")
      return {
        entry_id: "entry-1",
        source_language: "en",
        target_language: "zh",
        item_type: "word",
        source_text: "apple",
        primary_translation: "苹果",
        phonetic: null,
        parts_of_speech: [],
        alternatives: [],
        examples: [],
        usage_note: null,
        cache_hit: false,
      };
    if (path === "/settings/ai/test")
      return {
        ok: true,
        display_name: "Dictionary AI",
        model: "dictionary-model",
        latency_ms: 12,
      };
    if (path === "/dictionary/entries/entry-1/mark-unknown")
      return { id: "unknown-1", status: "unknown" };
    if (path === "/voice-versions?ready=true")
      return [{ id: "voice-1", display_name: "妈妈 / 清晰美音" }];
    if (path === "/dictionary/entries/entry-1/audio")
      return { asset_id: "asset-1" };
    throw new Error(`Unexpected API call: ${path}`);
  });

  render(<App />);
  await user.click(await screen.findByRole("button", { name: "登录" }));

  await user.click((await screen.findAllByRole("button", { name: "辞典" }))[0]);
  await user.type(screen.getByLabelText("查询内容"), "apple");
  await user.click(screen.getByRole("button", { name: "查询" }));
  expect(await screen.findByText("苹果")).toBeVisible();
  expect(mockedApi).toHaveBeenCalledWith("/dictionary/lookup", {
    method: "POST",
    body: JSON.stringify({ text: "apple", source_language: "auto" }),
  });
  await user.click(screen.getByRole("button", { name: "标记不认识" }));
  expect(mockedApi).toHaveBeenCalledWith(
    "/dictionary/entries/entry-1/mark-unknown",
    { method: "POST" },
  );
  await user.selectOptions(screen.getByLabelText("朗读声音"), "voice-1");
  await user.click(screen.getByRole("button", { name: "播放英文" }));
  expect(mockedApi).toHaveBeenCalledWith("/dictionary/entries/entry-1/audio", {
    method: "POST",
    body: JSON.stringify({ voice_version_id: "voice-1" }),
  });
  expect(mockedApiAudio).toHaveBeenCalledWith("/tts-assets/asset-1/audio");

  await user.click(screen.getAllByRole("button", { name: "设置" })[0]);
  expect(
    await screen.findByRole("heading", { name: "电子辞典 AI" }),
  ).toBeVisible();
  await user.type(screen.getByLabelText("AI API Key"), "replacement-secret");
  await user.click(screen.getByRole("button", { name: "保存 AI 配置" }));
  expect(mockedApi).toHaveBeenCalledWith(
    "/settings/ai",
    expect.objectContaining({
      method: "PATCH",
      body: expect.stringContaining("replacement-secret"),
    }),
  );
  expect(screen.getByLabelText("AI API Key")).toHaveValue("");
  await user.click(screen.getByRole("button", { name: "测试连接" }));
  expect(mockedApi).toHaveBeenCalledWith("/settings/ai/test", {
    method: "POST",
  });
});

it("opens the unknown-items page from the dictionary and creates a learning list", async () => {
  const user = userEvent.setup();
  const mockedApi = vi.mocked(api);
  mockedApi.mockImplementation(async (path: string) => {
    if (path === "/setup/status") return { needs_initial_admin: false };
    if (path === "/voice-versions?ready=true") return [];
    if (path === "/unknown-items?status=unknown")
      return [
        {
          id: "unknown-1",
          item_type: "word",
          source_text: "apple",
          translation_text: "苹果",
          status: "unknown",
        },
      ];
    if (path === "/learning-lists/from-unknown-items")
      return { id: "list-1", status: "draft" };
    throw new Error(`Unexpected API call: ${path}`);
  });

  render(<App />);
  await user.click(await screen.findByRole("button", { name: "登录" }));
  await user.click((await screen.findAllByRole("button", { name: "辞典" }))[0]);
  await user.click(screen.getByRole("button", { name: "查看生词本" }));
  expect(await screen.findByText("apple")).toBeVisible();
  await user.click(screen.getByLabelText("选择 apple"));
  await user.click(screen.getByRole("button", { name: "创建学习列表（1）" }));
  expect(mockedApi).toHaveBeenCalledWith("/learning-lists/from-unknown-items", {
    method: "POST",
    body: JSON.stringify({ unknown_item_ids: ["unknown-1"] }),
  });
});

it("requests voice selection metadata for dictation", async () => {
  const user = userEvent.setup();
  const mockedApi = vi.mocked(api);
  mockedApi.mockImplementation(async (path: string) => {
    if (path === "/setup/status") return { needs_initial_admin: false };
    if (path === "/word-lists") return { id: "list-1" };
    if (path === "/word-lists/list-1/confirm")
      return { word_list_version_id: "version-1" };
    if (path === "/speaker-profiles") return [];
    if (path === "/voice-versions?ready=true&include_selection_metadata=true")
      return [];
    throw new Error(`Unexpected API call: ${path}`);
  });

  render(<App />);
  await user.click(await screen.findByRole("button", { name: "登录" }));
  await user.click(screen.getAllByRole("button", { name: "学习本" })[0]);
  await user.type(screen.getByLabelText("粘贴单词"), "apple");
  await user.click(screen.getByRole("button", { name: "整理单词" }));
  await user.click(screen.getByRole("button", { name: "确认学习本" }));

  await waitFor(() =>
    expect(mockedApi).toHaveBeenCalledWith(
      "/voice-versions?ready=true&include_selection_metadata=true",
    ),
  );
});

it("loads the owned speaker profiles from settings and sends a default-voice request", async () => {
  const user = userEvent.setup();
  const mockedApi = vi.mocked(api);
  mockedApi.mockImplementation(async (path: string) => {
    if (path === "/setup/status") return { needs_initial_admin: false };
    if (path === "/settings/tts") return ttsConfig;
    if (path === "/settings/ai") return aiConfig;
    if (path === "/speaker-profiles")
      return [
        {
          id: "speaker-1",
          display_name: "妈妈",
          default_voice_version_id: "voice-1",
        },
      ];
    if (path === "/voice-versions?ready=false")
      return [
        {
          id: "voice-1",
          speaker_profile_id: "speaker-1",
          display_name: "妈妈 / 清晰美音",
          status: "ready",
        },
        {
          id: "voice-2",
          speaker_profile_id: "speaker-1",
          display_name: "妈妈 / 慢速美音",
          status: "ready",
        },
      ];
    if (path === "/voice-versions/voice-2/make-default")
      return {
        speaker_profile_id: "speaker-1",
        default_voice_version_id: "voice-2",
      };
    throw new Error(`Unexpected API call: ${path}`);
  });
  render(<App />);
  await user.click(await screen.findByRole("button", { name: "登录" }));
  await user.click(screen.getAllByRole("button", { name: "设置" })[0]);
  await user.click(await screen.findByRole("button", { name: "打开我的声音管理" }));
  await user.click(screen.getByRole("button", { name: "设为默认 慢速美音" }));
  expect(mockedApi).toHaveBeenCalledWith(
    "/voice-versions/voice-2/make-default",
    { method: "POST" },
  );
});

it("opens a speaker package dialog and sends a real inspect request", async () => {
  const user = userEvent.setup();
  const mockedApi = vi.mocked(api);
  mockedApi.mockImplementation(async (path: string) => {
    if (path === "/setup/status") return { needs_initial_admin: false };
    if (path === "/settings/tts") return ttsConfig;
    if (path === "/settings/ai") return aiConfig;
    if (path === "/speaker-profiles")
      return [
        {
          id: "speaker-1",
          display_name: "妈妈",
          default_voice_version_id: null,
        },
      ];
    if (path === "/voice-versions?ready=false") return [];
    if (path === "/speaker-profiles/import/inspect")
      return { import_id: "import-1", conflicts: [] };
    throw new Error(`Unexpected API call: ${path}`);
  });
  render(<App />);
  await user.click(await screen.findByRole("button", { name: "登录" }));
  await user.click(screen.getAllByRole("button", { name: "设置" })[0]);
  await user.click(await screen.findByRole("button", { name: "打开我的声音管理" }));
  await user.click(
    screen.getByRole("button", { name: "导入或导出声音包 妈妈" }),
  );
  await user.upload(
    screen.getByLabelText("导入声音包"),
    new File(["voice"], "voices.flvoice"),
  );
  await user.type(screen.getByLabelText("导入密码"), "package-password");
  await user.click(screen.getByRole("button", { name: "预览导入" }));
  expect(mockedApi).toHaveBeenCalledWith(
    "/speaker-profiles/import/inspect",
    expect.objectContaining({ method: "POST" }),
  );
});

it("exports only the selected speaker ready versions as an encrypted package", async () => {
  const user = userEvent.setup();
  const mockedApi = vi.mocked(api);
  const mockedBlob = vi.mocked(apiBlob);
  mockedBlob.mockResolvedValue(new Blob(["voice-package"]));
  mockedApi.mockImplementation(async (path: string) => {
    if (path === "/setup/status") return { needs_initial_admin: false };
    if (path === "/settings/tts") return ttsConfig;
    if (path === "/settings/ai") return aiConfig;
    if (path === "/speaker-profiles")
      return [
        {
          id: "speaker-1",
          display_name: "妈妈",
          default_voice_version_id: null,
        },
      ];
    if (path === "/voice-versions?ready=false")
      return [
        {
          id: "voice-1",
          speaker_profile_id: "speaker-1",
          display_name: "妈妈 / 清晰美音",
          status: "ready",
        },
      ];
    throw new Error(`Unexpected API call: ${path}`);
  });
  render(<App />);
  await user.click(await screen.findByRole("button", { name: "登录" }));
  await user.click(screen.getAllByRole("button", { name: "设置" })[0]);
  await user.click(await screen.findByRole("button", { name: "打开我的声音管理" }));
  await user.click(
    screen.getByRole("button", { name: "导入或导出声音包 妈妈" }),
  );
  await user.type(screen.getByLabelText("导出密码"), "package-password");
  await user.type(screen.getByLabelText("再次输入密码"), "package-password");
  await user.click(screen.getByRole("button", { name: "导出声音包" }));
  expect(mockedBlob).toHaveBeenCalledWith(
    "/speaker-profiles/speaker-1/export",
    {
      method: "POST",
      body: JSON.stringify({
        password: "package-password",
        voice_version_ids: ["voice-1"],
      }),
    },
  );
});

it("renders aggregate dictation statistics returned by the stats endpoint", async () => {
  const user = userEvent.setup();
  const mockedApi = vi.mocked(api);
  mockedApi.mockImplementation(async (path: string) => {
    if (path === "/setup/status") return { needs_initial_admin: false };
    if (path === "/stats/reading?period=month")
      return {
        combined_rate: 0,
        current_dual_streak: 0,
        chinese: { duration_ms: 0 },
        english: { duration_ms: 0 },
        calendar: [],
      };
    if (path === "/stats/dictation")
      return {
        daily: [],
        accuracy: 0.8,
        word_accuracy: 0.9,
        phrase_accuracy: 0.5,
        sentence_accuracy: null,
        unknown_items: { added_this_week: 3, mastered_this_week: 2 },
        dictionary_cache_hits: 7,
      };
    if (path === "/stats/mistakes") return [];
    throw new Error(`Unexpected API call: ${path}`);
  });

  render(<App />);
  await user.click(await screen.findByRole("button", { name: "登录" }));
  await user.click(screen.getAllByRole("button", { name: "统计" })[0]);

  expect(await screen.findByText("80%")).toBeVisible();
  expect(screen.getByText("90%")).toBeVisible();
  expect(screen.getByText("50%")).toBeVisible();
  expect(screen.getByText("3")).toBeVisible();
  expect(screen.getByText("2")).toBeVisible();
  expect(screen.getByText("7")).toBeVisible();
});
