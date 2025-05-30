import React, { useEffect, useState, useCallback } from 'react';
import { getVods, startStream, stopStream, getStreamStatus, logout } from '../api';

// Interfaces para os tipos de dados esperados
interface Vod {
  id: string;
  title: string;
  url: string;
  thumbnail_url: string;
  duration: string;
}

interface StreamStatus {
  status: string; // Ex: "Parado", "Ao Vivo", "Transmitindo (via Backend)"
  current_vod: string; // Ex: "Nenhum", "Título da live", "VOD selecionado"
}

const Dashboard: React.FC = () => {
  // Estados do componente
  const [username, setUsername] = useState<string>('');
  const [vods, setVods] = useState<Vod[]>([]);
  const [selectedVods, setSelectedVods] = useState<string[]>([]);
  const [quality, setQuality] = useState<string>('best');
  const [streamStatus, setStreamStatus] = useState<StreamStatus>({ status: 'Carregando...', current_vod: 'Carregando...' });
  const [message, setMessage] = useState<string | null>(null);
  const [streamKey, setStreamKey] = useState<string>(''); // Novo estado para a Stream Key
  const [loading, setLoading] = useState<boolean>(true); // Para indicar que os dados estão sendo carregados

  // Função para buscar VODs e o status inicial da transmissão
  const fetchData = useCallback(async () => {
    try {
      setLoading(true); // Inicia o estado de carregamento
      setMessage(null); // Limpa mensagens anteriores
      const data = await getVods(); // Chama a API para obter VODs e status
      setUsername(data.username);
      setVods(data.vods);
      setStreamStatus(data.status); // Atualiza o status da transmissão
    } catch (error: any) {
      console.error("Erro ao carregar dados do dashboard:", error);
      // Se não autenticado, redireciona para login
      if (error.message.includes("401") || (error.response && error.response.status === 401)) {
        window.location.href = '/login';
      } else {
        setMessage(`Erro ao carregar dados: ${error.message || 'Desconhecido'}`);
      }
    } finally {
      setLoading(false); // Finaliza o estado de carregamento
    }
  }, []);

  // Efeito para buscar dados na montagem do componente e configurar o polling de status
  useEffect(() => {
    fetchData(); // Chama a função para carregar dados iniciais

    // Configura um polling para o status da transmissão a cada 5 segundos
    const statusInterval = setInterval(async () => {
      try {
        const statusData = await getStreamStatus(); // Chama a API para obter apenas o status
        setStreamStatus(statusData); // Atualiza o estado do status
      } catch (error) {
        console.error("Erro ao atualizar status:", error);
        // Não redireciona para login automaticamente em caso de erro de polling para evitar loops
        // Mas pode exibir uma mensagem de erro temporária
        setMessage("Não foi possível atualizar o status da transmissão.");
      }
    }, 5000); // Atualiza a cada 5 segundos (5000 milissegundos)

    // Limpa o intervalo quando o componente é desmontado para evitar vazamento de memória
    return () => clearInterval(statusInterval);
  }, [fetchData]); // `fetchData` como dependência para garantir que o efeito seja re-executado se `fetchData` mudar (raro)

  // Manipulador para seleção/desseleção de VODs
  const handleVodSelect = (vodUrl: string) => {
    setSelectedVods(prev =>
      prev.includes(vodUrl) ? prev.filter(url => url !== vodUrl) : [...prev, vodUrl]
    );
  };

  // Função auxiliar para extrair uma mensagem de erro útil
  const getErrorMessage = (error: any): string => {
    if (error instanceof Error) {
      // Caso seja um erro padrão ou um erro lançado de api.ts com .message
      return error.message;
    } 
    // Tenta acessar 'detail' se o erro for um objeto JSON do FastAPI
    if (error && typeof error === 'object' && 'detail' in error) {
        // Se 'detail' for uma string
        if (typeof error.detail === 'string') {
            return error.detail;
        } 
        // Se 'detail' for uma lista de objetos (erros de validação do Pydantic)
        if (Array.isArray(error.detail) && error.detail.length > 0 && typeof error.detail[0].msg === 'string') {
            // Concatena as mensagens de erro de validação
            return error.detail.map((err: any) => err.msg).join('; ');
        }
    }
    // Caso o erro seja uma string direta
    if (typeof error === 'string') {
      return error;
    }
    // Fallback para erros desconhecidos
    return 'Ocorreu um erro desconhecido.';
  };


  // Manipulador para iniciar a transmissão
  const handleStartStream = async () => {
    // Validações antes de iniciar a stream
    if (selectedVods.length === 0) {
      setMessage('Selecione pelo menos um VOD para iniciar a transmissão.');
      return;
    }
    if (!streamKey) { // Verifica se a stream key está vazia
      setMessage('Por favor, insira sua Stream Key da Twitch para iniciar a transmissão.');
      return;
    }
    if (streamStatus.status === 'Ao Vivo' || streamStatus.status === 'Transmitindo (via Backend)') {
      setMessage('Uma transmissão já está ativa.');
      return;
    }

    setMessage('Iniciando transmissão...'); // Feedback imediato ao usuário
    try {
      // Chama a função startStream da API, passando os VODs, qualidade e a streamKey
      await startStream(selectedVods, quality, streamKey);
      setMessage('Transmissão iniciada com sucesso! Verifique seu canal na Twitch.');
      // O polling de status deve atualizar o status para "Ao Vivo" ou "Transmitindo"
    } catch (error: any) {
      console.error("Erro completo ao iniciar transmissão:", error); // Log para depuração
      setMessage(`Erro ao iniciar transmissão: ${getErrorMessage(error)}`); // Usa a nova função
    }
  };

  // Manipulador para encerrar a transmissão
  const handleStopStream = async () => {
    setMessage('Encerrando transmissão...'); // Feedback imediato ao usuário
    try {
      await stopStream(); // Chama a função stopStream da API
      setMessage('Transmissão encerrada.');
      // O polling de status vai atualizar a UI para "Parado"
    } catch (error: any) {
      console.error("Erro completo ao encerrar transmissão:", error); // Log para depuração
      setMessage(`Erro ao encerrar transmissão: ${getErrorMessage(error)}`); // Usa a nova função
    }
  };

  // Manipulador para o logout
  const handleLogout = async () => {
    try {
      await logout();
      window.location.href = '/login'; // Redireciona para a página de login após o logout
    } catch (error) {
      console.error("Erro ao fazer logout:", error);
      alert("Erro ao fazer logout. Tente novamente.");
    }
  };

  // Exibe mensagem de carregamento enquanto os dados são buscados
  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', backgroundColor: '#282c34', color: '#fff' }}>
        Carregando dashboard...
      </div>
    );
  }

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
      <header style={{ width: '100%', maxWidth: '800px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h1>Bem-vindo, {username}!</h1>
        <button
          onClick={handleLogout}
          style={{
            padding: '8px 15px',
            backgroundColor: '#f44336',
            color: '#fff',
            border: 'none',
            borderRadius: '5px',
            cursor: 'pointer',
            fontSize: '0.9em'
          }}
        >
          Logout
        </button>
      </header>

      {/* Área para exibir mensagens de status/erro */}
      {message && (
        <div style={{
          backgroundColor: '#3a3a3a',
          color: '#fff',
          padding: '10px 20px',
          borderRadius: '5px',
          marginBottom: '20px',
          textAlign: 'center',
          width: 'calc(100% - 40px)',
          maxWidth: '800px',
          boxShadow: '0 4px 8px rgba(0, 0, 0, 0.2)'
        }}>
          {message}
        </div>
      )}

      {/* Seção de Status da Transmissão e Controles */}
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
        <p>Status: <strong style={{ color: streamStatus.status === 'Ao Vivo' || streamStatus.status === 'Transmitindo (via Backend)' ? '#4CAF50' : '#f44336' }}>{streamStatus.status}</strong></p>
        <p>VOD Atual: <strong>{streamStatus.current_vod}</strong></p>

        {/* Campo para a Stream Key */}
        <div style={{ marginTop: '15px', textAlign: 'center' }}>
          <label htmlFor="stream-key" style={{ marginRight: '10px' }}>Stream Key da Twitch:</label>
          <input
            id="stream-key"
            type="password" // Tipo password para ocultar a chave
            value={streamKey}
            onChange={(e) => setStreamKey(e.target.value)}
            placeholder="Cole sua Twitch Stream Key aqui"
            style={{
              padding: '8px',
              borderRadius: '5px',
              border: '1px solid #555',
              backgroundColor: '#444',
              color: '#fff',
              width: '80%', // Ajuste para melhor responsividade
              maxWidth: '300px' // Limite máximo para a largura do input
            }}
          />
          <p style={{ fontSize: '0.8em', color: '#ffcc00', marginTop: '5px' }}>
            Aviso: Sua Stream Key é secreta! Não a compartilhe com ninguém.
          </p>
        </div>

        {/* Botões de Iniciar/Encerrar Transmissão e Seleção de Qualidade */}
        <div style={{ display: 'flex', gap: '10px', marginTop: '15px', justifyContent: 'center', flexWrap: 'wrap' }}>
          <button
            onClick={handleStartStream}
            // Desabilita se já estiver transmitindo, se não houver VOD selecionado, ou se a stream key estiver vazia
            disabled={streamStatus.status === 'Ao Vivo' || streamStatus.status === 'Transmitindo (via Backend)' || selectedVods.length === 0 || !streamKey}
            style={{
              padding: '10px 15px',
              backgroundColor: (streamStatus.status === 'Ao Vivo' || streamStatus.status === 'Transmitindo (via Backend)' || selectedVods.length === 0 || !streamKey) ? '#666' : '#4CAF50',
              color: '#fff',
              border: 'none',
              borderRadius: '5px',
              cursor: (streamStatus.status === 'Ao Vivo' || streamStatus.status === 'Transmitindo (via Backend)' || selectedVods.length === 0 || !streamKey) ? 'not-allowed' : 'pointer',
              fontSize: '1em'
            }}
          >
            Iniciar Transmissão
          </button>
          <button
            onClick={handleStopStream}
            // Desabilita se o status for "Parado"
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
          <label htmlFor="quality-select" style={{ marginRight: '10px' }}>Qualidade do VOD:</label>
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
            <option value="best">Melhor (Recomendado)</option>
            <option value="high">Alta</option>
            <option value="medium">Média</option>
            <option value="low">Baixa</option>
            <option value="mobile">Móvel</option>
            {/* Você pode adicionar mais opções de qualidade conforme a Twitch ou Streamlink oferecem */}
          </select>
        </div>
      </div>

      {/* Seção de Seus VODs Recentes */}
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
          <p style={{ textAlign: 'center', color: '#ccc' }}>Nenhum VOD encontrado ou carregando...</p>
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
                  onChange={() => handleVodSelect(vod.url)} // Manter onChange separado para acessibilidade
                  style={{ marginRight: '15px', transform: 'scale(1.5)' }}
                />
                <img
                  src={vod.thumbnail_url} // A URL já vem formatada do backend
                  alt={vod.title}
                  style={{ width: '120px', height: '90px', marginRight: '15px', borderRadius: '5px', objectFit: 'cover' }}
                />
                <div style={{ flexGrow: 1 }}>
                  <h3 style={{ margin: 0, fontSize: '1.1em' }}>{vod.title}</h3>
                  <p style={{ margin: '5px 0 0', fontSize: '0.9em', color: '#ccc' }}>Duração: {vod.duration}</p>
                  <a
                    href={vod.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ color: '#9147ff', textDecoration: 'none', fontSize: '0.85em' }}
                    onClick={(e) => e.stopPropagation()} // Impede que o clique no link selecione/desselecione o VOD
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