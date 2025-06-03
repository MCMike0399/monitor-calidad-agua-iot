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
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, Response
from logging_config import get_logger
from system_monitor import system_monitor, SystemEvent, EventType, monitor_websocket_events


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
            "T": round(self.turbidity, 2),    # Formato compatible con Arduino
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
        
        # MEJORADO: Registro de conexiones con IDs únicos
        self.connection_registry: Dict[str, Dict] = {}
        
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
    
    def generate_connection_id(self, websocket: WebSocket, client_type: str) -> str:
        """Genera un ID único para cada conexión"""
        client_host = getattr(websocket.client, 'host', 'unknown') if websocket.client else 'unknown'
        client_port = getattr(websocket.client, 'port', 0) if websocket.client else 0
        timestamp = int(time.time() * 1000)
        return f"{client_type}_{client_host}_{client_port}_{timestamp}"
    
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
            logger.info(f"📡 Datos del Arduino: T={reading.turbidity}NTU, pH={reading.ph}, C={reading.conductivity}μS/cm")
            
            # INTEGRACIÓN: Registrar en sistema de monitoreo
            data_json = json.dumps(reading.to_dict())
            await system_monitor.record_arduino_data(len(data_json))
        else:
            self.stats["mock_readings"] += 1
            logger.debug(f"🎭 Datos simulados: T={reading.turbidity}NTU, pH={reading.ph}, C={reading.conductivity}μS/cm")
        
        # Notificar a todos los clientes conectados
        await self._broadcast_to_clients()
        await self._broadcast_to_admin()
    
    async def _broadcast_to_clients(self):
        """Envía la última lectura a todos los clientes de monitoreo"""
        if not self.monitor_clients:
            return
            
        data = self.latest_reading.to_dict()
        disconnected_clients = []
        data_size = len(json.dumps(data))
        
        for client in self.monitor_clients:
            try:
                await client.send_json(data)
                
                # INTEGRACIÓN: Registrar envío en sistema de monitoreo
                await system_monitor.record_event(SystemEvent(
                    event_type=EventType.DATA_SENT,
                    timestamp=datetime.now(),
                    source="water_monitor_broadcast",
                    details={
                        "bytes": data_size,
                        "protocol": "WebSocket",
                        "data_type": "sensor_reading",
                        "explanation": "Datos enviados via WebSocket para visualización en tiempo real"
                    }
                ))
                
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
    
    def add_monitor_client(self, websocket: WebSocket) -> str:
        """Registra un nuevo cliente de monitoreo y retorna ID único"""
        connection_id = self.generate_connection_id(websocket, "monitor")
        self.monitor_clients.append(websocket)
        self.connection_registry[connection_id] = {
            "websocket": websocket,
            "type": "monitor",
            "connected_at": datetime.now()
        }
        self.stats["connected_clients"] = len(self.monitor_clients)
        logger.info(f"👥 Cliente de monitoreo conectado. Total: {len(self.monitor_clients)}")
        return connection_id
    
    def remove_monitor_client(self, websocket: WebSocket):
        """Remueve un cliente de monitoreo"""
        if websocket in self.monitor_clients:
            self.monitor_clients.remove(websocket)
            # Remover del registro también
            connection_id = None
            for conn_id, info in self.connection_registry.items():
                if info["websocket"] == websocket:
                    connection_id = conn_id
                    break
            if connection_id:
                del self.connection_registry[connection_id]
                
            self.stats["connected_clients"] = len(self.monitor_clients)
            logger.info(f"👥 Cliente de monitoreo desconectado. Total: {len(self.monitor_clients)}")
    
    def add_admin_client(self, websocket: WebSocket) -> str:
        """Registra un nuevo cliente administrador"""
        connection_id = self.generate_connection_id(websocket, "admin")
        self.admin_clients.append(websocket)
        self.connection_registry[connection_id] = {
            "websocket": websocket,
            "type": "admin",
            "connected_at": datetime.now()
        }
        logger.info(f"🛠️ Cliente admin conectado. Total: {len(self.admin_clients)}")
        return connection_id
    
    def remove_admin_client(self, websocket: WebSocket):
        """Remueve un cliente administrador"""
        if websocket in self.admin_clients:
            self.admin_clients.remove(websocket)
            # Remover del registro también
            connection_id = None
            for conn_id, info in self.connection_registry.items():
                if info["websocket"] == websocket:
                    connection_id = conn_id
                    break
            if connection_id:
                del self.connection_registry[connection_id]
                
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
    logger.info("🎭 Iniciando generación de datos simulados cada {:.1f} segundos".format(MOCK_DATA_CONFIG["interval_seconds"]))
    
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
    - Logging educativo para entender el proceso
    
    ¿Por qué HTTP y no WebSocket para Arduino?
    - Menor consumo de memoria RAM
    - Implementación más simple
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
            logger.info(f"✅ Datos del Arduino procesados y distribuidos a {len(water_state.monitor_clients)} clientes")
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

