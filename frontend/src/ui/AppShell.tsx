import { useEffect, useState, type PropsWithChildren } from "react";

type Destination = { label: string; icon: string };
type NavigationGroup = {
  label: string;
  icon: string;
  destinations: Destination[];
};

const asset = (name: string) => `/animal-island/${name}`;
const navigation: NavigationGroup[] = [
  {
    label: "首页",
    icon: "leaf.png",
    destinations: [{ label: "今天", icon: "leaf.png" }],
  },
  {
    label: "学习",
    icon: "diy.svg",
    destinations: [
      { label: "学习本", icon: "diy.svg" },
      { label: "单词默写", icon: "miles.svg" },
      { label: "辞典", icon: "critterpedia.svg" },
      { label: "生词本", icon: "design.svg" },
    ],
  },
  {
    label: "内容",
    icon: "camera.svg",
    destinations: [
      { label: "中文阅读", icon: "camera.svg" },
      { label: "英文阅读", icon: "chat.svg" },
      { label: "视频库", icon: "shopping.svg" },
    ],
  },
  {
    label: "我的",
    icon: "map.svg",
    destinations: [
      { label: "统计", icon: "miles.svg" },
      { label: "我的声音", icon: "chat.svg" },
      { label: "设置", icon: "design.svg" },
    ],
  },
];

const groupForDestination = (destination?: string) =>
  navigation.find((group) =>
    group.destinations.some((item) => item.label === destination),
  )?.label ?? "首页";

export function AppShell({
  children,
  onNavigate,
  activeDestination,
}: PropsWithChildren<{
  onNavigate?: (item: string) => void;
  activeDestination?: string;
}>) {
  const [activeGroup, setActiveGroup] = useState(() =>
    groupForDestination(activeDestination),
  );
  const [menuOpen, setMenuOpen] = useState(false);
  useEffect(
    () => setActiveGroup(groupForDestination(activeDestination)),
    [activeDestination],
  );
  const chooseGroup = (group: NavigationGroup) => {
    setActiveGroup(group.label);
    if (group.destinations.length === 1) {
      onNavigate?.(group.destinations[0].label);
      setMenuOpen(false);
    } else setMenuOpen(true);
  };
  const chooseDestination = (label: string) => {
    onNavigate?.(label);
    setMenuOpen(false);
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button className="brand" onClick={() => chooseDestination("今天")}>
          <img src={asset("leaf.png")} alt="" />
          <span>
            家庭学习岛<small>每天进步一点点</small>
          </span>
        </button>
        <nav aria-label="桌面导航">
          {navigation.map((group) => (
            <section className="nav-group" key={group.label}>
              <p>{group.label}</p>
              {group.destinations.map((item) => (
                <button
                  key={item.label}
                  onClick={() => chooseDestination(item.label)}
                  className="nav-item"
                >
                  <img src={asset(item.icon)} alt="" />
                  <span>{item.label}</span>
                </button>
              ))}
            </section>
          ))}
        </nav>
        <p className="asset-credit">
          界面素材来自 Animal Island UI
          <br />
          CC BY-NC 4.0
          <br />
          词典：ECDICT (MIT) / CC-CEDICT (CC BY-SA 3.0)
        </p>
      </aside>
      <header className="tablet-header">
        <button
          className="tablet-brand"
          onClick={() => chooseDestination("今天")}
        >
          <img src={asset("leaf.png")} alt="" />
          家庭学习岛
        </button>
        <nav aria-label="平板导航">
          {navigation.map((group) => (
            <button
              key={group.label}
              className={
                activeGroup === group.label ? "nav-item active" : "nav-item"
              }
              onClick={() => chooseGroup(group)}
            >
              <img src={asset(group.icon)} alt="" />
              <span>{group.label}</span>
            </button>
          ))}
        </nav>
      </header>
      <main className="main-content">{children}</main>
      {menuOpen && (
        <div
          className="mobile-menu-backdrop"
          onClick={() => setMenuOpen(false)}
        >
          <section
            className="mobile-menu"
            aria-label={`${activeGroup}功能`}
            onClick={(event) => event.stopPropagation()}
          >
            <header>
              <div>
                <p>选择功能</p>
                <h2>{activeGroup}</h2>
              </div>
              <button
                aria-label="关闭功能菜单"
                onClick={() => setMenuOpen(false)}
              >
                ×
              </button>
            </header>
            <div className="mobile-menu-grid">
              {navigation
                .find((group) => group.label === activeGroup)
                ?.destinations.map((item) => (
                  <button
                    key={item.label}
                    onClick={() => chooseDestination(item.label)}
                  >
                    <span>
                      <img src={asset(item.icon)} alt="" />
                    </span>
                    <strong>{item.label}</strong>
                  </button>
                ))}
            </div>
          </section>
        </div>
      )}
      <nav className="bottom-nav" aria-label="手机导航">
        {navigation.map((group) => (
          <button
            key={group.label}
            onClick={() => chooseGroup(group)}
            className={
              activeGroup === group.label ? "nav-item active" : "nav-item"
            }
          >
            <img src={asset(group.icon)} alt="" />
            <span>{group.label}</span>
          </button>
        ))}
      </nav>
    </div>
  );
}
