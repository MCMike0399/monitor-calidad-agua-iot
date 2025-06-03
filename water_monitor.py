"""
Sistema de Monitoreo de Agua - WebSockets & HTTP API
===================================================

Este módulo implementa el corazón del sistema de monitoreo de agua,
demostrando conceptos avanzados de sistemas distribuidos:

WebSockets: Comunicación bidireccional en tiempo real
HTTP API: Interfaz REST para dispositivos IoT
Pub/Sub: Patrón de publicación/suscripción
State Management: Manejo de estado distribuido
Real-time Data: Streaming de datos en tiempo real

Conceptos Educativos Demostrados:
================================
1. **WebSockets vs HTTP**: Diferencias y casos de uso
2. **Sistemas Distribuidos**: Comunicación entre componentes
3. **Patrón Pub/Sub**: Desacoplamiento de productores y consumidores
4. **Manejo de Estado**: Estado compartido entre múltiples clientes
5. **Error Handling**: Manejo robusto de errores en tiempo real
6. **Concurrencia**: Manejo de múltiples conexiones simultáneas

Arquitectura de Comunicación:
============================
              ┌─────────────────┐
              │    Arduino      │
              │   (Sensores)    │
              └─────────┬───────┘
                        │ HTTP POST
                        │ /water-monitor/publish
                        ▼
              ┌─────────────────┐      WebSocket      ┌─────────────────┐
              │   FastAPI       │◀────────────────────▶│   Cliente Web   │
              │   Servidor      │     /water-monitor  │   (Dashboard)   │
              └─────────┬───────┘                     └─────────────────┘
                        │
                        │ WebSocket
                        │ /admin-dashboard/ws
                        ▼
              ┌─────────────────┐
              │  Admin Panel    │
              │ (Monitoreo)     │
              └─────────────────┘

"""

import json
import asyncio
import random
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, Response
from logging_config import get_logger

# ============================================================================
# CONFIGURACIÓN Y CONSTANTES
# ============================================================================

logger = get_logger(__name__)

# Configuración de datos mock para pruebas sin Arduino
MOCK_DATA_CONFIG = {
    "interval_seconds": 3.0,  # Intervalo de generación de datos simulados
    "turbidity_range": (5, 800),     # Rango de turbidez (NTU)
    "ph_range": (3, 10),             # Rango de pH
    "conductivity_range": (100, 1200) # Rango de conductividad (μS/cm)
}

# ============================================================================
# MODELOS DE DATOS Y ESTRUCTURAS
# ============================================================================

class DataSource(Enum):
    """
    Enum para identificar el origen de los datos
    """
    MOCK = "mock"      # Datos simulados para pruebas
    ARDUINO = "arduino" # Datos reales del Arduino

