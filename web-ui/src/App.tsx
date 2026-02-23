import React, { createContext, useContext, useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate, Link } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Music, CheckCircle2, AlertCircle, Copy, LogOut, ArrowLeft } from 'lucide-react';

// --- Auth Context ---
interface AuthContextType {
  user: { username: string } | null;
  loading: boolean;
  checkAuth: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  checkAuth: async () => {},
  logout: async () => {},
});

const AuthProvider = ({ children }: { children: React.ReactNode }) => {
  const [user, setUser] = useState<{ username: string } | null>(null);
  const [loading, setLoading] = useState(true);

  const checkAuth = async () => {
    try {
      const res = await fetch('/api/me');
      if (res.ok) {
        const data = await res.json();
        if (data.status === 'ok') {
          setUser({ username: data.username });
        } else {
          setUser(null);
        }
      } else {
        setUser(null);
      }
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    try {
      await fetch('/api/logout', { method: 'POST' });
      setUser(null);
    } catch {
      console.error("Failed to logout");
    }
  };

  useEffect(() => {
    checkAuth();
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, checkAuth, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

const useAuth = () => useContext(AuthContext);

// --- Pages ---

function Home() {
  const { user, loading } = useAuth();

  if (loading) return null;

  return (
    <div className="min-h-screen bg-neutral-950 flex flex-col items-center justify-center p-4">
      <div className="mb-8 flex flex-col items-center gap-4 text-neutral-100">
        <div className="p-4 bg-neutral-900 rounded-2xl border border-neutral-800 shadow-xl">
          <Music className="w-12 h-12 text-indigo-400" />
        </div>
        <h1 className="text-4xl font-extrabold tracking-tight">Hifi OpenSubsonic</h1>
        <p className="text-neutral-400 text-center max-w-sm">
          A high-fidelity API proxy for Tidal. Connect any OpenSubsonic client to your music.
        </p>
      </div>

      <div className="flex flex-col sm:flex-row gap-4 w-full max-w-sm">
        {user ? (
          <Button asChild className="w-full bg-indigo-600 hover:bg-indigo-700 h-12 text-lg">
            <Link to="/dashboard">Go to Dashboard</Link>
          </Button>
        ) : (
          <>
            <Button asChild variant="outline" className="w-full border-neutral-700 bg-neutral-900 text-neutral-200 hover:bg-neutral-800 h-12 text-lg">
              <Link to="/login">Sign In</Link>
            </Button>
            <Button asChild className="w-full bg-indigo-600 hover:bg-indigo-700 text-white h-12 text-lg">
              <Link to="/register">Register</Link>
            </Button>
          </>
        )}
      </div>
    </div>
  );
}

function Login() {
  const [formData, setFormData] = useState({ username: '', password: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { checkAuth } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    
    try {
      const resp = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });
      const data = await resp.json();
      
      if (!resp.ok || data.status === 'error') {
        setError(data.message || 'Invalid credentials');
      } else {
        await checkAuth(); // Refresh user state
        navigate('/dashboard');
      }
    } catch {
      setError('Network error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-950 flex flex-col items-center justify-center p-4 relative">
      <div className="absolute top-4 left-4 sm:top-8 sm:left-8">
        <Button variant="ghost" size="sm" asChild className="text-neutral-400 hover:text-white">
          <Link to="/">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back
          </Link>
        </Button>
      </div>
      <Card className="w-full max-w-md bg-neutral-900 border-neutral-800 text-neutral-100 shadow-2xl">
        <CardHeader>
          <CardTitle>Welcome Back</CardTitle>
          <CardDescription className="text-neutral-400">Sign in to view your credentials.</CardDescription>
        </CardHeader>
        <CardContent>
          {error && (
            <Alert variant="destructive" className="mb-6 bg-red-950/50 border-red-900/50 text-red-400">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Error</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <Input 
                id="username" 
                value={formData.username}
                onChange={(e) => setFormData({...formData, username: e.target.value})}
                className="bg-neutral-950 border-neutral-800 focus-visible:ring-indigo-500 text-neutral-200"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input 
                id="password" 
                type="password"
                value={formData.password}
                onChange={(e) => setFormData({...formData, password: e.target.value})}
                className="bg-neutral-950 border-neutral-800 focus-visible:ring-indigo-500 text-neutral-200"
              />
            </div>
            <Button type="submit" className="w-full mt-6 bg-indigo-600 hover:bg-indigo-700 text-white" disabled={loading}>
              {loading ? 'Signing in...' : 'Sign In'}
            </Button>
          </form>
        </CardContent>
        <CardFooter className="flex justify-center border-t border-neutral-800 pt-6">
          <p className="text-neutral-400 text-sm">
            Don't have an account? <Link to="/register" className="text-indigo-400 hover:text-indigo-300 ml-1">Register</Link>
          </p>
        </CardFooter>
      </Card>
    </div>
  );
}

function Register() {
  const [formData, setFormData] = useState({ username: '', password: '', email: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { checkAuth } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    
    try {
      const resp = await fetch('/api/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });
      const data = await resp.json();
      
      if (!resp.ok || data.status === 'error') {
        setError(data.message || 'Registration failed');
      } else {
        await checkAuth(); // Reads the newly set HttpOnly cookie
        navigate('/dashboard');
      }
    } catch {
      setError('Network error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-950 flex flex-col items-center justify-center p-4 relative">
      <div className="absolute top-4 left-4 sm:top-8 sm:left-8">
        <Button variant="ghost" size="sm" asChild className="text-neutral-400 hover:text-white">
          <Link to="/">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back
          </Link>
        </Button>
      </div>
      <Card className="w-full max-w-md bg-neutral-900 border-neutral-800 text-neutral-100 shadow-2xl">
        <CardHeader>
          <CardTitle>Create an Account</CardTitle>
          <CardDescription className="text-neutral-400">Sign up to securely access your music library.</CardDescription>
        </CardHeader>
        <CardContent>
          {error && (
            <Alert variant="destructive" className="mb-6 bg-red-950/50 border-red-900/50 text-red-400">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Error</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <Input 
                id="username" 
                value={formData.username}
                onChange={(e) => setFormData({...formData, username: e.target.value})}
                className="bg-neutral-950 border-neutral-800 focus-visible:ring-indigo-500 text-neutral-200"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email <span className="text-neutral-500 text-xs">(Optional)</span></Label>
              <Input 
                id="email" 
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({...formData, email: e.target.value})}
                className="bg-neutral-950 border-neutral-800 focus-visible:ring-indigo-500 text-neutral-200"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input 
                id="password" 
                type="password"
                value={formData.password}
                onChange={(e) => setFormData({...formData, password: e.target.value})}
                className="bg-neutral-950 border-neutral-800 focus-visible:ring-indigo-500 text-neutral-200"
              />
            </div>
            <Button type="submit" className="w-full mt-6 bg-indigo-600 hover:bg-indigo-700 text-white" disabled={loading}>
              {loading ? 'Creating account...' : 'Create Account'}
            </Button>
          </form>
        </CardContent>
        <CardFooter className="flex justify-center border-t border-neutral-800 pt-6">
          <p className="text-neutral-400 text-sm">
            Already have an account? <Link to="/login" className="text-indigo-400 hover:text-indigo-300 ml-1">Sign In</Link>
          </p>
        </CardFooter>
      </Card>
    </div>
  );
}

function Dashboard() {
  const { user, loading, logout } = useAuth();
  const navigate = useNavigate();

  if (loading) return null;
  if (!user) {
    return <Navigate to="/login" replace />;
  }

  const serverUrl = window.location.origin;

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const handleLogout = async () => {
    await logout();
    navigate('/');
  };

  return (
    <div className="min-h-screen bg-neutral-950 flex flex-col items-center justify-center p-4">
      <Card className="w-full max-w-md bg-neutral-900 border-neutral-800 text-neutral-100 shadow-2xl relative overflow-hidden">
        <div className="absolute top-0 right-0 p-4">
          <Button variant="ghost" size="sm" onClick={handleLogout} className="text-neutral-400 hover:text-white hover:bg-neutral-800">
            <LogOut className="w-4 h-4 mr-2" />
            Sign Out
          </Button>
        </div>
        
        <CardHeader className="text-center pt-10 pb-2">
          <div className="mx-auto w-12 h-12 bg-green-500/20 rounded-full flex items-center justify-center mb-4">
            <CheckCircle2 className="w-6 h-6 text-green-500" />
          </div>
          <CardTitle className="text-2xl font-bold bg-gradient-to-br from-white to-neutral-400 bg-clip-text text-transparent">
            Welcome, {user.username}!
          </CardTitle>
          <CardDescription className="text-neutral-400 mt-2">
            Use these credentials to sign into your OpenSubsonic clients (like Feishin, Tempus, or Narjo).
          </CardDescription>
        </CardHeader>
        
        <CardContent className="space-y-4 pt-4">
          <div className="space-y-2 p-3 bg-black/40 rounded-lg border border-neutral-800">
            <Label className="text-neutral-500 text-xs uppercase tracking-wider">Server Address</Label>
            <div className="flex items-center justify-between">
              <code className="text-sm font-mono text-neutral-200 break-all">{serverUrl}</code>
              <Button variant="ghost" size="icon" className="h-6 w-6 shrink-0 text-neutral-400 hover:text-white" onClick={() => copyToClipboard(serverUrl)}>
                <Copy className="h-4 w-4" />
              </Button>
            </div>
          </div>
          <div className="space-y-2 p-3 bg-black/40 rounded-lg border border-neutral-800">
            <Label className="text-neutral-500 text-xs uppercase tracking-wider">Username</Label>
            <div className="flex items-center justify-between">
              <code className="text-sm font-mono text-neutral-200">{user.username}</code>
              <Button variant="ghost" size="icon" className="h-6 w-6 shrink-0 text-neutral-400 hover:text-white" onClick={() => copyToClipboard(user.username)}>
                <Copy className="h-4 w-4" />
              </Button>
            </div>
          </div>
          <div className="space-y-2 p-3 bg-black/40 rounded-lg border border-neutral-800">
            <Label className="text-neutral-500 text-xs uppercase tracking-wider">Password</Label>
            <p className="text-sm text-neutral-400 italic">The password you used to register/log in.</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// --- Main App Component ---

export default function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Router>
    </AuthProvider>
  );
}
