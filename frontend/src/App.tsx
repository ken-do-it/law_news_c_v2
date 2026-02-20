import { BrowserRouter, Routes, Route } from 'react-router-dom';
import TopNav from './components/TopNav';
import Dashboard from './pages/Dashboard';
import AnalysisList from './pages/AnalysisList';
import AnalysisDetail from './pages/AnalysisDetail';
import Settings from './pages/Settings';

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-[var(--color-bg)]">
        <TopNav />
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/analyses" element={<AnalysisList />} />
          <Route path="/analyses/:id" element={<AnalysisDetail />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<div className="p-8 text-center text-gray-500">404 - 페이지를 찾을 수 없습니다</div>} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