@dataclass
class SensorReading:
    """
    Clase de datos para una lectura de sensores
    
    Esta estructura define el formato estándar para todas las lecturas
    de sensores, asegurando consistencia en todo el sistema.
    
    Attributes:
        turbidity (float): Turbidez en NTU (Nephelometric Turbidity Units)
        ph (float): Nivel de pH (0-14)
        conductivity (float): Conductividad en μS/cm
        timestamp (datetime): Momento exacto de la lectura
        source (DataSource): Origen de los datos (mock o arduino)
    """
    turbidity: float
    ph: float
    conductivity: float
    timestamp: datetime
    source: DataSource
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte la lectura a diccionario para JSON serialization"""
        return {
            "T": round(self.turbidity, 2),    # Formato compatibile con Arduino
            "PH": round(self.ph, 2),
            "C": round(self.conductivity, 2),
            "timestamp": self.timestamp.isoformat(),
            "source": self.source.value
        }
    
    @classmethod
    def from_arduino_data(cls, data: Dict[str, Any]) -> 'SensorReading':
        """
        Crea una SensorReading desde datos del Arduino
        
        Args:
            data: Diccionario con claves 'T', 'PH', 'C'
        
        Returns:
            SensorReading: Instancia creada desde los datos
        """
        return cls(
            turbidity=float(data["T"]),
            ph=float(data["PH"]),
            conductivity=float(data["C"]),
            timestamp=datetime.now(),
            source=DataSource.ARDUINO
        )

# ============================================================================
# GESTOR DE ESTADO GLOBAL DEL SISTEMA
# ============================================================================

class WaterMonitorState:
    """
    Gestor de Estado Global del Sistema de Monitoreo
    ===============================================
    
    Esta clase centraliza todo el estado del sistema, implementando
    el patrón Singleton para asegurar una sola fuente de verdad.
    
    Responsabilidades:
    - Almacenar la última lectura de sensores
    - Mantener lista de clientes WebSocket conectados
    - Controlar el modo de operación (mock vs real)
    - Gestionar estadísticas del sistema
    """
    
    def __init__(self):
        # Última lectura de sensores (inicializada con valores por defecto)
        self.latest_reading: SensorReading = SensorReading(
            turbidity=25.0,
            ph=7.0,
            conductivity=300.0,
            timestamp=datetime.now(),
            source=DataSource.MOCK
        )
        
        # Lista de conexiones WebSocket activas para clientes de monitoreo
        self.monitor_clients: List[WebSocket] = []
        
        # Lista de conexiones WebSocket activas para panel de administración
        self.admin_clients: List[WebSocket] = []
        
        # Configuración del sistema
        self.use_mock_data: bool = True
        self.mock_task: Optional[asyncio.Task] = None
        
        # Estadísticas del sistema
        self.stats = {
            "total_readings": 0,
            "arduino_readings": 0,
            "mock_readings": 0,
            "connected_clients": 0,
            "uptime_start": datetime.now(),
            "last_arduino_connection": None
        }
        
        logger.info("🏗️ Estado del sistema inicializado")
    
    async def update_reading(self, reading: SensorReading):
        """
        Actualiza la última lectura y notifica a todos los clientes
        
        Args:
            reading: Nueva lectura de sensores
        """
        self.latest_reading = reading
        self.stats["total_readings"] += 1
        
        if reading.source == DataSource.ARDUINO:
            self.stats["arduino_readings"] += 1
            self.stats["last_arduino_connection"] = datetime.now()
            logger.info(f"📡 Datos del Arduino: T={reading.turbidity}, pH={reading.ph}, C={reading.conductivity}")
        else:
            self.stats["mock_readings"] += 1
            logger.debug(f"🎭 Datos simulados: T={reading.turbidity}, pH={reading.ph}, C={reading.conductivity}")
        
        # Notificar a todos los clientes conectados
        await self._broadcast_to_clients()
        await self._broadcast_to_admin()
    
    async def _broadcast_to_clients(self):
        """Envía la última lectura a todos los clientes de monitoreo"""
        if not self.monitor_clients:
            return
            
        data = self.latest_reading.to_dict()
        disconnected_clients = []
        
        for client in self.monitor_clients:
            try:
                await client.send_json(data)
            except Exception as e:
                logger.warning(f"🔌 Cliente desconectado: {str(e)}")
                disconnected_clients.append(client)
        
        # Remover clientes desconectados
        for client in disconnected_clients:
            self.monitor_clients.remove(client)
            
        # Actualizar estadísticas
        self.stats["connected_clients"] = len(self.monitor_clients)
    
    async def _broadcast_to_admin(self):
        """Envía estadísticas del sistema al panel de administración"""
        if not self.admin_clients:
            return
            
        admin_data = {
            "type": "system_update",
            "latest_reading": self.latest_reading.to_dict(),
            "stats": {
                **self.stats,
                "uptime_start": self.stats["uptime_start"].isoformat(),
                "last_arduino_connection": (
                    self.stats["last_arduino_connection"].isoformat() 
                    if self.stats["last_arduino_connection"] else None
                )
            },
            "config": {
                "use_mock_data": self.use_mock_data,
                "connected_monitor_clients": len(self.monitor_clients),
                "connected_admin_clients": len(self.admin_clients)
            }
        }
        
        disconnected_clients = []
        for client in self.admin_clients:
            try:
                await client.send_json(admin_data)
            except Exception as e:
                logger.warning(f"🔌 Admin cliente desconectado: {str(e)}")
                disconnected_clients.append(client)
        
        # Remover clientes desconectados
        for client in disconnected_clients:
            self.admin_clients.remove(client)
    
    def add_monitor_client(self, websocket: WebSocket):
        """Registra un nuevo cliente de monitoreo"""
        self.monitor_clients.append(websocket)
        self.stats["connected_clients"] = len(self.monitor_clients)
        logger.info(f"👥 Cliente de monitoreo conectado. Total: {len(self.monitor_clients)}")
    
    def remove_monitor_client(self, websocket: WebSocket):
        """Remueve un cliente de monitoreo"""
        if websocket in self.monitor_clients:
            self.monitor_clients.remove(websocket)
            self.stats["connected_clients"] = len(self.monitor_clients)
            logger.info(f"👥 Cliente de monitoreo desconectado. Total: {len(self.monitor_clients)}")
    
    def add_admin_client(self, websocket: WebSocket):
        """Registra un nuevo cliente administrador"""
        self.admin_clients.append(websocket)
        logger.info(f"🛠️ Cliente admin conectado. Total: {len(self.admin_clients)}")
    
    def remove_admin_client(self, websocket: WebSocket):
        """Remueve un cliente administrador"""
        if websocket in self.admin_clients:
            self.admin_clients.remove(websocket)
            logger.info(f"🛠️ Cliente admin desconectado. Total: {len(self.admin_clients)}")

# Instancia global del estado del sistema (Singleton)
water_state = WaterMonitorState()

# ============================================================================
# GENERADOR DE DATOS SIMULADOS
# ============================================================================

async def generate_mock_data():
    """
    Generador de Datos Simulados para Pruebas
    ========================================
    
    Esta función ejecuta en background y genera datos simulados
    de sensores cuando no hay Arduino conectado. Útil para:
    - Desarrollo sin hardware
    - Demos y presentaciones
    - Testing de la interfaz
    - Validación del sistema
    
    Los datos generados siguen patrones realistas basados en
    parámetros típicos de calidad de agua.
    """
    logger.info("🎭 Iniciando generación de datos simulados")
    
    while True:
        try:
            # Solo generar si el modo mock está activo
            if water_state.use_mock_data:
                # Generar valores con variaciones realistas
                mock_reading = SensorReading(
                    turbidity=round(random.uniform(*MOCK_DATA_CONFIG["turbidity_range"]), 2),
                    ph=round(random.uniform(*MOCK_DATA_CONFIG["ph_range"]), 2),
                    conductivity=round(random.uniform(*MOCK_DATA_CONFIG["conductivity_range"]), 2),
                    timestamp=datetime.now(),
                    source=DataSource.MOCK
                )
                
                # Actualizar estado global
                await water_state.update_reading(mock_reading)
            
            # Esperar antes de la siguiente generación
            await asyncio.sleep(MOCK_DATA_CONFIG["interval_seconds"])
            
        except asyncio.CancelledError:
            logger.info("🛑 Generación de datos mock cancelada")
            break
        except Exception as e:
            logger.error(f"💥 Error en generación de datos mock: {str(e)}")
            await asyncio.sleep(5)  # Esperar antes de reintentar

# ============================================================================
# ENDPOINTS HTTP PARA ARDUINO
# ============================================================================

async def arduino_http_endpoint(request: Request) -> Response:
    """
    Endpoint HTTP POST para Recepción de Datos del Arduino
    =====================================================
    
    Este endpoint está optimizado para dispositivos IoT con limitaciones:
    - Respuestas rápidas para conservar batería
    - Manejo eficiente de memoria
    - Tolerancia a fallos de red
    - Logging mínimo para performance
    
    ¿Por qué HTTP y no WebSocket para Arduino?
    - Menor consumo de memoria RAM
    - Implementación más simple en microcontroladores
    - Mejor manejo de reconexión automática
    - Compatible con bibliotecas HTTP estándar
    
    Args:
        request: Request HTTP con datos JSON del Arduino
        
    Returns:
        Response: Respuesta HTTP minimalista (200 OK o error)
    """
    try:
        # Leer datos del cuerpo de la petición de manera eficiente
        content_length = int(request.headers.get("content-length", 0))
        
        if content_length == 0:
            logger.warning("🚨 Petición vacía del Arduino")
            return Response(status_code=400)
        
        # Parsear JSON de manera segura
        body = await request.body()
        arduino_data = json.loads(body.decode('utf-8'))
        
        # Validar estructura de datos
        required_fields = ["T", "PH", "C"]
        if not all(field in arduino_data for field in required_fields):
            logger.warning(f"🚨 Datos incompletos del Arduino: {arduino_data}")
            return Response(status_code=400)
        
        # Crear lectura desde datos del Arduino
        reading = SensorReading.from_arduino_data(arduino_data)
        
        # Actualizar estado solo si no estamos en modo mock
        if not water_state.use_mock_data:
            await water_state.update_reading(reading)
            return Response(status_code=200)  # OK - Datos procesados
        else:
            logger.debug("🎭 Datos del Arduino ignorados (modo mock activo)")
            return Response(status_code=202)  # Accepted - Datos recibidos pero no procesados
            
    except json.JSONDecodeError as e:
        logger.error(f"💥 JSON inválido del Arduino: {str(e)}")
        return Response(status_code=400)
    except Exception as e:
        logger.error(f"💥 Error procesando datos del Arduino: {str(e)}")
        return Response(status_code=500)

# ============================================================================
# WEBSOCKET ENDPOINTS
# ============================================================================

async def monitor_websocket_endpoint(websocket: WebSocket):
    """
    WebSocket para Clientes de Monitoreo (Dashboard Principal)
    ========================================================
    
    Este endpoint maneja la comunicación en tiempo real con
    el dashboard web de monitoreo. Características:
    
    - Envío automático de datos cada vez que se actualiza una lectura
    - Manejo robusto de desconexiones
    - Envío de datos históricos al conectarse
    - Heartbeat para detectar conexiones perdidas
    
    Flujo de Comunicación:
    1. Cliente se conecta
    2. Servidor envía datos actuales inmediatamente
    3. Servidor envía actualizaciones cuando hay nuevos datos
    4. Cliente puede enviar comandos (futuro: filtros, configuración)
    
    Args:
        websocket: Conexión WebSocket con el cliente
    """
    await websocket.accept()
    water_state.add_monitor_client(websocket)
    
    try:
        # Enviar datos actuales inmediatamente al conectarse
        initial_data = water_state.latest_reading.to_dict()
        await websocket.send_json(initial_data)
        logger.info("📊 Cliente de monitoreo conectado y datos iniciales enviados")
        
        # Mantener conexión activa y procesar mensajes del cliente
        while True:
            try:
                # Esperar mensajes del cliente (con timeout para heartbeat)
                message = await asyncio.wait_for(
                    websocket.receive_text(), 
                    timeout=30.0  # 30 segundos timeout
                )
                
                # Procesar mensaje del cliente
                try:
                    client_data = json.loads(message)
                    logger.debug(f"📨 Mensaje del cliente de monitoreo: {client_data}")
                    
                    # Responder con eco para confirmar recepción
                    await websocket.send_json({
                        "type": "echo",
                        "original_message": client_data,
                        "timestamp": datetime.now().isoformat(),
                        "status": "received"
                    })
                    
                except json.JSONDecodeError:
                    logger.warning(f"🚨 JSON inválido del cliente: {message}")
                    
            except asyncio.TimeoutError:
                # Verificar que la conexión sigue activa enviando un mensaje de heartbeat
                try:
                    await websocket.send_json({
                        "type": "heartbeat",
                        "timestamp": datetime.now().isoformat()
                    })
                    logger.debug("🏓 Heartbeat enviado al cliente de monitoreo")
                except:
                    logger.info("💔 Conexión de monitoreo perdida (heartbeat falló)")
                    break
                    
    except WebSocketDisconnect:
        logger.info("🔌 Cliente de monitoreo desconectado normalmente")
    except Exception as e:
        logger.error(f"💥 Error en WebSocket de monitoreo: {str(e)}")
    finally:
        water_state.remove_monitor_client(websocket)

async def admin_websocket_endpoint(websocket: WebSocket):
    """
    WebSocket para Panel de Administración del Sistema
    =================================================
    
    Este endpoint proporciona acceso de administración al sistema:
    - Control del modo mock/real
    - Estadísticas detalladas del sistema
    - Información sobre conexiones activas
    - Comandos de configuración
    
    Comandos soportados:
    - {"command": "set_mock_mode", "value": true/false}
    - {"command": "get_stats"}
    - {"command": "get_status"}
    
    Args:
        websocket: Conexión WebSocket con el panel admin
    """
    await websocket.accept()
    water_state.add_admin_client(websocket)
    
    try:
        # Enviar estado inicial del sistema
        initial_status = {
            "type": "system_status",
            "config": {
                "use_mock_data": water_state.use_mock_data,
                "connected_monitor_clients": len(water_state.monitor_clients)
            },
            "latest_reading": water_state.latest_reading.to_dict(),
            "stats": {
                **water_state.stats,
                "uptime_start": water_state.stats["uptime_start"].isoformat(),
                "last_arduino_connection": (
                    water_state.stats["last_arduino_connection"].isoformat() 
                    if water_state.stats["last_arduino_connection"] else None
                )
            }
        }
        await websocket.send_json(initial_status)
        logger.info("🛠️ Cliente admin conectado y estado inicial enviado")
        
        # Procesar comandos del panel admin
        while True:
            message = await websocket.receive_text()
            
            try:
                command_data = json.loads(message)
                command = command_data.get("command")
                
                logger.info(f"🎛️ Comando admin recibido: {command}")
                
                if command == "set_mock_mode":
                    # Cambiar modo mock/real
                    new_mode = command_data.get("value", True)
                    water_state.use_mock_data = new_mode
                    
                    response = {
                        "type": "command_response",
                        "command": "set_mock_mode",
                        "success": True,
                        "message": f"Modo cambiado a {'mock' if new_mode else 'real'}",
                        "new_value": new_mode
                    }
                    await websocket.send_json(response)
                    logger.info(f"🔄 Modo de datos cambiado a: {'mock' if new_mode else 'real'}")
                
                elif command == "get_stats":
                    # Enviar estadísticas completas
                    stats_response = {
                        "type": "stats_response",
                        "stats": {
                            **water_state.stats,
                            "uptime_start": water_state.stats["uptime_start"].isoformat(),
                            "last_arduino_connection": (
                                water_state.stats["last_arduino_connection"].isoformat() 
                                if water_state.stats["last_arduino_connection"] else None
                            )
                        }
                    }
                    await websocket.send_json(stats_response)
                
                else:
                    # Comando no reconocido
                    error_response = {
                        "type": "error",
                        "message": f"Comando no reconocido: {command}",
                        "available_commands": ["set_mock_mode", "get_stats"]
                    }
                    await websocket.send_json(error_response)
                    
            except json.JSONDecodeError:
                logger.warning(f"🚨 JSON inválido del admin: {message}")
                error_response = {
                    "type": "error",
                    "message": "Formato JSON inválido"
                }
                await websocket.send_json(error_response)
                
    except WebSocketDisconnect:
        logger.info("🔌 Cliente admin desconectado")
    except Exception as e:
        logger.error(f"💥 Error en WebSocket admin: {str(e)}")
    finally:
        water_state.remove_admin_client(websocket)

# ============================================================================
# INTERFAZ WEB DE ADMINISTRACIÓN
# ============================================================================

async def get_admin_dashboard():
    """
    Página Web del Dashboard de Administración
    ========================================
    
    Interfaz web interactiva para que los profesores puedan:
    - Ver el estado del sistema en tiempo real
    - Cambiar entre modo mock y datos reales
    - Monitorear conexiones activas
    - Ver estadísticas del sistema
    - Entender el funcionamiento interno
    """
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🛠️ Dashboard de Administración - Monitor de Agua IoT</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
                color: white; min-height: 100vh; padding: 20px;
            }
            .dashboard { max-width: 1400px; margin: 0 auto; }
            .header { text-align: center; margin-bottom: 30px; }
            .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
            .card { 
                background: rgba(255,255,255,0.1); backdrop-filter: blur(10px);
                border-radius: 15px; padding: 25px; border: 1px solid rgba(255,255,255,0.2);
            }
            .status-indicator { 
                display: inline-block; width: 12px; height: 12px; border-radius: 50%; 
                margin-right: 8px; animation: pulse 2s infinite;
            }
            .online { background: #4ade80; }
            .offline { background: #f87171; }
            @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
            .btn { 
                background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.3);
                color: white; padding: 12px 20px; border-radius: 8px; cursor: pointer;
                transition: all 0.3s; margin: 5px;
            }
            .btn:hover { background: rgba(255,255,255,0.3); }
            .btn.active { background: #4ade80; }
            .btn.inactive { background: #f87171; }
            .metric { display: flex; justify-content: space-between; margin: 10px 0; }
            .metric-value { font-weight: bold; font-family: 'Courier New', monospace; }
            .log { 
                background: rgba(0,0,0,0.3); border-radius: 8px; padding: 15px;
                height: 200px; overflow-y: auto; font-family: 'Courier New', monospace;
                font-size: 12px;
            }
            .reading-display {
                display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px;
                margin: 15px 0;
            }
            .reading-item {
                text-align: center; background: rgba(255,255,255,0.1);
                padding: 15px; border-radius: 8px;
            }
            .reading-value { font-size: 24px; font-weight: bold; margin: 5px 0; }
            .reading-label { font-size: 12px; opacity: 0.8; }
        </style>
    </head>
    <body>
        <div class="dashboard">
            <div class="header">
                <h1>🛠️ Dashboard de Administración</h1>
                <p>Monitor IoT de Calidad de Agua - Panel de Control del Sistema</p>
                <div>
                    <span id="connectionStatus" class="status-indicator offline"></span>
                    <span id="connectionText">Conectando...</span>
                </div>
            </div>
            
            <div class="grid">
                <!-- Control del Sistema -->
                <div class="card">
                    <h3>🎛️ Control del Sistema</h3>
                    <p>Cambiar entre datos simulados y datos reales del Arduino</p>
                    <div style="margin: 15px 0;">
                        <button id="mockBtn" class="btn" onclick="setMockMode(true)">
                            🎭 Datos Simulados
                        </button>
                        <button id="realBtn" class="btn" onclick="setMockMode(false)">
                            📡 Datos del Arduino
                        </button>
                    </div>
                    <div id="modeStatus" class="metric">
                        <span>Modo actual:</span>
                        <span class="metric-value">Detectando...</span>
                    </div>
                </div>
                
                <!-- Estadísticas del Sistema -->
                <div class="card">
                    <h3>📊 Estadísticas del Sistema</h3>
                    <div class="metric">
                        <span>Lecturas totales:</span>
                        <span id="totalReadings" class="metric-value">0</span>
                    </div>
                    <div class="metric">
                        <span>Lecturas Arduino:</span>
                        <span id="arduinoReadings" class="metric-value">0</span>
                    </div>
                    <div class="metric">
                        <span>Lecturas simuladas:</span>
                        <span id="mockReadings" class="metric-value">0</span>
                    </div>
                    <div class="metric">
                        <span>Clientes conectados:</span>
                        <span id="connectedClients" class="metric-value">0</span>
                    </div>
                    <div class="metric">
                        <span>Última conexión Arduino:</span>
                        <span id="lastArduino" class="metric-value">Nunca</span>
                    </div>
                </div>
                
                <!-- Lecturas Actuales -->
                <div class="card">
                    <h3>🌊 Lecturas Actuales</h3>
                    <div class="reading-display">
                        <div class="reading-item">
                            <div class="reading-label">Turbidez</div>
                            <div id="currentTurbidity" class="reading-value">--</div>
                            <div class="reading-label">NTU</div>
                        </div>
                        <div class="reading-item">
                            <div class="reading-label">pH</div>
                            <div id="currentPH" class="reading-value">--</div>
                            <div class="reading-label">Unidades</div>
                        </div>
                        <div class="reading-item">
                            <div class="reading-label">Conductividad</div>
                            <div id="currentConductivity" class="reading-value">--</div>
                            <div class="reading-label">μS/cm</div>
                        </div>
                    </div>
                    <div class="metric">
                        <span>Origen de datos:</span>
                        <span id="dataSource" class="metric-value">--</span>
                    </div>
                    <div class="metric">
                        <span>Última actualización:</span>
                        <span id="lastUpdate" class="metric-value">--</span>
                    </div>
                </div>
                
                <!-- Log del Sistema -->
                <div class="card" style="grid-column: 1 / -1;">
                    <h3>📝 Log del Sistema en Tiempo Real</h3>
                    <div id="systemLog" class="log">
                        <div style="color: #4ade80;">Sistema iniciando...</div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            let socket = null;
            let reconnectInterval = null;
            
            function addLogEntry(message, type = 'info') {
                const log = document.getElementById('systemLog');
                const timestamp = new Date().toLocaleTimeString();
                const colors = {
                    'info': '#4ade80',
                    'warning': '#fbbf24',
                    'error': '#f87171',
                    'data': '#60a5fa'
                };
                
                const entry = document.createElement('div');
                entry.style.color = colors[type] || colors.info;
                entry.innerHTML = `[${timestamp}] ${message}`;
                
                log.appendChild(entry);
                log.scrollTop = log.scrollHeight;
                
                // Limitar a 100 entradas
                while (log.children.length > 100) {
                    log.removeChild(log.firstChild);
                }
            }
            
            function connectWebSocket() {
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const wsUrl = `${protocol}//${window.location.host}/admin-dashboard/ws`;
                
                socket = new WebSocket(wsUrl);
                
                socket.onopen = function() {
                    document.getElementById('connectionStatus').className = 'status-indicator online';
                    document.getElementById('connectionText').textContent = 'Conectado al sistema';
                    addLogEntry('🟢 Conectado al sistema de administración', 'info');
                    
                    if (reconnectInterval) {
                        clearInterval(reconnectInterval);
                        reconnectInterval = null;
                    }
                };
                
                socket.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    
                    if (data.type === 'system_update' || data.type === 'system_status') {
                        updateSystemDisplay(data);
                        addLogEntry(`📊 Actualización del sistema recibida`, 'data');
                    } else if (data.type === 'command_response') {
                        addLogEntry(`✅ Comando ejecutado: ${data.message}`, 'info');
                        if (data.command === 'set_mock_mode') {
                            updateModeButtons(data.new_value);
                        }
                    } else if (data.type === 'error') {
                        addLogEntry(`❌ Error: ${data.message}`, 'error');
                    }
                };
                
                socket.onclose = function() {
                    document.getElementById('connectionStatus').className = 'status-indicator offline';
                    document.getElementById('connectionText').textContent = 'Desconectado - Reconectando...';
                    addLogEntry('🔴 Conexión perdida, intentando reconectar...', 'warning');
                    
                    if (!reconnectInterval) {
                        reconnectInterval = setInterval(connectWebSocket, 3000);
                    }
                };
                
                socket.onerror = function(error) {
                    addLogEntry('💥 Error de conexión WebSocket', 'error');
                };
            }
            
            function updateSystemDisplay(data) {
                // Actualizar estadísticas
                if (data.stats) {
                    document.getElementById('totalReadings').textContent = data.stats.total_readings;
                    document.getElementById('arduinoReadings').textContent = data.stats.arduino_readings;
                    document.getElementById('mockReadings').textContent = data.stats.mock_readings;
                    document.getElementById('connectedClients').textContent = data.stats.connected_clients;
                    
                    if (data.stats.last_arduino_connection) {
                        const lastDate = new Date(data.stats.last_arduino_connection);
                        document.getElementById('lastArduino').textContent = lastDate.toLocaleString();
                    }
                }
                
                // Actualizar lecturas actuales
                if (data.latest_reading) {
                    document.getElementById('currentTurbidity').textContent = data.latest_reading.T;
                    document.getElementById('currentPH').textContent = data.latest_reading.PH;
                    document.getElementById('currentConductivity').textContent = data.latest_reading.C;
                    document.getElementById('dataSource').textContent = data.latest_reading.source;
                    
                    if (data.latest_reading.timestamp) {
                        const updateTime = new Date(data.latest_reading.timestamp);
                        document.getElementById('lastUpdate').textContent = updateTime.toLocaleTimeString();
                    }
                }
                
                // Actualizar modo
                if (data.config) {
                    updateModeButtons(data.config.use_mock_data);
                }
            }
            
            function updateModeButtons(useMockData) {
                const mockBtn = document.getElementById('mockBtn');
                const realBtn = document.getElementById('realBtn');
                const modeStatus = document.getElementById('modeStatus').querySelector('.metric-value');
                
                if (useMockData) {
                    mockBtn.className = 'btn active';
                    realBtn.className = 'btn inactive';
                    modeStatus.textContent = '🎭 Datos Simulados';
                } else {
                    mockBtn.className = 'btn inactive';
                    realBtn.className = 'btn active';
                    modeStatus.textContent = '📡 Datos del Arduino';
                }
            }
            
            function setMockMode(useMock) {
                if (socket && socket.readyState === WebSocket.OPEN) {
                    const command = {
                        command: 'set_mock_mode',
                        value: useMock
                    };
                    socket.send(JSON.stringify(command));
                    addLogEntry(`🎛️ Cambiando modo a: ${useMock ? 'simulado' : 'real'}`, 'info');
                } else {
                    addLogEntry('❌ No conectado al sistema', 'error');
                }
            }
            
            // Conectar al cargar la página
            window.onload = function() {
                connectWebSocket();
                addLogEntry('🚀 Dashboard de administración iniciado', 'info');
            };
        </script>
    </body>
    </html>
    """)

