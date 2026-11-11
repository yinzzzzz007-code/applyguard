import { lazy, Suspense } from 'react'
import { useLocation } from 'react-router-dom'
import { LoadingState } from './components/States'
import { RouteBoundary } from './components/RouteBoundary'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { DemoProvider } from './context/DemoContext'
const AtsSimulatorPage = lazy(() => import('./pages/AtsSimulatorPage').then(module => ({ default: module.AtsSimulatorPage })))
const ApplicationHistoryPage = lazy(() => import('./pages/ApplicationHistoryPage').then(module => ({ default: module.ApplicationHistoryPage })))
const ResumeImportPage = lazy(() => import('./pages/ResumeImportPage').then(module => ({ default: module.ResumeImportPage })))
const CareerVaultPage = lazy(() => import('./pages/CareerVaultPage').then(module => ({ default: module.CareerVaultPage })))
const ClaimVerificationPage = lazy(() => import('./pages/ClaimVerificationPage').then(module => ({ default: module.ClaimVerificationPage })))
const EvidenceMatchPage = lazy(() => import('./pages/EvidenceMatchPage').then(module => ({ default: module.EvidenceMatchPage })))
const EvidenceWorkspacePage = lazy(() => import('./pages/EvidenceWorkspacePage').then(module => ({ default: module.EvidenceWorkspacePage })))
const HumanConfirmationPage = lazy(() => import('./pages/HumanConfirmationPage').then(module => ({ default: module.HumanConfirmationPage })))
const JdInputPage = lazy(() => import('./pages/JdInputPage').then(module => ({ default: module.JdInputPage })))
const ResumeReviewPage = lazy(() => import('./pages/ResumeReviewPage').then(module => ({ default: module.ResumeReviewPage })))
const JobRadarPage = lazy(() => import('./pages/JobRadarPage').then(module => ({ default: module.JobRadarPage })))
const HelpPage = lazy(() => import('./pages/HelpPage').then(module => ({ default: module.HelpPage })))

function PageRoutes() {
  const { pathname } = useLocation()
  return <RouteBoundary key={pathname}><Suspense fallback={<LoadingState label="正在打开页面…" />}>
    <Routes>
            <Route path="/" element={<ResumeImportPage />} />
            <Route path="/vault" element={<CareerVaultPage />} />
            <Route path="/evidence" element={<EvidenceWorkspacePage />} />
            <Route path="/jd" element={<JdInputPage />} />
            <Route path="/jobs" element={<JobRadarPage />} />
            <Route path="/match" element={<EvidenceMatchPage />} />
            <Route path="/resume" element={<ResumeReviewPage />} />
            <Route path="/claims" element={<ClaimVerificationPage />} />
            <Route path="/ats" element={<AtsSimulatorPage />} />
            <Route path="/confirm" element={<HumanConfirmationPage />} />
            <Route path="/history" element={<ApplicationHistoryPage />} />
            <Route path="/help" element={<HelpPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  </Suspense></RouteBoundary>
}

export default function App() {
  return (
    <BrowserRouter>
      <DemoProvider>
        <AppShell>
          <PageRoutes />
        </AppShell>
      </DemoProvider>
    </BrowserRouter>
  )
}
