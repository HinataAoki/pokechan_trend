import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

// Google Analytics (GA4) is loaded via the standard static snippet in
// index.html - GA's tag-detection crawler only reads the raw HTML, so a
// JS-injected tag gets reported as "not detected".

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
