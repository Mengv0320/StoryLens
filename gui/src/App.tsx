import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import AppShell from "./components/shell/AppShell";
import DashboardPage from "./pages/DashboardPage";
import TasksPage from "./pages/TasksPage";
import CharactersPage from "./pages/CharactersPage";
import TimelinePage from "./pages/TimelinePage";
import ExportsPage from "./pages/ExportsPage";
import SettingsPage from "./pages/SettingsPage";
import ChapterAnalysisPage from "./pages/ChapterAnalysisPage";
import NarrativePage from "./pages/NarrativePage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/tasks" element={<TasksPage />} />
          <Route path="/characters" element={<CharactersPage />} />
          <Route path="/timeline" element={<TimelinePage />} />
          <Route path="/exports" element={<ExportsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/chapter-analysis" element={<ChapterAnalysisPage />} />
          <Route path="/narrative" element={<NarrativePage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
