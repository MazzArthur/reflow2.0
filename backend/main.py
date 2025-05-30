from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
import os
import httpx
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

# --- INÍCIO DO CÓDIGO DE DEBUG ---
# Estas linhas imprimirão os valores das suas variáveis de ambiente no terminal do backend.
print("--- DEBUG DE VARIÁVEIS DE AMBIENTE ---")
print(f"Valor de TWITCH_CLIENT_ID no .env: '{os.getenv('TWITCH_CLIENT_ID')}'")
print(f"Valor de TWITCH_CLIENT_SECRET no .env: '{os.getenv('TWITCH_CLIENT_SECRET')}'")
print(f"Valor de TWITCH_REDIRECT_URI no .env: '{os.getenv('TWITCH_REDIRECT_URI')}'")
print(f"Valor de SECRET_KEY no .env: '{os.getenv('SECRET_KEY')}'")
print("--- FIM DO DEBUG ---")
# --- FIM DO CÓDIGO DE DEBUG ---

app = FastAPI()

# --- Configurações de Ambiente ---
# Pega as variáveis de ambiente. Se não existirem, usa um valor padrão ou None.
CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
CLIENT_SECRET = os.getenv('TWITCH_CLIENT_SECRET')
REDIRECT_URI = os.getenv('TWITCH_REDIRECT_URI', "http://localhost:5000/api/auth/callback")
# A SECRET_KEY é crucial para a segurança da sessão. Use uma chave longa e aleatória.
SECRET_KEY = os.getenv('SECRET_KEY', 'uma_chave_secreta_padrao_muito_longa_e_complexa_e_aleatoria_para_fins_de_desenvolvimento_apenas')

# --- Configuração do CORS Middleware ---
# A porta do seu frontend React é 5173.
origins = [
    "http://localhost:5173",  # O frontend React rodará nesta porta
    "http://localhost:3000",  # Uma porta alternativa comum para frontend React
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True, # ESSENCIAL: Permite que o navegador envie cookies de sessão
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], # Métodos HTTP permitidos
    allow_headers=["*"], # Permite todos os cabeçalhos HTTP
)

# --- Configuração do Session Middleware ---
# Usa a SECRET_KEY para criptografar os cookies de sessão.
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# --- Rotas ---

@app.get("/")
async def read_root():
    return {"message": "Bem-vindo ao Backend Twitch VODs!"}

@app.get("/api/auth/twitch", response_class=RedirectResponse)
async def twitch_auth():
    """
    Redireciona o usuário para a página de autorização do Twitch.
    """
    if not CLIENT_ID:
        raise HTTPException(status_code=500, detail="TWITCH_CLIENT_ID não configurado no .env")

    # Scopes necessários para acessar e-mail do usuário e VODs/informações de transmissão.
    # 'user:read:email': Permite ler o endereço de e-mail verificado do usuário.
    # 'user:read:broadcast': Permite acessar informações de transmissão do usuário (inclui VODs).
    scopes = "user:read:email user:read:broadcast"
    twitch_auth_url = (
        f"https://id.twitch.tv/oauth2/authorize?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope={scopes}"
    )
    return RedirectResponse(url=twitch_auth_url)

