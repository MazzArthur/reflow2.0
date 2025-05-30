// frontend/src/api.ts

// A URL base do seu backend FastAPI
const BASE_URL = 'http://localhost:5000'; // Mude para a URL de produção quando deployar

// Interface para um VOD (Video On Demand)
interface Vod {
  id: string;
  title: string;
  url: string;
  thumbnail_url: string;
  duration: string;
}

// Interface para o status da transmissão
interface StreamStatus {
  status: string;
  current_vod: string;
}

// Função para iniciar o fluxo de autenticação OAuth da Twitch
export const startTwitchOAuth = () => {
  window.location.href = `${BASE_URL}/api/auth/twitch`;
};

// Função para fazer logout
export const logout = async () => {
  try {
    const response = await fetch(`${BASE_URL}/api/logout`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include', // Importante para enviar os cookies de sessão
    });
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  } catch (error) {
    console.error("Erro ao fazer logout:", error);
    throw error;
  }
};

// Função para buscar os VODs e o status da transmissão do usuário
export const getVods = async (): Promise<{ username: string; vods: Vod[]; status: StreamStatus }> => {
  try {
    const response = await fetch(`${BASE_URL}/api/vods`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include', // Importante para enviar os cookies de sessão
    });

    if (!response.ok) {
      // Se for 401 Unauthorized, o token pode ter expirado ou o usuário não está logado
      if (response.status === 401) {
        // Redireciona para o login e adiciona um erro na URL
        window.location.href = '/login?error=unauthenticated';
      }
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error("Erro ao buscar VODs:", error);
    throw error; // Propaga o erro para o componente lidar
  }
};

// Função para buscar apenas o status da transmissão (para polling)
export const getStreamStatus = async (): Promise<StreamStatus> => {
  try {
    const response = await fetch(`${BASE_URL}/api/stream_status`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include', // Importante para enviar os cookies de sessão
    });

    if (!response.ok) {
      if (response.status === 401) {
        // Redireciona para login se não estiver autenticado
        window.location.href = '/login?error=unauthenticated';
      }
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error("Erro ao buscar status da transmissão:", error);
    // Retorna um status de erro para que o Dashboard possa exibir
    return { status: 'Erro na API', current_vod: 'N/A' };
  }
};

// Função para iniciar uma transmissão REAL
// Agora aceita a streamKey como um parâmetro
export const startStream = async (vodUrls: string[], quality: string, streamKey: string) => {
  try {
    const response = await fetch(`${BASE_URL}/api/stream/start`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include', // Importante para enviar os cookies de sessão
      body: JSON.stringify({ vod_urls: vodUrls, quality: quality, stream_key: streamKey }), // Inclui a stream_key
    });

    if (!response.ok) {
      // Tenta ler a mensagem de erro do backend se disponível
      const errorData = await response.json();
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }
    return response.json();
  } catch (error) {
    console.error("Erro ao iniciar transmissão:", error);
    throw error; // Propaga o erro para o componente lidar
  }
};

// Função para encerrar uma transmissão
export const stopStream = async () => {
  try {
    const response = await fetch(`${BASE_URL}/api/stream/stop`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include', // Importante para enviar os cookies de sessão
    });

    if (!response.ok) {
      // Tenta ler a mensagem de erro do backend se disponível
      const errorData = await response.json();
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }
    return response.json();
  } catch (error) {
    console.error("Erro ao encerrar transmissão:", error);
    throw error; // Propaga o erro para o componente lidar
  }
};