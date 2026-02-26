import { BrowserRouter, Routes, Route } from 'react-router-dom';
import TopNav from './components/TopNav';
import { ToastProvider } from './components/Toast';
import ReviewHome from './pages/ReviewHome';
import Dashboard from './pages/Dashboard';
import AnalysisList from './pages/AnalysisList';
import AnalysisDetail from './pages/AnalysisDetail';
import Settings from './pages/Settings';

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <div className="min-h-screen bg-bg">
          <TopNav />
          <Routes>
            <Route path="/" element={<ReviewHome />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/analyses" element={<AnalysisList />} />
            <Route path="/analyses/:id" element={<AnalysisDetail />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </div>
      </ToastProvider>
    </BrowserRouter>
  );
}