@app.get("/api/auth/callback")
async def twitch_callback(request: Request, code: str = None, error: str = None, error_description: str = None):
    """
    Endpoint de callback para o Twitch OAuth.
    Recebe o código de autorização e troca por um token de acesso.
    Armazena o token e informações do usuário na sessão.
    """
    # Se houve um erro no OAuth da Twitch
    if error:
        frontend_redirect_url = f"http://localhost:5173/login?error={error}&error_description={error_description}"
        return RedirectResponse(url=frontend_redirect_url, status_code=status.HTTP_302_FOUND)

    # Se o código de autorização não foi recebido
    if not code:
        frontend_redirect_url = "http://localhost:5173/login?error=no_code_received"
        return RedirectResponse(url=frontend_redirect_url, status_code=status.HTTP_302_FOUND)

    # Verifica se as credenciais da Twitch estão configuradas
    if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
        raise HTTPException(status_code=500, detail="Variáveis de ambiente Twitch não configuradas.")

    # Troca o código de autorização por um token de acesso
    token_url = "https://id.twitch.tv/oauth2/token"
    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(token_url, data=payload)
            response.raise_for_status()  # Levanta uma exceção para códigos de status 4xx/5xx
            token_data = response.json()
            access_token = token_data.get("access_token")
            refresh_token = token_data.get("refresh_token") # É bom guardar para renovar o token no futuro

            if not access_token:
                frontend_redirect_url = "http://localhost:5173/login?error=no_access_token"
                return RedirectResponse(url=frontend_redirect_url, status_code=status.HTTP_302_FOUND)

            # Usa o token de acesso para obter informações do usuário
            user_info_url = "https://api.twitch.tv/helix/users"
            headers = {
                "Client-ID": CLIENT_ID,
                "Authorization": f"Bearer {access_token}",
            }
            user_info_response = await client.get(user_info_url, headers=headers)
            user_info_response.raise_for_status()
            user_info_data = user_info_response.json()
            user_data = user_info_data.get("data")
            if not user_data:
                frontend_redirect_url = "http://localhost:5173/login?error=user_info_failed"
                return RedirectResponse(url=frontend_redirect_url, status_code=status.HTTP_302_FOUND)

            username = user_data[0].get("display_name")
            user_id = user_data[0].get("id")

            # Armazena os dados essenciais do usuário na sessão do FastAPI
            request.session['user_access_token'] = access_token
            request.session['refresh_token'] = refresh_token
            request.session['username'] = username
            request.session['user_id'] = user_id

            # Redireciona de volta para o frontend, passando o sucesso e o nome de usuário na URL
            frontend_redirect_url = f"http://localhost:5173/dashboard?success=true&username={username}"
            return RedirectResponse(url=frontend_redirect_url, status_code=status.HTTP_302_FOUND)

        except httpx.HTTPStatusError as e:
            # Captura erros HTTP (ex: 400, 500) da API da Twitch
            print(f"Erro HTTP na API da Twitch: {e.response.status_code} - {e.response.text}")
            frontend_redirect_url = f"http://localhost:5173/login?error=twitch_api_error&details={e.response.status_code}"
            return RedirectResponse(url=frontend_redirect_url, status_code=status.HTTP_302_FOUND)
        except Exception as e:
            # Captura outros erros inesperados
            print(f"Erro inesperado no callback OAuth: {e}")
            frontend_redirect_url = f"http://localhost:5173/login?error=internal_server_error"
            return RedirectResponse(url=frontend_redirect_url, status_code=status.HTTP_302_FOUND)

@app.get("/api/vods")
async def get_vods_data(request: Request):
    """
    Retorna os VODs (vídeos) e o status da transmissão do usuário logado.
    Requer autenticação via sessão.
    """
    # Tenta recuperar os dados do usuário da sessão
    user_access_token = request.session.get('user_access_token')
    username = request.session.get('username')
    user_id = request.session.get('user_id')

    # Se qualquer dado essencial estiver faltando na sessão, o usuário não está autenticado.
    if not user_access_token or not username or not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado. Faça login via Twitch.")

    headers = {
        "Client-ID": CLIENT_ID,
        "Authorization": f"Bearer {user_access_token}",
    }

    vods_data = []
    stream_status = {"status": "Parado", "current_vod": "Nenhum"}

    async with httpx.AsyncClient() as client:
        try:
            # 1. Buscar VODs (vídeos arquivados) do usuário
            videos_url = f"https://api.twitch.tv/helix/videos?user_id={user_id}&type=archive"
            videos_response = await client.get(videos_url, headers=headers)
            videos_response.raise_for_status() # Levanta exceção para erros HTTP
            videos_json = videos_response.json()

            for video in videos_json.get('data', []):
                # Formata a URL da thumbnail para um tamanho fixo (320x180)
                thumbnail = video.get("thumbnail_url", "").replace("%{width}x%{height}", "320x180")
                vods_data.append({
                    "id": video.get("id"),
                    "title": video.get("title"),
                    "url": video.get("url"),
                    "thumbnail_url": thumbnail,
                    "duration": video.get("duration"),
                })

            # 2. Buscar status da transmissão atual do usuário
            stream_url = f"https://api.twitch.tv/helix/streams?user_id={user_id}"
            stream_response = await client.get(stream_url, headers=headers)
            stream_response.raise_for_status() # Levanta exceção para erros HTTP
            stream_json = stream_response.json()

            if stream_json.get('data'):
                # Se há dados, o usuário está transmitindo ao vivo
                current_stream = stream_json['data'][0]
                stream_status["status"] = "Ao Vivo"
                stream_status["current_vod"] = current_stream.get("title", "Stream ao vivo")
            else:
                # Caso contrário, o usuário não está transmitindo
                stream_status["status"] = "Parado"
                stream_status["current_vod"] = "Nenhum"

        except httpx.HTTPStatusError as e:
            # Captura erros específicos da API da Twitch (ex: token expirado, permissões insuficientes)
            print(f"Erro ao buscar dados da Twitch API: {e.response.status_code} - {e.response.text}")
            if e.response.status_code in [401, 403]:
                # Se o token estiver expirado ou inválido, força o logout (solicita novo login)
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de acesso Twitch inválido ou expirado. Faça login novamente.")
            else:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao comunicar com a API da Twitch: {e.response.text}")
        except Exception as e:
            # Captura outros erros inesperados no processo de busca de VODs
            print(f"Erro inesperado ao buscar VODs e status: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro interno ao buscar dados do Twitch.")

    # Retorna os dados como JSON
    return JSONResponse(content={
        "username": username,
        "vods": vods_data,
        "status": stream_status
    })

