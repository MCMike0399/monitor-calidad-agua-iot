"""
Servidor Principal - Monitor de Calidad de Agua en Tiempo Real
==============================================================

Este es el punto de entrada principal para nuestro sistema de monitoreo de agua.
Demuestra conceptos clave de:
- Sistemas distribuidos (Arduino + Servidor + Cliente Web)
- WebSockets para comunicación bidireccional en tiempo real
- HTTP REST API para dispositivos IoT con limitaciones
- Containerización con Docker
- Middleware para logging y manejo de errores

Arquitectura del Sistema:
┌─────────────┐    HTTP POST    ┌──────────────┐    WebSocket    ┌─────────────┐
│   Arduino   │ ───────────────▶│   FastAPI    │ ───────────────▶│  Cliente    │
│  (Sensores) │                 │   Servidor   │                 │    Web      │
└─────────────┘                 └──────────────┘                 └─────────────┘
                                        │
                                        ▼
                                ┌──────────────┐
                                │   Dashboard  │
                                │    Admin     │
                                └──────────────┘

"""

import uuid
import time
import os
import uvicorn
import asyncio
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request, WebSocketDisconnect
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from logging_config import get_logger, setup_logging
from dotenv import load_dotenv
from water_monitor import register_routes

# ============================================================================
# CONFIGURACIÓN INICIAL Y LOGGING
# ============================================================================

# Cargar variables de entorno desde archivo .env
load_dotenv()

# Configurar sistema de logging para toda la aplicación
setup_logging()
logger = get_logger(__name__)

# ============================================================================
# CREACIÓN DE LA APLICACIÓN FASTAPI
# ============================================================================

# Crear instancia principal de FastAPI con metadatos de documentación
app = FastAPI(
    title="🌊 Monitor de Calidad de Agua IoT",
    description="""
    Sistema de monitoreo en tiempo real para calidad de agua usando:
    
    🔧 **Hardware**: Arduino Uno R4 WiFi con sensores ADC
    📡 **Comunicación**: HTTP POST + WebSockets
    🐳 **Despliegue**: Docker + AWS
    📊 **Frontend**: HTML5 + JavaScript + Plotly.js
    
    **Endpoints principales:**
    - `/water-monitor` - Interfaz web de monitoreo
    - `/admin-dashboard` - Panel de administración del servidor
    - `/docs` - Documentación automática de la API
    """,
    version="2.0.0",
    docs_url="/docs",           # Swagger UI automático
    redoc_url="/redoc",         # ReDoc UI alternativo
    openapi_url="/openapi.json", # Esquema OpenAPI
)

# ============================================================================
# CONFIGURACIÓN DE MIDDLEWARE
# ============================================================================

# Middleware CORS - Permite solicitudes desde diferentes dominios
# Importante para desarrollo local y despliegue en producción
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especifica dominios exactos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware personalizado para logging de requests
# Esto nos permite monitorear toda la actividad del servidor
@app.middleware("http")
async def log_requests_middleware(request: Request, call_next):
    """
    Middleware de Logging para Monitoreo de Requests
    ===============================================
    
    Este middleware demuestra cómo interceptar y monitorear TODAS las 
    peticiones HTTP que llegan al servidor. Útil para:
    - Debugging en desarrollo
    - Análisis de performance
    - Auditoría de seguridad
    - Monitoreo en producción
    
    Args:
        request: Objeto Request de FastAPI con toda la info de la petición
        call_next: Función para continuar al siguiente middleware/handler
    
    Returns:
        Response object con headers adicionales de monitoreo
    """
    # Generar ID único para rastrear cada petición
    request_id = str(uuid.uuid4())[:8]  # Solo primeros 8 caracteres
    start_time = time.time()
    
    # Log de la petición entrante
    logger.info(
        f"🔄 [{request_id}] Petición entrante: "
        f"{request.method} {request.url.path} "
        f"desde {request.client.host if request.client else 'Unknown'}"
    )
    
    try:
        # Ejecutar la petición y medir tiempo de respuesta
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Determinar emoji según el status code
        status_emoji = "✅" if response.status_code < 400 else "❌"
        
        # Log de la respuesta
        logger.info(
            f"{status_emoji} [{request_id}] Respuesta: "
            f"Status {response.status_code} "
            f"({process_time:.3f}s)"
        )
        
        # Agregar headers de debugging (útil para desarrollo)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(process_time)
        
        return response
        
    except Exception as e:
        # Log de errores no manejados
        logger.error(f"💥 [{request_id}] Error no manejado: {str(e)}")
        raise  # Re-lanzar la excepción para que FastAPI la maneje

