import os
import httpx
import asyncio
import platform
import traceback
import subprocess
import threading
import queue
import streamlink # Importação essencial para o Streamlink

from dotenv import load_dotenv

from fastapi import FastAPI, Request, HTTPException, status, Body
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

# --- CÓDIGO DE DEBUG (manter para verificar .env) ---
print("--- DEBUG DE VARIÁVEIS DE AMBIENTE ---")
print(f"Valor de TWITCH_CLIENT_ID no .env: '{os.getenv('TWITCH_CLIENT_ID')}'")
print(f"Valor de TWITCH_CLIENT_SECRET no .env: '{os.getenv('TWITCH_CLIENT_SECRET')}'")
print(f"Valor de TWITCH_REDIRECT_URI no .env: '{os.getenv('TWITCH_REDIRECT_URI')}'")
print(f"Valor de SECRET_KEY no .env: '{os.getenv('SECRET_KEY')}'")
print(f"Valor de FFMPEG_PATH no .env: '{os.getenv('FFMPEG_PATH')}'")
print(f"Valor de STREAMLINK_PATH no .env: '{os.getenv('STREAMLINK_PATH')}'")
print("--- FIM DO DEBUG ---")

app = FastAPI()

# --- Configurações de Ambiente ---
CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
CLIENT_SECRET = os.getenv('TWITCH_CLIENT_SECRET')
REDIRECT_URI = os.getenv('TWITCH_REDIRECT_URI', "http://localhost:5000/api/auth/callback")
SECRET_KEY = os.getenv('SECRET_KEY', 'uma_chave_secreta_padrao_muito_longa_e_complexa_e_aleatoria_para_fins_de_desenvolvimento_apenas')

# --- CONFIGURAÇÃO PARA FERRAMENTAS EXTERNAS ---
# Certifique-se de que estes caminhos estão ABSOLUTOS e CORRETOS no seu .env
FFMPEG_PATH = os.getenv('FFMPEG_PATH', 'ffmpeg')
STREAMLINK_PATH = os.getenv('STREAMLINK_PATH', 'streamlink')

# Dicionários globais para gerenciar streams e status
# Chave: user_id, Valor: subprocess.Popen (objeto do processo FFmpeg)
active_streams = {}
# Chave: user_id, Valor: dict com status e current_vod
user_stream_status = {} # Para manter o status da stream por usuário

# Fila para VODs (se você quiser mais de um VOD em sequência)
# Chave: user_id, Valor: queue.Queue()
user_vod_queues = {}

# --- MODELO PARA A REQUISIÇÃO DE START STREAM ---
class StartStreamRequest(BaseModel):
    vod_urls: list[str]
    quality: str
    stream_key: str

