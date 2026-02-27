import React, { useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';

const Login = () => {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const navigate = useNavigate();

    const handleLogin = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError('');
        try {
            const response = await axios.post('/api/auth/login', { email, password });
            localStorage.setItem('token', response.data.token);
            localStorage.setItem('user', JSON.stringify(response.data.user));

            if (response.data.user.role === 'admin') {
                navigate('/admin');
            } else {
                navigate('/cleaner');
            }
        } catch (err) {
            setError(err.response?.data?.error || 'Login failed. Please check your credentials.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="login-page fade-in">
            <div className="login-card glass">
                <div className="login-header">
                    <div className="logo-icon">✨</div>
                    <h1>Cleaner Attendance</h1>
                    <p>Login to your account</p>
                </div>

                <form onSubmit={handleLogin}>
                    <div className="form-group">
                        <label>Email Address</label>
                        <input
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            placeholder="name@company.com"
                            required
                        />
                    </div>

                    <div className="form-group">
                        <label>Password</label>
                        <input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="••••••••"
                            required
                        />
                    </div>

                    {error && <div className="error-message">{error}</div>}

                    <button type="submit" className="btn btn-primary login-btn" disabled={loading}>
                        {loading ? 'Authenticating...' : 'Sign In'}
                    </button>
                </form>
            </div>

            <style jsx>{`
        .login-page {
          display: flex;
          align-items: center;
          justify-content: center;
          flex: 1;
          padding: 1.5rem;
          background: radial-gradient(circle at top right, #1e293b, #0f172a);
        }
        .login-card {
          width: 100%;
          max-width: 400px;
          padding: 2.5rem;
        }
        .login-header {
          text-align: center;
          margin-bottom: 2rem;
        }
        .logo-icon {
          font-size: 3rem;
          margin-bottom: 0.5rem;
        }
        .form-group {
          margin-bottom: 1.5rem;
        }
        label {
          display: block;
          font-size: 0.875rem;
          color: var(--text-muted);
          margin-bottom: 0.5rem;
        }
        input {
          width: 100%;
          padding: 0.75rem 1rem;
          background: var(--surface-light);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: var(--radius);
          color: white;
          font-size: 1rem;
          outline: none;
          transition: border-color 0.2s;
        }
        input:focus {
          border-color: var(--primary);
        }
        .login-btn {
          width: 100%;
          margin-top: 1rem;
        }
        .error-message {
          color: var(--danger);
          font-size: 0.875rem;
          margin-bottom: 1rem;
          text-align: center;
        }
      `}</style>
        </div>
    );
};

export default Login;
