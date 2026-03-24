import { useState, useCallback } from "react";
import { Outlet } from "react-router-dom";
import TopBar from "./TopBar";
import SidebarNav from "./SidebarNav";
import NetworkBanner from "./NetworkBanner";
import RunLogDrawer from "./RunLogDrawer";

export default function AppShell() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const toggleSidebar = useCallback(() => setSidebarOpen((v) => !v), []);
  const closeSidebar = useCallback(() => setSidebarOpen(false), []);

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-bg text-txt">
      <TopBar onMenuToggle={toggleSidebar} />
      <NetworkBanner />
      <div className="flex flex-1 min-h-0">
        <SidebarNav open={sidebarOpen} onClose={closeSidebar} />
        <main className="flex-1 overflow-y-auto bg-bg">
          <Outlet />
        </main>
      </div>
      <RunLogDrawer />
    </div>
  );
}
