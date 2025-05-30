import axios from 'axios';

// A URL base do seu backend FastAPI
const BASE_URL = 'http://localhost:5000'; // Mude para a URL de produção quando deployar

const api = axios.create({
  baseURL: BASE_URL,
  withCredentials: true, // Importante para enviar e receber cookies de sessão (CORS)
});

export const startTwitchOAuth = () => {
  // Redireciona o navegador para o endpoint OAuth do FastAPI
  window.location.href = `${BASE_URL}/api/auth/twitch`;
};

export const getVods = async () => {
  try {
    const response = await api.get('/api/vods');
    return response.data;
  } catch (error) {
    console.error('Erro ao buscar VODs:', error);
    throw error;
  }
};

export const startStream = async (vodUrls: string[], quality: string = 'best') => {
  try {
    const formData = new FormData();
    vodUrls.forEach(url => {
      formData.append('vod_urls', url);
    });
    formData.append('quality', quality);

    const response = await api.post('/api/iniciar', formData, {
      headers: {
        'Content-Type': 'multipart/form-data', // Importante para `Form(...)` no FastAPI
      },
    });
    return response.data;
  } catch (error) {
    console.error('Erro ao iniciar transmissão:', error);
    throw error;
  }
};

export const stopStream = async () => {
  try {
    const response = await api.post('/api/encerrar');
    return response.data;
  } catch (error) {
    console.error('Erro ao encerrar transmissão:', error);
    throw error;
  }
};

export const getStreamStatus = async () => {
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
        return { status: 'Erro', current_vod: 'Não autenticado' };
      }
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error("Erro ao buscar status da transmissão:", error);
    return { status: 'Erro', current_vod: 'Falha na conexão' };
  }
};

export default api;