# ============================================================================
# MANEJADORES DE ERRORES GLOBALES
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Manejador Global de Excepciones HTTP
    ===================================
    
    Centraliza el manejo de errores HTTP para:
    - Consistencia en respuestas de error
    - Logging automático de errores
    - Formato estándar para el frontend
    
    Args:
        request: Request que causó el error
        exc: HTTPException con detalles del error
    
    Returns:
        JSONResponse con formato estándar de error
    """
    logger.warning(
        f"🚨 HTTP Error {exc.status_code}: {exc.detail} "
        f"en {request.method} {request.url.path}"
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "status_code": exc.status_code,
            "message": exc.detail,
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url.path)
        }
    )

@app.exception_handler(WebSocketDisconnect)
async def websocket_disconnect_handler(request: Request, exc: WebSocketDisconnect):
    """
    Manejador de Desconexiones WebSocket
    ===================================
    
    Maneja desconexiones inesperadas de WebSockets.
    Útil para cleanup y logging de conexiones perdidas.
    """
    logger.info(f"🔌 WebSocket desconectado: {exc.code}")

# ============================================================================
# RUTAS BÁSICAS DEL SERVIDOR
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """
    Página de Inicio del Sistema
    ============================
    
    Punto de entrada principal que muestra información del sistema
    y enlaces a las diferentes interfaces disponibles.
    """
    logger.info("📍 Acceso a página principal")
    
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🌊 Monitor de Calidad de Agua IoT</title>
        <style>
            body { 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                margin: 0; padding: 40px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white; min-height: 100vh;
            }
            .container { max-width: 800px; margin: 0 auto; text-align: center; }
            .card { 
                background: rgba(255,255,255,0.1); backdrop-filter: blur(10px);
                border-radius: 15px; padding: 30px; margin: 20px 0;
                box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            }
            .btn { 
                display: inline-block; background: rgba(255,255,255,0.2);
                padding: 15px 25px; margin: 10px; border-radius: 50px;
                text-decoration: none; color: white; transition: all 0.3s;
                border: 2px solid rgba(255,255,255,0.3);
            }
            .btn:hover { 
                background: rgba(255,255,255,0.3); 
                transform: translateY(-2px);
            }
            .status { font-family: 'Courier New', monospace; font-size: 14px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🌊 Monitor de Calidad de Agua IoT</h1>
            <div class="card">
                <h2>Sistema de Monitoreo en Tiempo Real</h2>
                <p>Monitoreo de parámetros de calidad de agua usando Arduino y WebSockets</p>
                <div class="status">
                    <p>🟢 Servidor: Activo</p>
                    <p>⏰ Timestamp: <span id="timestamp"></span></p>
                </div>
            </div>
            
            <div class="card">
                <h3>Interfaces Disponibles</h3>
                <a href="/water-monitor" class="btn">📊 Monitor de Agua</a>
                <a href="/admin-dashboard" class="btn">⚙️ Dashboard Admin</a>
                <a href="/docs" class="btn">📚 API Docs</a>
            </div>
            
            <div class="card">
                <h3>Arquitectura del Sistema</h3>
                <p style="font-family: monospace; font-size: 12px;">
                Arduino → HTTP POST → FastAPI → WebSocket → Cliente Web
                </p>
            </div>
        </div>
        
        <script>
            // Actualizar timestamp cada segundo
            function updateTimestamp() {
                document.getElementById('timestamp').textContent = new Date().toLocaleString();
            }
            updateTimestamp();
            setInterval(updateTimestamp, 1000);
        </script>
    </body>
    </html>
    """)

