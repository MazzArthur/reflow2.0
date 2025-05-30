import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import Login from './components/Login';
import Dashboard from './components/Dashboard';

const AppContent: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    // Processa os parâmetros da URL após o retorno do Twitch OAuth
    const params = new URLSearchParams(location.search);
    const success = params.get('success');
    const username = params.get('username');
    const error = params.get('error');

    if (success === 'true') {
      // Login bem-sucedido, redireciona para o dashboard
      // Remove os parâmetros da URL para uma URL mais limpa
      navigate('/dashboard', { replace: true, state: { username } });
    } else if (error) {
      // Houve um erro no OAuth, redireciona para o login e exibe o erro
      alert(`Erro no login da Twitch: ${error}. Por favor, tente novamente.`);
      navigate('/login', { replace: true });
    } else if (location.pathname === '/' || location.pathname === '') {
      // Se estiver na raiz e não houver parâmetros de login, vá para a tela de login
      navigate('/login', { replace: true });
    }
  }, [location, navigate]);

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/dashboard" element={<Dashboard />} />
      {/* Redirecionamento da raiz para o login será tratado no useEffect acima */}
      <Route path="*" element={<div>Página não encontrada</div>} />
    </Routes>
  );
};

const App: React.FC = () => {
  return (
    <Router>
      <AppContent />
    </Router>
  );
};

export default App;