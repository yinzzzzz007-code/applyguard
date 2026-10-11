import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { DemoProvider } from './context/DemoContext'
import { AtsSimulatorPage } from './pages/AtsSimulatorPage'
import { ApplicationHistoryPage } from './pages/ApplicationHistoryPage'
import { ResumeImportPage } from './pages/ResumeImportPage'
import { CareerVaultPage } from './pages/CareerVaultPage'
import { ClaimVerificationPage } from './pages/ClaimVerificationPage'
import { EvidenceMatchPage } from './pages/EvidenceMatchPage'
import { EvidenceWorkspacePage } from './pages/EvidenceWorkspacePage'
import { HumanConfirmationPage } from './pages/HumanConfirmationPage'
import { JdInputPage } from './pages/JdInputPage'
import { ResumeReviewPage } from './pages/ResumeReviewPage'

export default function App() {
  return (
    <BrowserRouter>
      <DemoProvider>
        <AppShell>
          <Routes>
            <Route path="/" element={<ResumeImportPage />} />
            <Route path="/vault" element={<CareerVaultPage />} />
            <Route path="/evidence" element={<EvidenceWorkspacePage />} />
            <Route path="/jd" element={<JdInputPage />} />
            <Route path="/match" element={<EvidenceMatchPage />} />
            <Route path="/resume" element={<ResumeReviewPage />} />
            <Route path="/claims" element={<ClaimVerificationPage />} />
            <Route path="/ats" element={<AtsSimulatorPage />} />
            <Route path="/confirm" element={<HumanConfirmationPage />} />
            <Route path="/history" element={<ApplicationHistoryPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AppShell>
      </DemoProvider>
    </BrowserRouter>
  )
}
