import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { authAPI } from '../api/client'
import toast from 'react-hot-toast'

export default function Login() {
  const navigate = useNavigate()
  const [pin, setPin] = useState('')
  const [hasPin, setHasPin] = useState(null)
  const [loading, setLoading] = useState(false)
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    if (localStorage.getItem('auth_token')) {
      navigate('/')
      return
    }
    authAPI.status().then(res => {
      setHasPin(res.data.has_pin)
      setChecking(false)
    }).catch(() => {
      setHasPin(false)
      setChecking(false)
    })
  }, [])

  const handleSubmit = async (e) => {
    e?.preventDefault()
    if (pin.length < 4) return toast.error('PIN must be at least 4 digits')
    setLoading(true)
    try {
      const res = hasPin
        ? await authAPI.login(pin)
        : await authAPI.setup(pin)
      localStorage.setItem('auth_token', res.data.access_token)
      toast.success(hasPin ? 'Welcome back!' : 'PIN set! Welcome to WealthOS')
      navigate('/')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Invalid PIN')
    } finally {
      setLoading(false)
    }
  }

  const handleKeyPress = (digit) => {
    if (pin.length < 6) setPin(p => p + digit)
  }
  const handleDelete = () => setPin(p => p.slice(0, -1))

  if (checking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-bg-primary">
        <div className="w-8 h-8 border-2 border-accent-green border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-bg-primary flex items-center justify-center relative overflow-hidden">
      {/* Background decoration */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[600px] bg-accent-green/3 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 left-1/3 w-[400px] h-[400px] bg-accent-blue/3 rounded-full blur-3xl pointer-events-none" />

      <div className="relative z-10 w-full max-w-sm mx-4">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 mx-auto rounded-2xl bg-accent-green/10 border border-accent-green/30 flex items-center justify-center mb-4">
            <span className="text-3xl">₹</span>
          </div>
          <h1 className="font-display text-2xl font-bold text-text-primary">WealthOS</h1>
          <p className="text-text-secondary text-sm mt-1">
            {hasPin ? 'Enter your PIN to unlock' : 'Set up your 4-6 digit PIN'}
          </p>
        </div>

        {/* PIN dots */}
        <div className="flex justify-center gap-3 mb-8">
          {[0,1,2,3,4,5].map(i => (
            <div
              key={i}
              className={`w-3.5 h-3.5 rounded-full border-2 transition-all duration-150 ${
                i < pin.length
                  ? 'bg-accent-green border-accent-green scale-110'
                  : 'border-bg-border bg-bg-card'
              }`}
            />
          ))}
        </div>

        {/* Keypad */}
        <div className="card p-6">
          <div className="grid grid-cols-3 gap-3">
            {[1,2,3,4,5,6,7,8,9,'',0,'⌫'].map((key, i) => (
              <button
                key={i}
                onClick={() => key === '⌫' ? handleDelete() : key !== '' && handleKeyPress(String(key))}
                disabled={key === '' || loading}
                className={`h-14 rounded-xl font-mono text-lg font-medium transition-all duration-100 
                  ${key === '' ? 'invisible' :
                    key === '⌫' ? 'text-text-secondary hover:bg-bg-hover active:scale-95' :
                    'text-text-primary bg-bg-hover hover:bg-bg-border active:scale-95 hover:text-accent-green'}
                  ${loading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
                `}
              >
                {key}
              </button>
            ))}
          </div>

          <button
            onClick={handleSubmit}
            disabled={pin.length < 4 || loading}
            className={`w-full mt-4 h-12 rounded-xl font-semibold text-sm transition-all duration-150
              ${pin.length >= 4 && !loading
                ? 'bg-accent-green text-bg-primary hover:bg-accent-green/90 active:scale-98'
                : 'bg-bg-hover text-text-muted cursor-not-allowed'}
            `}
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                {hasPin ? 'Unlocking...' : 'Setting up...'}
              </span>
            ) : (
              hasPin ? 'Unlock' : 'Set PIN & Enter'
            )}
          </button>
        </div>

        <p className="text-center text-xs text-text-muted mt-6">
          🔒 All data stored locally on your machine
        </p>
      </div>
    </div>
  )
}
