import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import AppShell from "./components/shell/AppShell";
import DashboardPage from "./pages/DashboardPage";
import TasksPage from "./pages/TasksPage";
import EpisodesPage from "./pages/EpisodesPage";
import CharactersPage from "./pages/CharactersPage";
import TimelinePage from "./pages/TimelinePage";
import ExportsPage from "./pages/ExportsPage";
import SettingsPage from "./pages/SettingsPage";
import OverviewPage from "./pages/OverviewPage";
import SegmentsPage from "./pages/SegmentsPage";
import KeyChaptersPage from "./pages/KeyChaptersPage";
import ChapterAnalysisPage from "./pages/ChapterAnalysisPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/tasks" element={<TasksPage />} />
          <Route path="/episodes" element={<EpisodesPage />} />
          <Route path="/characters" element={<CharactersPage />} />
          <Route path="/timeline" element={<TimelinePage />} />
          <Route path="/exports" element={<ExportsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/overview" element={<OverviewPage />} />
          <Route path="/segments" element={<SegmentsPage />} />
          <Route path="/key-chapters" element={<KeyChaptersPage />} />
          <Route path="/chapter-analysis" element={<ChapterAnalysisPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