@app.get("/health")
async def health_check():
    """
    Health Check Endpoint
    ====================
    
    Endpoint estándar para verificar el estado del servidor.
    Usado por:
    - Docker HEALTHCHECK
    - Load balancers
    - Monitoreo automático
    - CI/CD pipelines
    
    Returns:
        dict: Estado actual del servidor con métricas básicas
    """
    current_time = datetime.now()
    logger.debug("🏥 Health check ejecutado")
    
    return {
        "status": "healthy",
        "timestamp": current_time.isoformat(),
        "uptime": "Calculando...",  # En producción, calcular uptime real
        "version": "2.0.0",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "websockets": "active",
        "database": "not_connected"  # Expandir cuando agregues BD
    }

# ============================================================================
# REGISTRO DE RUTAS DE MONITOREO
# ============================================================================

# Registrar todas las rutas relacionadas con el monitoreo de agua
# Esto incluye WebSockets, API REST, y páginas web
register_routes(app)

# Integrar el monitor de sistema distribuido (funcionalidad educativa avanzada)
# Esto proporciona visualización en tiempo real de:
# - Métricas de sistema (CPU, memoria, red)
# - Eventos de comunicación entre componentes
# - Logs estructurados para debugging
# - Topología de red del sistema distribuido
try:
    from system_monitor import integrate_system_monitor
    integrate_system_monitor(app)
    logger.info("🔍 Monitor de sistema distribuido integrado exitosamente")
except ImportError:
    logger.warning("⚠️ Monitor de sistema no disponible (instalar psutil para habilitarlo)")
except Exception as e:
    logger.error(f"💥 Error integrando monitor de sistema: {str(e)}")

# ============================================================================
# EVENTOS DEL CICLO DE VIDA DE LA APLICACIÓN
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """
    Evento de Inicio de la Aplicación
    =================================
    
    Se ejecuta cuando el servidor inicia. Útil para:
    - Inicializar conexiones a base de datos
    - Configurar tareas en background
    - Validar configuraciones
    - Establecer estado inicial
    """
    logger.info("🚀 Iniciando servidor de Monitor de Agua IoT...")
    logger.info("=" * 60)
    logger.info("📋 Sistema de Monitoreo de Calidad de Agua")
    logger.info("🏗️  Arquitectura: Arduino + FastAPI + WebSockets")
    logger.info("🐳 Contenedor: Docker")
    logger.info("☁️  Despliegue: AWS")
    logger.info("=" * 60)
    
    # Aquí podrías inicializar conexiones a BD, caches, etc.
    # await database.connect()
    # await redis.connect()

@app.on_event("shutdown")
async def shutdown_event():
    """
    Evento de Cierre de la Aplicación
    =================================
    
    Se ejecuta cuando el servidor se cierra. Útil para:
    - Cerrar conexiones a base de datos
    - Guardar estado persistente
    - Cancelar tareas en background
    - Cleanup de recursos
    """
    logger.info("🛑 Cerrando servidor de Monitor de Agua IoT...")
    logger.info("✅ Cleanup completado")
    
    # Aquí podrías cerrar conexiones y hacer cleanup
    # await database.disconnect()
    # await redis.disconnect()

# ============================================================================
# FUNCIÓN PRINCIPAL - PUNTO DE ENTRADA
# ============================================================================

if __name__ == "__main__":
    """
    Punto de Entrada Principal
    =========================
    
    Se ejecuta solo cuando el archivo se ejecuta directamente
    (no cuando se importa como módulo).
    
    En producción, se usa típicamente:
    uvicorn main:app --host 0.0.0.0 --port 8000
    """
    
    # Obtener configuración del entorno
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    debug_mode = os.getenv("DEBUG", "True").lower() == "true"
    
    logger.info(f"🌐 Iniciando servidor en {host}:{port}")
    logger.info(f"🔧 Modo debug: {debug_mode}")
    logger.info(f"📂 Directorio de trabajo: {os.getcwd()}")
    
    # Iniciar servidor Uvicorn
    # reload=True permite recarga automática en desarrollo
    uvicorn.run(
        "main:app", 
        host=host, 
        port=port, 
        reload=debug_mode,
        log_level="info" if not debug_mode else "debug"
    )