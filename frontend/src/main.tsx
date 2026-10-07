import React from 'react'
import ReactDOM from 'react-dom/client'
import { Toaster } from 'react-hot-toast'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
    <Toaster
      position="top-right"
      toastOptions={{
        duration: 3000,
        style: {
          background: '#ffffff',
          color: '#27342d',
          border: '1px solid #dfe4da',
        },
        success: {
          iconTheme: {
            primary: '#29483e',
            secondary: '#27342d',
          },
        },
        error: {
          iconTheme: {
            primary: '#EF4444',
            secondary: '#27342d',
          },
        },
      }}
    />
  </React.StrictMode>,
)
