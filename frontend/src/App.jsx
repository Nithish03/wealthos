import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Investments from './pages/Investments'
import CreditCards from './pages/CreditCards'
import BankAccounts from './pages/BankAccounts'
import Suggestions from './pages/Suggestions'
import Settings from './pages/Settings'

function PrivateRoute({ children }) {
  const token = localStorage.getItem('auth_token')
  return token ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: '#141927',
            color: '#e8edf5',
            border: '1px solid #1e2a40',
            borderRadius: '12px',
            fontSize: '14px',
          },
          success: { iconTheme: { primary: '#00d4aa', secondary: '#080b12' } },
          error: { iconTheme: { primary: '#f43f5e', secondary: '#080b12' } },
        }}
      />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<PrivateRoute><Layout /></PrivateRoute>}>
          <Route index element={<Dashboard />} />
          <Route path="investments" element={<Investments />} />
          <Route path="credit-cards" element={<CreditCards />} />
          <Route path="bank-accounts" element={<BankAccounts />} />
          <Route path="suggestions" element={<Suggestions />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
