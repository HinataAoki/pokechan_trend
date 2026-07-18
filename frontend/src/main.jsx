import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

// Google Analytics (GA4). The measurement id is a public identifier (it's
// visible in any site's page source), so the production default lives here;
// VITE_GA_MEASUREMENT_ID overrides it, and dev-server sessions send nothing.
const gaId =
  import.meta.env.VITE_GA_MEASUREMENT_ID ||
  (import.meta.env.PROD ? 'G-XGQJETQFQ3' : '')
if (gaId) {
  const script = document.createElement('script')
  script.async = true
  script.src = `https://www.googletagmanager.com/gtag/js?id=${gaId}`
  document.head.appendChild(script)

  window.dataLayer = window.dataLayer || []
  function gtag() {
    window.dataLayer.push(arguments)
  }
  window.gtag = gtag
  gtag('js', new Date())
  gtag('config', gaId)
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
