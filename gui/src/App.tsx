import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import ErrorBoundary, { PageErrorBoundary } from "./components/ErrorBoundary";
import AppShell from "./components/shell/AppShell";

const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const TasksPage = lazy(() => import("./pages/TasksPage"));
const CharactersPage = lazy(() => import("./pages/CharactersPage"));
const TimelinePage = lazy(() => import("./pages/TimelinePage"));
const ExportsPage = lazy(() => import("./pages/ExportsPage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));
const ChapterAnalysisPage = lazy(() => import("./pages/ChapterAnalysisPage"));
const NarrativePage = lazy(() => import("./pages/NarrativePage"));
const LibraryPage = lazy(() => import("./pages/LibraryPage"));
const BookDetailPage = lazy(() => import("./pages/BookDetailPage"));
const ReaderComparePage = lazy(() => import("./pages/ReaderComparePage"));
const SearchPage = lazy(() => import("./pages/SearchPage"));
const NotFoundPage = lazy(() => import("./pages/NotFoundPage"));

const Loading = () => (
  <div className="flex items-center justify-center min-h-[40vh] text-txt-soft text-sm">加载中...</div>
);

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Suspense fallback={<Loading />}>
          <Routes>
            <Route element={<AppShell />}>
              <Route path="/" element={<Navigate to="/library" replace />} />
              <Route path="/library" element={<PageErrorBoundary><LibraryPage /></PageErrorBoundary>} />
              <Route path="/book/:bookId" element={<PageErrorBoundary><BookDetailPage /></PageErrorBoundary>} />
              <Route path="/reader/:bookId" element={<PageErrorBoundary><ReaderComparePage /></PageErrorBoundary>} />
              <Route path="/dashboard" element={<PageErrorBoundary><DashboardPage /></PageErrorBoundary>} />
              <Route path="/tasks" element={<PageErrorBoundary><TasksPage /></PageErrorBoundary>} />
              <Route path="/characters" element={<PageErrorBoundary><CharactersPage /></PageErrorBoundary>} />
              <Route path="/timeline" element={<PageErrorBoundary><TimelinePage /></PageErrorBoundary>} />
              <Route path="/exports" element={<PageErrorBoundary><ExportsPage /></PageErrorBoundary>} />
              <Route path="/settings" element={<PageErrorBoundary><SettingsPage /></PageErrorBoundary>} />
              <Route path="/chapter-analysis" element={<PageErrorBoundary><ChapterAnalysisPage /></PageErrorBoundary>} />
              <Route path="/narrative" element={<PageErrorBoundary><NarrativePage /></PageErrorBoundary>} />
              <Route path="/search" element={<PageErrorBoundary><SearchPage /></PageErrorBoundary>} />
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
    </ErrorBoundary>
  );
}