# --- Rota para iniciar transmissão (Exemplo: Funcionalidade simulada) ---
@app.post("/api/stream/start")
async def start_stream_route(request: Request, quality: str):
    user_access_token = request.session.get('user_access_token')
    user_id = request.session.get('user_id')

    if not user_access_token or not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado.")

    # IMPORTANTE: Iniciar uma transmissão real requer:
    # 1. Escopos OAuth adicionais (ex: 'channel:manage:broadcast').
    # 2. Integração com APIs da Twitch que gerenciam a transmissão (ex: APIs de Stream Key ou ferramentas de OBS).
    # Este é apenas um exemplo SIMULADO para demonstrar a chamada do frontend.
    print(f"Simulando início de transmissão para {user_id} com qualidade {quality}")
    return {"message": f"Transmissão simulada iniciada com qualidade: {quality}"}

# --- Rota para encerrar transmissão (Exemplo: Funcionalidade simulada) ---
@app.post("/api/stream/stop")
async def stop_stream_route(request: Request):
    user_access_token = request.session.get('user_access_token')
    user_id = request.session.get('user_id')

    if not user_access_token or not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado.")

    # IMPORTANTE: Encerrar uma transmissão real requer:
    # 1. Escopos OAuth adicionais (ex: 'channel:manage:broadcast').
    # 2. Integração com APIs da Twitch que gerenciam a transmissão.
    # Este é apenas um exemplo SIMULADO.
    print(f"Simulando encerramento de transmissão para {user_id}")
    return {"message": "Transmissão simulada encerrada."}

# --- Rota para Logout ---
@app.post("/api/logout")
async def logout(request: Request):
    """
    Limpa os dados da sessão do usuário.
    """
    request.session.clear() # Limpa todos os dados da sessão
    return {"message": "Sessão encerrada com sucesso."}

@app.get("/api/stream_status")
async def get_stream_status(request: Request):
    """
    Verifica e retorna o status atual da transmissão do usuário logado (Ao Vivo/Parado).
    """
    user_access_token = request.session.get('user_access_token')
    user_id = request.session.get('user_id')

    if not user_access_token or not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado. Faça login via Twitch para verificar o status da transmissão.")

    headers = {
        "Client-ID": os.getenv('TWITCH_CLIENT_ID'), # Usa CLIENT_ID diretamente aqui
        "Authorization": f"Bearer {user_access_token}",
    }

    stream_status_info = {"status": "Parado", "current_vod": "Nenhum"}

    async with httpx.AsyncClient() as client:
        try:
            stream_url = f"https://api.twitch.tv/helix/streams?user_id={user_id}"
            stream_response = await client.get(stream_url, headers=headers)
            stream_response.raise_for_status() # Levanta exceção para erros HTTP
            stream_json = stream_response.json()

            if stream_json.get('data'):
                current_stream = stream_json['data'][0]
                stream_status_info["status"] = "Ao Vivo"
                stream_status_info["current_vod"] = current_stream.get("title", "Stream ao vivo")
            else:
                stream_status_info["status"] = "Parado"
                stream_status_info["current_vod"] = "Nenhum"

        except httpx.HTTPStatusError as e:
            print(f"Erro ao buscar status da transmissão na Twitch API: {e.response.status_code} - {e.response.text}")
            if e.response.status_code in [401, 403]:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de acesso Twitch inválido ou expirado ao verificar status. Faça login novamente.")
            else:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao comunicar com a API da Twitch para status: {e.response.text}")
        except Exception as e:
            print(f"Erro inesperado ao buscar status da transmissão: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro interno ao buscar status da transmissão.")

    return JSONResponse(content=stream_status_info)