@monitor_websocket_events
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
    connection_id = water_state.add_monitor_client(websocket)
    connection_start_time = time.time()
    
    try:
        # Enviar datos actuales inmediatamente al conectarse
        initial_data = water_state.latest_reading.to_dict()
        await websocket.send_json(initial_data)
        logger.info(f"📊 Cliente de monitoreo conectado y datos iniciales enviados (conexión: {connection_id[:8]})")
        
        # INTEGRACIÓN: Registrar conexión educativa
        await system_monitor.record_event(SystemEvent(
            event_type=EventType.CONNECTION,
            timestamp=datetime.now(),
            source="water_monitor_websocket",
            details={
                "client_type": "water_dashboard",
                "protocol": "WebSocket",
                "explanation": "Dashboard usa WebSocket para recibir datos en tiempo real sin polling",
                "connection_id": connection_id
            }
        ))
        
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
                    
                    # INTEGRACIÓN: Registrar interacción
                    await system_monitor.record_event(SystemEvent(
                        event_type=EventType.DATA_RECEIVED,
                        timestamp=datetime.now(),
                        source="water_monitor_client",
                        details={
                            "message_type": client_data.get("type", "unknown"),
                            "bytes": len(message),
                            "protocol": "WebSocket",
                            "explanation": "Cliente envía comando interactivo via WebSocket"
                        }
                    ))
                    
                except json.JSONDecodeError:
                    logger.warning(f"🚨 JSON inválido del cliente: {message}")
                    
            except asyncio.TimeoutError:
                # Verificar que la conexión sigue activa enviando un mensaje de heartbeat
                try:
                    heartbeat_data = {
                        "type": "heartbeat",
                        "timestamp": datetime.now().isoformat(),
                        "server_status": "active",
                        "connected_clients": len(water_state.monitor_clients),
                        "data_source": water_state.latest_reading.source.value
                    }
                    await websocket.send_json(heartbeat_data)
                    logger.debug("🏓 Heartbeat enviado al cliente de monitoreo")
                except:
                    logger.info("💔 Conexión de monitoreo perdida (heartbeat falló)")
                    break
                    
    except WebSocketDisconnect:
        logger.info(f"🔌 Cliente de monitoreo desconectado normalmente (conexión: {connection_id[:8]})")
    except Exception as e:
        logger.error(f"💥 Error en WebSocket de monitoreo: {str(e)}")
    finally:
        water_state.remove_monitor_client(websocket)
        
        # INTEGRACIÓN: Registrar desconexión con duración
        duration = (time.time() - connection_start_time) * 1000
        await system_monitor.record_event(SystemEvent(
            event_type=EventType.DISCONNECTION,
            timestamp=datetime.now(),
            source="water_monitor_websocket",
            details={
                "client_type": "water_dashboard",
                "reason": "websocket_closed",
                "session_duration_ms": duration,
                "connection_id": connection_id
            },
            duration_ms=duration
        ))

