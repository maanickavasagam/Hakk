import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './lib/AuthContext';
import Shell from './components/Shell';
import { PageLoader } from './components/ui';
import SignIn from './pages/SignIn';
import Landing from './pages/Landing';
import Cases from './pages/Cases';
import CaseDetail from './pages/CaseDetail';
import NewComplaint from './pages/NewComplaint';
import Lawyers from './pages/Lawyers';

function Gate() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen grid place-items-center bg-canvas">
        <PageLoader label="Signing you in" />
      </div>
    );
  }

  if (!user) return <SignIn />;

  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<Landing />} />
        <Route path="cases" element={<Cases />} />
        <Route path="cases/:id" element={<CaseDetail />} />
        <Route path="new" element={<NewComplaint />} />
        <Route path="lawyers" element={<Lawyers />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Gate />
      </AuthProvider>
    </BrowserRouter>
  );
}
