import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './palette.css'
import './index.css'
import './workspace.css'
import './demo-experience.css'
import './resume-generate.css'
import './workspace-polish.css'
import './vault-flow.css'
import './github-guide.css'
import './radar-dialog.css'
import './cloud-guide.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