# ============================================================================
# FUNCIÓN PRINCIPAL DE REGISTRO DE RUTAS
# ============================================================================

def register_routes(app: FastAPI):
    """
    Registrar Todas las Rutas del Sistema de Monitoreo
    =================================================
    
    Esta función centraliza el registro de todas las rutas y endpoints
    del sistema, organizándolos de manera lógica y documentada.
    
    Rutas registradas:
    - Archivos estáticos (CSS, JS, imágenes)
    - Página principal de monitoreo
    - Dashboard de administración
    - API HTTP para Arduino
    - WebSockets para clientes y admin
    
    Args:
        app: Instancia de FastAPI para registrar las rutas
    """
    logger.info("🔗 Registrando rutas del sistema de monitoreo...")
    
    # ========================================================================
    # ARCHIVOS ESTÁTICOS
    # ========================================================================
    
    # Configurar directorio de archivos estáticos
    static_dir = os.path.join(os.getcwd(), "static")
    if not os.path.exists(static_dir):
        os.makedirs(static_dir, exist_ok=True)
        logger.info(f"📁 Directorio estático creado: {static_dir}")
    
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    logger.info(f"📁 Archivos estáticos montados desde: {static_dir}")
    
    # ========================================================================
    # PÁGINAS WEB
    # ========================================================================
    
    @app.get("/water-monitor")
    async def get_water_monitor():
        """Página principal de monitoreo de agua"""
        html_path = os.path.join(static_dir, "ws_client.html")
        if os.path.exists(html_path):
            logger.info("📊 Sirviendo página de monitoreo")
            return FileResponse(html_path)
        else:
            logger.warning("⚠️ Archivo de monitoreo no encontrado")
            return HTMLResponse(
                "<html><body><h1>❌ Página de monitoreo no encontrada</h1>"
                "<p>El archivo ws_client.html no existe en el directorio static/</p></body></html>",
                status_code=404
            )
    
    @app.get("/admin-dashboard")
    async def get_admin_dashboard_route():
        """Dashboard de administración del sistema"""
        logger.info("🛠️ Sirviendo dashboard de administración")
        return await get_admin_dashboard()
    
    # ========================================================================
    # API HTTP PARA ARDUINO
    # ========================================================================
    
    @app.post("/water-monitor/publish")
    async def arduino_http_route(request: Request):
        """Endpoint HTTP POST optimizado para Arduino"""
        return await arduino_http_endpoint(request)
    
    # ========================================================================
    # WEBSOCKET ENDPOINTS
    # ========================================================================
    
    @app.websocket("/water-monitor")
    async def monitor_websocket_route(websocket: WebSocket):
        """WebSocket para clientes de monitoreo"""
        await monitor_websocket_endpoint(websocket)
    
    @app.websocket("/admin-dashboard/ws")
    async def admin_websocket_route(websocket: WebSocket):
        """WebSocket para panel de administración"""
        await admin_websocket_endpoint(websocket)
    
    # ========================================================================
    # EVENTOS DEL CICLO DE VIDA
    # ========================================================================
    
    @app.on_event("startup")
    async def startup_water_monitor():
        """Inicializar sistema de monitoreo al arrancar"""
        logger.info("🚀 Iniciando sistema de monitoreo de agua...")
        
        # Iniciar tarea de generación de datos mock
        water_state.mock_task = asyncio.create_task(generate_mock_data())
        logger.info("🎭 Tarea de datos simulados iniciada")
    
    @app.on_event("shutdown")
    async def shutdown_water_monitor():
        """Cleanup al cerrar el sistema"""
        logger.info("🛑 Cerrando sistema de monitoreo...")
        
        # Cancelar tarea de datos mock
        if water_state.mock_task and not water_state.mock_task.done():
            water_state.mock_task.cancel()
            try:
                await water_state.mock_task
            except asyncio.CancelledError:
                logger.info("✅ Tarea de datos simulados cancelada")
        
        logger.info("✅ Sistema de monitoreo cerrado correctamente")
    
    logger.info("✅ Todas las rutas del sistema de monitoreo registradas")