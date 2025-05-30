import React, { useEffect, useState, useCallback } from 'react';
import { getVods, startStream, stopStream, getStreamStatus } from '../api';

interface Vod {
  id: string;
  title: string;
  url: string;
  thumbnail_url: string;
  duration: string;
}

interface StreamStatus {
  status: string;
  current_vod: string;
}

const Dashboard: React.FC = () => {
  const [username, setUsername] = useState<string>('');
  const [vods, setVods] = useState<Vod[]>([]);
  const [selectedVods, setSelectedVods] = useState<string[]>([]);
  const [quality, setQuality] = useState<string>('best');
  const [streamStatus, setStreamStatus] = useState<StreamStatus>({ status: 'Parado', current_vod: 'Nenhum' });
  const [message, setMessage] = useState<string | null>(null);

  // Função para buscar VODs e status
  const fetchData = useCallback(async () => {
    try {
      const data = await getVods();
      setUsername(data.username);
      setVods(data.vods);
      setStreamStatus(data.status);
    } catch (error: any) {
      // Se não autenticado, redireciona para login
      if (error.response && error.response.status === 401) {
        window.location.href = '/login';
      } else {
        setMessage(`Erro ao carregar dados: ${error.message || 'Desconhecido'}`);
        console.error("Erro ao carregar dados:", error);
      }
    }
  }, []);

  // Efeito para buscar dados na montagem do componente
  useEffect(() => {
    fetchData();
    // Configura um polling para o status da transmissão a cada 5 segundos
    const statusInterval = setInterval(async () => {
      try {
        const statusData = await getStreamStatus();
        setStreamStatus(statusData);
      } catch (error) {
        console.error("Erro ao atualizar status:", error);
      }
    }, 5000); // Poll a cada 5 segundos

    // Limpa o intervalo ao desmontar o componente
    return () => clearInterval(statusInterval);
  }, [fetchData]);

  const handleVodSelect = (vodUrl: string) => {
    setSelectedVods(prev =>
      prev.includes(vodUrl) ? prev.filter(url => url !== vodUrl) : [...prev, vodUrl]
    );
  };

  const handleStartStream = async () => {
    if (selectedVods.length === 0) {
      setMessage('Selecione pelo menos um VOD para iniciar a transmissão.');
      return;
    }
    try {
      await startStream(selectedVods, quality);
      setMessage('Transmissão iniciada com sucesso!');
      fetchData(); // Atualiza status após iniciar
    } catch (error: any) {
      setMessage(`Erro ao iniciar transmissão: ${error.response?.data?.detail || error.message}`);
    }
  };

  const handleStopStream = async () => {
    try {
      await stopStream();
      setMessage('Transmissão encerrada.');
      fetchData(); // Atualiza status após encerrar
    } catch (error: any) {
      setMessage(`Erro ao encerrar transmissão: ${error.response?.data?.detail || error.message}`);
    }
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      minHeight: '100vh',
      backgroundColor: '#282c34',
      color: '#fff',
      padding: '20px',
      fontFamily: 'Arial, sans-serif'
    }}>
      <h1>Bem-vindo, {username}!</h1>

      {message && (
        <div style={{
          backgroundColor: '#3a3a3a',
          color: '#fff',
          padding: '10px 20px',
          borderRadius: '5px',
          marginBottom: '20px',
          textAlign: 'center'
        }}>
          {message}
        </div>
      )}

      <div style={{
        backgroundColor: '#3a3a3a',
        padding: '15px 20px',
        borderRadius: '8px',
        marginBottom: '20px',
        width: 'calc(100% - 40px)',
        maxWidth: '800px',
        boxShadow: '0 4px 8px rgba(0, 0, 0, 0.2)'
      }}>
        <h2>Status da Transmissão</h2>
        <p>Status: <strong style={{ color: streamStatus.status === 'Transmitindo' ? '#4CAF50' : '#f44336' }}>{streamStatus.status}</strong></p>
        <p>VOD Atual: <strong>{streamStatus.current_vod}</strong></p>
        <div style={{ display: 'flex', gap: '10px', marginTop: '15px', justifyContent: 'center' }}>
          <button
            onClick={handleStartStream}
            disabled={streamStatus.status === 'Transmitindo' || selectedVods.length === 0}
            style={{
              padding: '10px 15px',
              backgroundColor: streamStatus.status === 'Transmitindo' ? '#666' : '#4CAF50',
              color: '#fff',
              border: 'none',
              borderRadius: '5px',
              cursor: streamStatus.status === 'Transmitindo' ? 'not-allowed' : 'pointer',
              fontSize: '1em'
            }}
          >
            Iniciar Transmissão
          </button>
          <button
            onClick={handleStopStream}
            disabled={streamStatus.status === 'Parado'}
            style={{
              padding: '10px 15px',
              backgroundColor: streamStatus.status === 'Parado' ? '#666' : '#f44336',
              color: '#fff',
              border: 'none',
              borderRadius: '5px',
              cursor: streamStatus.status === 'Parado' ? 'not-allowed' : 'pointer',
              fontSize: '1em'
            }}
          >
            Encerrar Transmissão
          </button>
        </div>
        <div style={{ marginTop: '15px', textAlign: 'center' }}>
          <label htmlFor="quality-select">Qualidade: </label>
          <select
            id="quality-select"
            value={quality}
            onChange={(e) => setQuality(e.target.value)}
            style={{
              padding: '8px',
              borderRadius: '5px',
              border: '1px solid #555',
              backgroundColor: '#444',
              color: '#fff'
            }}
          >
            <option value="best">Melhor</option>
            <option value="high">Alta</option>
            <option value="medium">Média</option>
            <option value="low">Baixa</option>
            <option value="mobile">Móvel</option>
            {/* Você pode adicionar mais opções de qualidade conforme a Twitch ou Streamlink oferecem */}
          </select>
        </div>
      </div>

      <div style={{
        backgroundColor: '#3a3a3a',
        padding: '15px 20px',
        borderRadius: '8px',
        width: 'calc(100% - 40px)',
        maxWidth: '800px',
        boxShadow: '0 4px 8px rgba(0, 0, 0, 0.2)'
      }}>
        <h2>Seus VODs Recentes</h2>
        {vods.length === 0 ? (
          <p>Nenhum VOD encontrado ou carregando...</p>
        ) : (
          <ul style={{ listStyle: 'none', padding: 0 }}>
            {vods.map(vod => (
              <li
                key={vod.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  backgroundColor: selectedVods.includes(vod.url) ? '#555' : '#444',
                  margin: '10px 0',
                  padding: '10px',
                  borderRadius: '5px',
                  cursor: 'pointer',
                  transition: 'background-color 0.2s',
                  boxShadow: '0 2px 4px rgba(0, 0, 0, 0.1)'
                }}
                onClick={() => handleVodSelect(vod.url)}
              >
                <input
                  type="checkbox"
                  checked={selectedVods.includes(vod.url)}
                  onChange={() => handleVodSelect(vod.url)}
                  style={{ marginRight: '15px', transform: 'scale(1.5)' }}
                />
                <img
                  src={vod.thumbnail_url.replace('%{width}', '120').replace('%{height}', '90')}
                  alt={vod.title}
                  style={{ width: '120px', height: '90px', marginRight: '15px', borderRadius: '5px' }}
                />
                <div style={{ flexGrow: 1 }}>
                  <h3 style={{ margin: 0, fontSize: '1.1em' }}>{vod.title}</h3>
                  <p style={{ margin: '5px 0 0', fontSize: '0.9em', color: '#ccc' }}>Duração: {vod.duration}</p>
                  <a
                    href={vod.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ color: '#9147ff', textDecoration: 'none', fontSize: '0.85em' }}
                    onClick={(e) => e.stopPropagation()} // Impede que o clique no link selecione o VOD
                  >
                    Ver no Twitch
                  </a>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};

export default Dashboard;