@monitor_websocket_events
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
    connection_id = water_state.add_admin_client(websocket)
    connection_start_time = time.time()
    
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
        logger.info(f"🛠️ Cliente admin conectado y estado inicial enviado (conexión: {connection_id[:8]})")
        
        # INTEGRACIÓN: Registrar conexión admin
        await system_monitor.record_event(SystemEvent(
            event_type=EventType.CONNECTION,
            timestamp=datetime.now(),
            source="admin_websocket",
            details={
                "client_type": "admin_panel",
                "protocol": "WebSocket",
                "explanation": "Panel admin usa WebSocket para control bidireccional del sistema",
                "connection_id": connection_id
            }
        ))
        
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
                    old_mode = water_state.use_mock_data
                    water_state.use_mock_data = new_mode
                    
                    response = {
                        "type": "command_response",
                        "command": "set_mock_mode",
                        "success": True,
                        "message": f"Modo cambiado de {'simulado' if old_mode else 'real'} a {'simulado' if new_mode else 'real'}",
                        "new_value": new_mode
                    }
                    await websocket.send_json(response)
                    logger.info(f"🔄 Modo de datos cambiado a: {'simulado' if new_mode else 'real'}")
                    
                    # INTEGRACIÓN: Registrar cambio de modo
                    await system_monitor.record_event(SystemEvent(
                        event_type=EventType.DATA_RECEIVED,
                        timestamp=datetime.now(),
                        source="admin_command",
                        details={
                            "command": "set_mock_mode",
                            "old_mode": "mock" if old_mode else "arduino",
                            "new_mode": "mock" if new_mode else "arduino",
                            "explanation": f"Sistema cambiado a modo {'simulado' if new_mode else 'real'} desde panel admin"
                        }
                    ))
                
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
        logger.info(f"🔌 Cliente admin desconectado (conexión: {connection_id[:8]})")
    except Exception as e:
        logger.error(f"💥 Error en WebSocket admin: {str(e)}")
    finally:
        water_state.remove_admin_client(websocket)
        
        # INTEGRACIÓN: Registrar desconexión admin
        duration = (time.time() - connection_start_time) * 1000
        await system_monitor.record_event(SystemEvent(
            event_type=EventType.DISCONNECTION,
            timestamp=datetime.now(),
            source="admin_websocket",
            details={
                "client_type": "admin_panel",
                "reason": "websocket_closed",
                "session_duration_ms": duration,
                "connection_id": connection_id
            },
            duration_ms=duration
        ))

# ============================================================================
# INTERFAZ WEB DE ADMINISTRACIÓN
# ============================================================================

async def get_admin_dashboard():
    """
    Página Web del Dashboard de Administración
    ========================================
    
    Carga la página desde el archivo HTML en static/
    """
    html_path = os.path.join("static", "admin_dashboard.html")
    if os.path.exists(html_path):
        logger.info("🛠️ Sirviendo dashboard de administración desde archivo")
        return FileResponse(html_path)
    else:
        logger.warning("⚠️ Archivo admin_dashboard.html no encontrado")
        return HTMLResponse(
            "<html><body><h1>❌ Dashboard Admin no encontrado</h1>"
            "<p>El archivo admin_dashboard.html no existe en static/</p></body></html>",
            status_code=404
        )

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
    logger.info("🔗 Registrando rutas del sistema de monitoreo educativo...")
    
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
            logger.info("📊 Sirviendo página de monitoreo de agua")
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
        """Endpoint HTTP POST optimizado para Arduino IoT"""
        return await arduino_http_endpoint(request)
    
    # ========================================================================
    # WEBSOCKET ENDPOINTS
    # ========================================================================
    
    @app.websocket("/water-monitor")
    async def monitor_websocket_route(websocket: WebSocket):
        """WebSocket para clientes de monitoreo del dashboard de agua"""
        await monitor_websocket_endpoint(websocket)
    
    @app.websocket("/admin-dashboard/ws")
    async def admin_websocket_route(websocket: WebSocket):
        """WebSocket para panel de administración del sistema"""
        await admin_websocket_endpoint(websocket)
    
    # ========================================================================
    # EVENTOS DEL CICLO DE VIDA
    # ========================================================================
    
    @app.on_event("startup")
    async def startup_water_monitor():
        """Inicializar sistema de monitoreo al arrancar"""
        logger.info("🚀 Iniciando sistema de monitoreo de agua educativo...")
        
        # Iniciar tarea de generación de datos mock
        water_state.mock_task = asyncio.create_task(generate_mock_data())
        logger.info("🎭 Tarea de datos simulados iniciada para demos y desarrollo")
        
        # INTEGRACIÓN: Registrar inicio en sistema de monitoreo
        await system_monitor.record_event(SystemEvent(
            event_type=EventType.CONNECTION,
            timestamp=datetime.now(),
            source="water_monitor_startup",
            details={
                "subsystem": "water_monitoring",
                "mock_data_enabled": water_state.use_mock_data,
                "explanation": "Sistema de monitoreo de agua iniciado correctamente"
            }
        ))
    
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