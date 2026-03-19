import { NavLink } from "react-router-dom";
import { LayoutDashboard, ListChecks, FileText, BookOpen, Users, Clock, Download, Settings } from "lucide-react";

const navItems = [
  { to: "/dashboard", label: "仪表盘", icon: LayoutDashboard },
  { to: "/tasks", label: "任务", icon: ListChecks },
  { to: "/chapter-analysis", label: "章节分析", icon: FileText },
  { to: "/narrative", label: "叙事分析", icon: BookOpen },
  { to: "/characters", label: "角色", icon: Users },
  { to: "/timeline", label: "时间线", icon: Clock },
  { to: "/exports", label: "导出", icon: Download },
  { to: "/settings", label: "设置", icon: Settings },
];

export default function SidebarNav() {
  return (
    <nav className="w-[220px] min-h-0 flex-shrink-0 border-r border-border bg-panel flex flex-col py-4">
      {navItems.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            `flex items-center gap-3 px-5 py-2.5 text-md transition-colors ${
              isActive
                ? "bg-accent-soft text-accent font-medium"
                : "text-txt-soft hover:bg-panel-muted hover:text-txt"
            }`
          }
        >
          <Icon size={18} />
          <span>{label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
