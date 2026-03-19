import { Outlet } from "react-router-dom";
import TopBar from "./TopBar";
import SidebarNav from "./SidebarNav";
import RunLogDrawer from "./RunLogDrawer";

export default function AppShell() {
  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <TopBar />
      <div className="flex flex-1 min-h-0">
        <SidebarNav />
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
      <RunLogDrawer />
    </div>
  );
}