# --- Configuração do CORS Middleware ---
origins = [
    "http://localhost:5173",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# --- ROTAS DA API ---

@app.get("/")
async def read_root():
    return {"message": "Bem-vindo ao Backend Twitch VODs!"}

@app.get("/api/auth/twitch", response_class=RedirectResponse)
async def twitch_auth():
    if not CLIENT_ID:
        raise HTTPException(status_code=500, detail="TWITCH_CLIENT_ID não configurado no .env")

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
    if error:
        print(f"Erro no callback Twitch: {error} - {error_description}")
        frontend_redirect_url = f"http://localhost:5173/login?error={error}&error_description={error_description}"
        return RedirectResponse(url=frontend_redirect_url, status_code=status.HTTP_302_FOUND)

    if not code:
        print("Código de autorização não recebido no callback.")
        frontend_redirect_url = "http://localhost:5173/login?error=no_code_received"
        return RedirectResponse(url=frontend_redirect_url, status_code=status.HTTP_302_FOUND)

    if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
        raise HTTPException(status_code=500, detail="Variáveis de ambiente Twitch não configuradas.")

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
            response.raise_for_status()
            token_data = response.json()
            access_token = token_data.get("access_token")
            refresh_token = token_data.get("refresh_token")

            if not access_token:
                print("Token de acesso não recebido.")
                frontend_redirect_url = "http://localhost:5173/login?error=no_access_token"
                return RedirectResponse(url=frontend_redirect_url, status_code=status.HTTP_302_FOUND)

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
                print("Dados do usuário não encontrados após autenticação.")
                frontend_redirect_url = "http://localhost:5173/login?error=user_info_failed"
                return RedirectResponse(url=frontend_redirect_url, status_code=status.HTTP_302_FOUND)

            username = user_data[0].get("display_name")
            user_id = user_data[0].get("id")

            request.session['user_access_token'] = access_token
            request.session['refresh_token'] = refresh_token
            request.session['username'] = username
            request.session['user_id'] = user_id

            # Inicializa o status para o novo usuário
            user_stream_status[user_id] = {"status": "Parado", "current_vod": "Nenhum"}

            print(f"Usuário {username} autenticado com sucesso. Redirecionando para o dashboard.")
            frontend_redirect_url = f"http://localhost:5173/dashboard?success=true&username={username}"
            return RedirectResponse(url=frontend_redirect_url, status_code=status.HTTP_302_FOUND)

        except httpx.HTTPStatusError as e:
            print(f"Erro HTTP na API da Twitch durante o callback: {e.response.status_code} - {e.response.text}")
            frontend_redirect_url = f"http://localhost:5173/login?error=twitch_api_error&details={e.response.status_code}"
            return RedirectResponse(url=frontend_redirect_url, status_code=status.HTTP_302_FOUND)
        except Exception as e:
            print(f"Erro inesperado no callback OAuth: {e}")
            frontend_redirect_url = f"http://localhost:5173/login?error=internal_server_error"
            return RedirectResponse(url=frontend_redirect_url, status_code=status.HTTP_302_FOUND)

@app.post("/api/logout")
async def logout(request: Request):
    user_id = request.session.get('user_id')
    if user_id and user_id in active_streams:
        process_to_kill = active_streams.pop(user_id)
        if process_to_kill.poll() is None:
            print(f"Encerrando stream ativa para {user_id} antes do logout.")
            process_to_kill.terminate()
        if user_id in user_stream_status:
            user_stream_status[user_id] = {"status": "Parado", "current_vod": "Nenhum"}

    request.session.clear()
    return {"message": "Sessão encerrada com sucesso."}

@app.get("/api/vods")
async def get_vods_data(request: Request):
    user_access_token = request.session.get('user_access_token')
    username = request.session.get('username')
    user_id = request.session.get('user_id')

    if not user_access_token or not username or not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado. Faça login via Twitch.")

    headers = {
        "Client-ID": CLIENT_ID,
        "Authorization": f"Bearer {user_access_token}",
    }

    vods_data = []
    # Pega o status atual do usuário. Se não existir, inicializa como parado.
    stream_status = user_stream_status.get(user_id, {"status": "Parado", "current_vod": "Nenhum"})

    async with httpx.AsyncClient() as client:
        try:
            videos_url = f"https://api.twitch.tv/helix/videos?user_id={user_id}&type=archive"
            videos_response = await client.get(videos_url, headers=headers)
            videos_response.raise_for_status()
            videos_json = videos_response.json()

            for video in videos_json.get('data', []):
                thumbnail = video.get("thumbnail_url", "").replace("%{width}x%{height}", "320x180")
                vods_data.append({
                    "id": video.get("id"),
                    "title": video.get("title"),
                    "url": video.get("url"),
                    "thumbnail_url": thumbnail,
                    "duration": video.get("duration"),
                })

            # Verifica o status da transmissão atual na Twitch API (para garantir que não estamos transmitindo de outro lugar)
            stream_url = f"https://api.twitch.tv/helix/streams?user_id={user_id}"
            stream_response = await client.get(stream_url, headers=headers)
            stream_response.raise_for_status()
            stream_json = stream_response.json()

            if stream_json.get('data'):
                current_stream = stream_json['data'][0]
                stream_status["status"] = "Ao Vivo" # Status da Twitch API
                stream_status["current_vod"] = current_stream.get("title", "Stream ao vivo")
            # Se não estiver ao vivo na Twitch, mas estiver transmitindo via backend, manter o status do backend
            elif user_id in active_streams and active_streams[user_id].poll() is None:
                stream_status["status"] = "Transmitindo (via Backend)"
                # current_vod é atualizado na função stream_vods_thread
            else:
                stream_status["status"] = "Parado"
                stream_status["current_vod"] = "Nenhum"


        except httpx.HTTPStatusError as e:
            print(f"Erro ao buscar dados da Twitch API (VODs/Stream Status): {e.response.status_code} - {e.response.text}")
            if e.response.status_code in [401, 403]:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de acesso Twitch inválido ou expirado. Faça login novamente.")
            else:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao comunicar com a API da Twitch: {e.response.text}")
        except Exception as e:
            print(f"Erro inesperado ao buscar VODs e status: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro interno ao buscar dados do Twitch.")

    # Atualiza o status global para o usuário
    user_stream_status[user_id] = stream_status

    return JSONResponse(content={
        "username": username,
        "vods": vods_data,
        "status": stream_status
    })

@app.get("/api/stream_status")
async def get_stream_status(request: Request):
    user_id = request.session.get('user_id')

    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado. Faça login via Twitch para verificar o status da transmissão.")

    # Retorna o status armazenado para o usuário
    current_status = user_stream_status.get(user_id, {"status": "Parado", "current_vod": "Nenhum"})

    # Verifica se o processo FFmpeg ainda está ativo
    if user_id in active_streams and active_streams[user_id].poll() is None:
        current_status["status"] = "Transmitindo (via Backend)"
    else:
        # Se o processo não está ativo, mas o status ainda diz transmitindo, corrige
        if current_status["status"] == "Transmitindo (via Backend)":
             current_status["status"] = "Parado"
             current_status["current_vod"] = "Nenhum"
        # Além disso, faz uma checagem rápida na Twitch API para ver se está ao vivo por fora
        headers = {
            "Client-ID": CLIENT_ID,
            "Authorization": f"Bearer {request.session.get('user_access_token')}",
        }
        async with httpx.AsyncClient() as client:
            try:
                stream_url = f"https://api.twitch.tv/helix/streams?user_id={user_id}"
                stream_response = await client.get(stream_url, headers=headers)
                stream_response.raise_for_status()
                stream_json = stream_response.json()
                if stream_json.get('data'):
                    current_stream = stream_json['data'][0]
                    current_status["status"] = "Ao Vivo"
                    current_status["current_vod"] = current_stream.get("title", "Stream ao vivo")
            except Exception as e:
                print(f"Erro ao verificar status da Twitch API no polling: {e}")
                pass # Apenas loga e mantém o status atual

    user_stream_status[user_id] = current_status # Atualiza o status global

    return JSONResponse(content=current_status)


# --- FUNÇÃO QUE EXECUTA A TRANSMISSÃO EM UMA THREAD SEPARADA (ADAPTADA E CORRIGIDA) ---
def stream_vods_thread(user_id: str, vod_urls: list[str], quality: str, stream_key: str):
    global active_streams
    global user_stream_status

    rtmp_url = f"rtmp://live.twitch.tv/app/{stream_key}"
    
    # Limpa a fila de VODs para este usuário e adiciona os novos
    if user_id not in user_vod_queues:
        user_vod_queues[user_id] = queue.Queue()
    else:
        while not user_vod_queues[user_id].empty():
            user_vod_queues[user_id].get()

    # Adiciona os VODs selecionados à fila
    for url in vod_urls:
        try:
            streams = streamlink.streams(url)
            m3u8_url = None # Inicializa como None
            if quality in streams:
                m3u8_url = streams[quality].url
            elif 'best' in streams: # Verifica se 'best' existe como fallback
                m3u8_url = streams['best'].url

            if m3u8_url: # Agora verifica a variável m3u8_url corretamente
                user_vod_queues[user_id].put(m3u8_url)
            else:
                print(f"[{user_id}] Aviso: Não foi possível obter URL M3U8 para VOD: {url} com qualidade '{quality}'.")
        except streamlink.exceptions.NoStreamsError:
            print(f"[{user_id}] Aviso: Nenhuma stream encontrada para VOD: {url}")
        except Exception as e:
            print(f"[{user_id}] Erro ao obter URL M3U8 para {url}: {e}")
            traceback.print_exc() # Imprime o stack trace completo para depuração

    if user_vod_queues[user_id].empty():
        print(f"[{user_id}] Nenhuma URL de VOD válida foi adicionada à fila. Encerrando thread de stream.")
        user_stream_status[user_id] = {"status": "Parado", "current_vod": "Nenhum"}
        if user_id in active_streams:
            del active_streams[user_id]
        return

    print(f"[{user_id}] Iniciando processo FFmpeg principal para RTMP: {rtmp_url}")
    user_stream_status[user_id] = {"status": "Transmitindo (via Backend)", "current_vod": "Iniciando..."}
    
    ffmpeg_process = None # Inicializa para o bloco finally
    try:
        ffmpeg_process = subprocess.Popen(
            [FFMPEG_PATH, "-i", "-", "-c:v", "copy", "-c:a", "aac", "-f", "flv", rtmp_url],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            bufsize=0
        )
        active_streams[user_id] = ffmpeg_process

        def log_ffmpeg_stderr(proc, user_id_log):
            for line in proc.stderr:
                print(f"[{user_id_log}][FFmpeg STDERR]: {line.decode(errors='ignore').strip()}")
        threading.Thread(target=log_ffmpeg_stderr, args=(ffmpeg_process, user_id), daemon=True).start()

        while not user_vod_queues[user_id].empty() and ffmpeg_process.poll() is None:
            vod_url = user_vod_queues[user_id].get()
            print(f"[{user_id}] Transmitindo VOD: {vod_url}")
            user_stream_status[user_id]["current_vod"] = vod_url
            
            decode_proc = subprocess.Popen(
                [FFMPEG_PATH, "-i", vod_url, "-f", "mpegts", "-c:v", "copy", "-c:a", "aac", "-"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            
            while True:
                chunk = decode_proc.stdout.read(4096)
                if not chunk:
                    break
                try:
                    ffmpeg_process.stdin.write(chunk)
                except BrokenPipeError:
                    print(f"[{user_id}] BrokenPipeError: FFmpeg principal encerrou inesperadamente.")
                    break
                except ValueError:
                    print(f"[{user_id}] ValueError: stdin do FFmpeg principal foi fechado.")
                    break
            decode_proc.wait()

        if ffmpeg_process and ffmpeg_process.stdin:
            ffmpeg_process.stdin.close()
        if ffmpeg_process:
            ffmpeg_process.wait()
            print(f"[{user_id}] FFmpeg principal terminou com código: {ffmpeg_process.returncode}")

    except FileNotFoundError as e:
        print(f"[{user_id}] Erro: Comando não encontrado - '{e.filename}'. Certifique-se de que FFmpeg e Streamlink estão instalados e no PATH do servidor, ou que os caminhos em .env estão corretos.")
        user_stream_status[user_id] = {"status": "Erro", "current_vod": f"Ferramenta não encontrada: {e.filename}"}
    except Exception as e:
        print(f"[{user_id}] Erro inesperado na thread de stream: {e}")
        traceback.print_exc()
        user_stream_status[user_id] = {"status": "Erro", "current_vod": f"Erro interno: {str(e)}"}
    finally:
        if user_id in active_streams:
            proc = active_streams.pop(user_id)
            if proc and proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=5)
            print(f"[{user_id}] Processo FFmpeg limpo.")
        
        user_stream_status[user_id] = {"status": "Parado", "current_vod": "Nenhum"}
        print(f"[{user_id}] Thread de transmissão encerrada. Status: Parado.")


# --- Rota para iniciar transmissão (AGORA CHAMA A THREAD) ---
@app.post("/api/stream/start")
async def start_stream_route(request: Request, stream_data: StartStreamRequest):
    user_id = request.session.get('user_id')

    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado. Faça login.")

    if not stream_data.stream_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A Stream Key é necessária para iniciar a transmissão.")

    if not stream_data.vod_urls:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pelo menos um VOD deve ser selecionado para iniciar a transmissão.")

    if user_id in active_streams and active_streams[user_id].poll() is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Uma transmissão já está ativa para este usuário.")

    print(f"[{user_id}] Requisição para iniciar transmissão recebida.")
    
    threading.Thread(target=stream_vods_thread, args=(
        user_id,
        stream_data.vod_urls,
        stream_data.quality,
        stream_data.stream_key
    ), daemon=True).start()

    return JSONResponse(content={"message": "Iniciando transmissão em segundo plano. Verifique o status."})

@app.post("/api/stream/stop")
async def stop_stream_route(request: Request):
    user_id = request.session.get('user_id')

    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado. Faça login.")

    if user_id not in active_streams:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nenhuma transmissão ativa encontrada para este usuário.")

    ffmpeg_process_to_kill = active_streams.pop(user_id)
    user_stream_status[user_id] = {"status": "Parando...", "current_vod": "Nenhum"}

    if ffmpeg_process_to_kill.poll() is None:
        print(f"[{user_id}] Encerrando transmissão. PID do FFmpeg: {ffmpeg_process_to_kill.pid}")
        try:
            ffmpeg_process_to_kill.terminate()
            print(f"[{user_id}] Sinal de terminação enviado ao FFmpeg.")
            user_stream_status[user_id] = {"status": "Parado", "current_vod": "Nenhum"}
            return JSONResponse(content={"message": "Sinal de encerramento enviado. Verifique o status."})
        except Exception as e:
            print(f"[{user_id}] Erro ao encerrar processo: {e}")
            user_stream_status[user_id] = {"status": "Erro", "current_vod": f"Erro ao encerrar: {str(e)}"}
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao encerrar transmissão: {str(e)}")
    else:
        print(f"[{user_id}] Processo já não estava rodando ao tentar encerrar.")
        user_stream_status[user_id] = {"status": "Parado", "current_vod": "Nenhum"}
        return JSONResponse(content={"message": "Transmissão já estava inativa."})