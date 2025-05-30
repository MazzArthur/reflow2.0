import React from 'react';
import { startTwitchOAuth } from '../api';

const Login: React.FC = () => {
  const handleLogin = () => {
    // Chama a função que redireciona para o OAuth da Twitch via FastAPI
    startTwitchOAuth();
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '100vh',
      backgroundColor: '#1a1a1a',
      color: '#fff',
      fontFamily: 'Arial, sans-serif'
    }}>
      <h1>Bem-vindo ao VOD Streamer!</h1>
      <p>Faça login com sua conta da Twitch para começar.</p>
      <button
        onClick={handleLogin}
        style={{
          padding: '10px 20px',
          fontSize: '1.2em',
          backgroundColor: '#9147ff', // Cor roxa da Twitch
          color: '#fff',
          border: 'none',
          borderRadius: '5px',
          cursor: 'pointer',
          marginTop: '20px',
          display: 'flex',
          alignItems: 'center',
          gap: '10px'
        }}
      >
        <img src="https://www.twitch.tv/favicon.ico" alt="Twitch Logo" style={{ width: '24px', height: '24px' }} />
        Login com Twitch
      </button>
      <p style={{ marginTop: '30px', fontSize: '0.9em', color: '#aaa' }}>
        *Seus dados de cliente e chave de transmissão são mantidos seguros no backend.
      </p>
    </div>
  );
};

export default Login;