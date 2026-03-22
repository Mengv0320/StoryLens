import { NavLink } from "react-router-dom";
import {
  Library, FileText, LayoutDashboard, ListChecks, Settings,
  Users, Clock, Download, BookOpenCheck, Search,
} from "lucide-react";
import { useActiveBook } from "../../lib/useActiveBook";

// 需要激活书才有意义的分析 Tab
const BOOK_SCOPED_PATHS = [
  "/dashboard", "/chapter-analysis", "/narrative", "/characters", "/timeline",
];

const navItems = [
  { to: "/library",          label: "书架",     icon: Library },
  { to: "/search",           label: "搜索",     icon: Search },
  { to: "/dashboard",        label: "分析总览", icon: LayoutDashboard },
  { to: "/chapter-analysis", label: "章节分析", icon: FileText },
  { to: "/narrative",        label: "叙事分析", icon: BookOpenCheck },
  { to: "/characters",       label: "角色",     icon: Users },
  { to: "/timeline",         label: "时间线",   icon: Clock },
  { to: "/tasks",            label: "任务中心", icon: ListChecks },
  { to: "/exports",          label: "导出",     icon: Download },
  { to: "/settings",         label: "设置",     icon: Settings },
];

export default function SidebarNav() {
  const { activeBook } = useActiveBook();
  const hasActiveBook = !!activeBook;

  return (
    <nav className="w-[220px] min-h-0 flex-shrink-0 border-r border-border/40 bg-panel/60 backdrop-blur-xl flex flex-col py-4 shadow-[4px_0_24px_rgba(0,0,0,0.02)] z-40 transition-all duration-300">
      {navItems.map(({ to, label, icon: Icon }) => {
        const needsBook = BOOK_SCOPED_PATHS.includes(to);
        const dimmed = needsBook && !hasActiveBook;

        return (
          <NavLink
            key={to}
            to={to}
            title={dimmed ? "请先从书架选择一本书" : undefined}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 mx-3 my-0.5 text-sm transition-colors rounded-md outline-none ${
                isActive
                  ? "bg-accent-soft text-accent font-medium"
                  : dimmed
                    ? "text-txt-faint cursor-not-allowed pointer-events-none opacity-60 bg-panel-muted/30 border border-transparent"
                    : "text-txt-soft hover:bg-panel-muted/80 hover:text-txt"
              }`
            }
          >
            {({ isActive }) => (
              <>
                <Icon size={18} className={isActive ? "text-accent" : ""} />
                <span>{label}</span>
                {dimmed && (
                  <span className="ml-auto text-[9px] text-txt-faint leading-none px-1.5 py-0.5 rounded-md bg-panel/50 border border-border/50">选书</span>
                )}
              </>
            )}
          </NavLink>
        );
      })}
    </nav>
  );
}
