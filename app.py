from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import requests
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from dotenv import load_dotenv
import os

# Cargar variables de entorno
load_dotenv()

app = FastAPI()

# Configuración del modelo de Google
CREDENTIALS_PATH = "mineria-441617-5eff761d48fd.json"  # Cambiar según ubicación real
SCOPES = ["https://www.googleapis.com/auth/generative-language"]
API_ENDPOINT = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent'

# Esquemas de entrada y salida
class TextRequest(BaseModel):
    content: str
    author: str

class TextResponse(BaseModel):
    corrected_text: str
    contains_bad_words: bool

# Obtener token de acceso
def get_access_token():    
    credentials = service_account.Credentials.from_service_account_file(
        CREDENTIALS_PATH, scopes=SCOPES)
    credentials.refresh(Request())
    return credentials.token

# Revisar texto con la API de Google
import time

# Revisar texto con la API de Google
def revisar_texto_google(post: dict):
    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Construir el prompt dinámico
    prompt_inicial = (
        "Eres un sistema avanzado de corrección y análisis de texto. Tus tareas son:\n"
        "1. Corregir errores ortográficos y gramaticales en el texto proporcionado.\n"
        "2. Detectar y marcar si el texto contiene palabras o frases extremadamente ofensivas, discriminatorias o explícitas.\n"
        "3. No hagas juicios sobre intenciones o contextos subyacentes. Solo analiza el contenido literal.\n"
        "4. Si el texto contiene lenguaje ofensivo o explícito, responde con 'Inapropiado'.\n"
        "5. Si el texto no contiene lenguaje ofensivo, responde con 'Texto corregido: [texto corregido]'.\n"
        "6. Ignora errores menores de ortografía a menos que afecten la interpretación del contenido.\n\n"
    )
    
    texto_a_procesar = f"Post: {post['content']}"
    payload = {
        "contents": [
            {"parts": [{"text": prompt_inicial + texto_a_procesar}]}
        ]
    }
    
    print(f"Solicitando a la API de Google con el siguiente payload: {payload}")  # Agregar esta línea
    
    # Intentar enviar la solicitud con reintentos en caso de error 503
    for attempt in range(5):  # Intentar hasta 5 veces
        response = requests.post(API_ENDPOINT, headers=headers, json=payload)
        
        if response.status_code == 200:
            print("Respuesta de la API de Google:", response.json())  # Agregar esta línea
            data = response.json()
            try:
                contenido = data["candidates"][0]["content"]["parts"][0]["text"]
                if "Inapropiado" in contenido:
                    return None, True  # Contiene malas palabras
                texto_corregido = contenido.split("Texto corregido:")[1].strip()
                return texto_corregido, False
            except (IndexError, KeyError, TypeError) as e:
                print(f"Error procesando la respuesta: {e}")
                raise ValueError("La respuesta de la API no contiene el formato esperado.")
        elif response.status_code == 503:
            print("El modelo está sobrecargado. Intentando nuevamente...")
            time.sleep(5)  # Esperar 5 segundos antes de reintentar
        else:
            print(f"Error en la solicitud a Google. Status Code: {response.status_code}")  # Agregar esta línea
            print("Respuesta: ", response.text)  # Agregar esta línea para ver el mensaje completo
            raise HTTPException(status_code=500, detail="Error en la API de Google")
    
    # Si llegamos a este punto, significa que hemos intentado varias veces y sigue fallando
    raise HTTPException(status_code=503, detail="El modelo está sobrecargado, intente más tarde.")

# Manejador de excepciones para errores de validación
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body},
    )

# Endpoint actualizado
@app.post("/process", response_model=TextResponse)
def process_post(post: TextRequest):
    print(f"Post recibido: {post}")
    try:
        # Procesamos el post y obtenemos el texto corregido
        texto_corregido, contiene_malas_palabras = revisar_texto_google(post.dict())
        
        if contiene_malas_palabras:
            return TextResponse(corrected_text="", contains_bad_words=True)
        
        # Devolver la respuesta con el texto corregido
        return TextResponse(corrected_text=texto_corregido, contains_bad_words=False)
        
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

