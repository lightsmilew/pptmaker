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
          background: '#1E293B',
          color: '#F1F5F9',
          border: '1px solid #334155',
        },
        success: {
          iconTheme: {
            primary: '#10B981',
            secondary: '#F1F5F9',
          },
        },
        error: {
          iconTheme: {
            primary: '#EF4444',
            secondary: '#F1F5F9',
          },
        },
      }}
    />
  </React.StrictMode>,
)
