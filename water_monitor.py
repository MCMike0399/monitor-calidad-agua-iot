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

logger = get_logger(__name__)

# Configuración de datos mock para pruebas sin Arduino
MOCK_DATA_CONFIG = {
    "interval_seconds": 3.0,
    "turbidity_range": (5, 800),
    "ph_range": (3, 10),
    "conductivity_range": (100, 1200)
}

class DataSource(Enum):
    """Enum para identificar el origen de los datos"""
    MOCK = "mock"
    ARDUINO = "arduino"

@dataclass
class SensorReading:
    """Clase de datos para una lectura de sensores"""
    turbidity: float
    ph: float
    conductivity: float
    timestamp: datetime
    source: DataSource
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte la lectura a diccionario para JSON serialization"""
        return {
            "T": round(self.turbidity, 2),
            "PH": round(self.ph, 2),
            "C": round(self.conductivity, 2),
            "timestamp": self.timestamp.isoformat(),
            "source": self.source.value
        }
    
    @classmethod
    def from_arduino_data(cls, data: Dict[str, Any]) -> 'SensorReading':
        """Crea una SensorReading desde datos del Arduino"""
        return cls(
            turbidity=float(data["T"]),
            ph=float(data["PH"]),
            conductivity=float(data["C"]),
            timestamp=datetime.now(),
            source=DataSource.ARDUINO
        )

class WaterMonitorState:

    def __init__(self):
        # Última lectura de sensores
        self.latest_reading: SensorReading = SensorReading(
            turbidity=25.0,
            ph=7.0,
            conductivity=300.0,
            timestamp=datetime.now(),
            source=DataSource.MOCK
        )
        
        # CORREGIDO: Separación clara de tipos de conexiones
        self.monitor_clients: List[WebSocket] = []  # Solo clientes del dashboard de agua
        self.admin_clients: List[WebSocket] = []    # Solo clientes del panel admin
        
        # NUEVO: Registro detallado con IDs únicos para debugging
        self.connection_registry: Dict[str, Dict] = {}
        
        # Configuración del sistema
        self.use_mock_data: bool = True
        self.mock_task: Optional[asyncio.Task] = None
        
        # Estadísticas del sistema
        self.stats = {
            "total_readings": 0,
            "arduino_readings": 0,
            "mock_readings": 0,
            "connected_clients": 0,  # CORREGIDO: Solo clientes web reales
            "uptime_start": datetime.now(),
            "last_arduino_connection": None
        }
        
        logger.info("🏗️ Estado del sistema inicializado con conteo de conexiones corregido")
    
    def generate_connection_id(self, websocket: WebSocket, client_type: str) -> str:
        """Genera un ID único para cada conexión"""
        client_host = getattr(websocket.client, 'host', 'unknown') if websocket.client else 'unknown'
        client_port = getattr(websocket.client, 'port', 0) if websocket.client else 0
        timestamp = int(time.time() * 1000)
        return f"{client_type}_{client_host}_{client_port}_{timestamp}"
    
    def get_web_client_count(self) -> int:
        """
        NUEVO: Función específica para contar SOLO clientes web reales
        
        Returns:
            int: Número total de clientes web conectados (dashboard + admin)
        """
        return len(self.monitor_clients) + len(self.admin_clients)
    
    async def update_reading(self, reading: SensorReading):
        """Actualiza la última lectura y notifica a todos los clientes"""
        self.latest_reading = reading
        self.stats["total_readings"] += 1
        
        if reading.source == DataSource.ARDUINO:
            self.stats["arduino_readings"] += 1
            self.stats["last_arduino_connection"] = datetime.now()
            logger.info(f"📡 Datos del Arduino: T={reading.turbidity}NTU, pH={reading.ph}, C={reading.conductivity}μS/cm")
            
            # Registrar en sistema de monitoreo
            data_json = json.dumps(reading.to_dict())
            await system_monitor.record_arduino_data(len(data_json))
        else:
            self.stats["mock_readings"] += 1
            logger.debug(f"🎭 Datos simulados: T={reading.turbidity}NTU, pH={reading.ph}, C={reading.conductivity}μS/cm")
        
        # CORREGIDO: Actualizar conteo solo de clientes web reales
        self.stats["connected_clients"] = self.get_web_client_count()
        
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
                
                # Registrar envío en sistema de monitoreo
                await system_monitor.record_event(SystemEvent(
                    event_type=EventType.DATA_SENT,
                    timestamp=datetime.now(),
                    source="water_monitor_broadcast",
                    details={
                        "bytes": data_size,
                        "protocol": "WebSocket",
                        "data_type": "sensor_reading",
                        "explanation": "Datos enviados via WebSocket para visualización en tiempo real",
                        "client_count": len(self.monitor_clients)
                    }
                ))
                
            except Exception as e:
                logger.warning(f"🔌 Cliente desconectado: {str(e)}")
                disconnected_clients.append(client)
        
        # Remover clientes desconectados
        for client in disconnected_clients:
            self.monitor_clients.remove(client)
            
        # CORREGIDO: Actualizar estadísticas solo con clientes web reales
        self.stats["connected_clients"] = self.get_web_client_count()
    
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
                ),
                # CORREGIDO: Asegurar que connected_clients refleje solo clientes web
                "connected_clients": self.get_web_client_count()
            },
            "config": {
                "use_mock_data": self.use_mock_data,
                "connected_monitor_clients": len(self.monitor_clients),
                "connected_admin_clients": len(self.admin_clients),
                # NUEVO: Información detallada para debugging
                "total_web_clients": self.get_web_client_count()
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
        """Registra un nuevo cliente de monitoreo"""
        connection_id = self.generate_connection_id(websocket, "monitor")
        self.monitor_clients.append(websocket)
        self.connection_registry[connection_id] = {
            "websocket": websocket,
            "type": "monitor",
            "connected_at": datetime.now()
        }
        
        # CORREGIDO: Actualizar conteo solo con clientes web reales
        self.stats["connected_clients"] = self.get_web_client_count()
        
        logger.info(f"👥 Cliente de monitoreo conectado. Dashboard clients: {len(self.monitor_clients)}, Total web clients: {self.get_web_client_count()}")
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
                
            # CORREGIDO: Actualizar conteo solo con clientes web reales
            self.stats["connected_clients"] = self.get_web_client_count()
            
            logger.info(f"👥 Cliente de monitoreo desconectado. Dashboard clients: {len(self.monitor_clients)}, Total web clients: {self.get_web_client_count()}")
    
    def add_admin_client(self, websocket: WebSocket) -> str:
        """Registra un nuevo cliente administrador"""
        connection_id = self.generate_connection_id(websocket, "admin")
        self.admin_clients.append(websocket)
        self.connection_registry[connection_id] = {
            "websocket": websocket,
            "type": "admin",
            "connected_at": datetime.now()
        }
        
        # CORREGIDO: Actualizar conteo solo con clientes web reales
        self.stats["connected_clients"] = self.get_web_client_count()
        
        logger.info(f"🛠️ Cliente admin conectado. Admin clients: {len(self.admin_clients)}, Total web clients: {self.get_web_client_count()}")
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
                
            # CORREGIDO: Actualizar conteo solo con clientes web reales
            self.stats["connected_clients"] = self.get_web_client_count()
            
            logger.info(f"🛠️ Cliente admin desconectado. Admin clients: {len(self.admin_clients)}, Total web clients: {self.get_web_client_count()}")

# Instancia global del estado del sistema
water_state = WaterMonitorState()

# Generador de datos simulados (sin cambios)
async def generate_mock_data():
    """Generador de Datos Simulados para Pruebas"""
    logger.info("🎭 Iniciando generación de datos simulados cada {:.1f} segundos".format(MOCK_DATA_CONFIG["interval_seconds"]))
    
    while True:
        try:
            if water_state.use_mock_data:
                mock_reading = SensorReading(
                    turbidity=round(random.uniform(*MOCK_DATA_CONFIG["turbidity_range"]), 2),
                    ph=round(random.uniform(*MOCK_DATA_CONFIG["ph_range"]), 2),
                    conductivity=round(random.uniform(*MOCK_DATA_CONFIG["conductivity_range"]), 2),
                    timestamp=datetime.now(),
                    source=DataSource.MOCK
                )
                
                await water_state.update_reading(mock_reading)
            
            await asyncio.sleep(MOCK_DATA_CONFIG["interval_seconds"])
            
        except asyncio.CancelledError:
            logger.info("🛑 Generación de datos mock cancelada")
            break
        except Exception as e:
            logger.error(f"💥 Error en generación de datos mock: {str(e)}")
            await asyncio.sleep(5)

# Endpoint HTTP para Arduino (sin cambios)
async def arduino_http_endpoint(request: Request) -> Response:
    """Endpoint HTTP POST para Recepción de Datos del Arduino"""
    try:
        content_length = int(request.headers.get("content-length", 0))
        
        if content_length == 0:
            logger.warning("🚨 Petición vacía del Arduino")
            return Response(status_code=400)
        
        body = await request.body()
        arduino_data = json.loads(body.decode('utf-8'))
        
        required_fields = ["T", "PH", "C"]
        if not all(field in arduino_data for field in required_fields):
            logger.warning(f"🚨 Datos incompletos del Arduino: {arduino_data}")
            return Response(status_code=400)
        
        reading = SensorReading.from_arduino_data(arduino_data)
        
        if not water_state.use_mock_data:
            await water_state.update_reading(reading)
            logger.info(f"✅ Datos del Arduino procesados y distribuidos a {water_state.get_web_client_count()} clientes web")
            return Response(status_code=200)
        else:
            logger.debug("🎭 Datos del Arduino ignorados (modo mock activo)")
            return Response(status_code=202)
            
    except json.JSONDecodeError as e:
        logger.error(f"💥 JSON inválido del Arduino: {str(e)}")
        return Response(status_code=400)
    except Exception as e:
        logger.error(f"💥 Error procesando datos del Arduino: {str(e)}")
        return Response(status_code=500)

# WebSocket Endpoints CORREGIDOS
@monitor_websocket_events
async def monitor_websocket_endpoint(websocket: WebSocket):
    """WebSocket para Clientes de Monitoreo (Dashboard Principal) - CONTEO CORREGIDO"""
    await websocket.accept()
    connection_id = water_state.add_monitor_client(websocket)
    connection_start_time = time.time()
    
    try:
        # Enviar datos actuales inmediatamente al conectarse
        initial_data = water_state.latest_reading.to_dict()
        await websocket.send_json(initial_data)
        
        logger.info(f"📊 Cliente de monitoreo conectado y datos iniciales enviados (conexión: {connection_id[:8]})")
        logger.info(f"📈 Estado actual: Dashboard clients: {len(water_state.monitor_clients)}, Total web clients: {water_state.get_web_client_count()}")
        
        # Registrar conexión educativa
        await system_monitor.record_event(SystemEvent(
            event_type=EventType.CONNECTION,
            timestamp=datetime.now(),
            source="water_monitor_websocket",
            details={
                "client_type": "water_dashboard",
                "protocol": "WebSocket",
                "explanation": "Dashboard usa WebSocket para recibir datos en tiempo real sin polling",
                "connection_id": connection_id,
                "total_web_clients": water_state.get_web_client_count()  # NUEVO: Info corregida
            }
        ))
        
        # Mantener conexión activa y procesar mensajes del cliente
        while True:
            try:
                message = await asyncio.wait_for(
                    websocket.receive_text(), 
                    timeout=30.0
                )
                
                try:
                    client_data = json.loads(message)
                    logger.debug(f"📨 Mensaje del cliente de monitoreo: {client_data}")
                    
                    await websocket.send_json({
                        "type": "echo",
                        "original_message": client_data,
                        "timestamp": datetime.now().isoformat(),
                        "status": "received"
                    })
                    
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
                try:
                    heartbeat_data = {
                        "type": "heartbeat",
                        "timestamp": datetime.now().isoformat(),
                        "server_status": "active",
                        "connected_clients": water_state.get_web_client_count(),  # CORREGIDO
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
        
        duration = (time.time() - connection_start_time) * 1000
        await system_monitor.record_event(SystemEvent(
            event_type=EventType.DISCONNECTION,
            timestamp=datetime.now(),
            source="water_monitor_websocket",
            details={
                "client_type": "water_dashboard",
                "reason": "websocket_closed",
                "session_duration_ms": duration,
                "connection_id": connection_id,
                "remaining_web_clients": water_state.get_web_client_count()  # NUEVO
            },
            duration_ms=duration
        ))

@monitor_websocket_events
async def admin_websocket_endpoint(websocket: WebSocket):
    """WebSocket para Panel de Administración del Sistema - CONTEO CORREGIDO"""
    await websocket.accept()
    connection_id = water_state.add_admin_client(websocket)
    connection_start_time = time.time()
    
    try:
        # Enviar estado inicial del sistema
        initial_status = {
            "type": "system_status",
            "config": {
                "use_mock_data": water_state.use_mock_data,
                "connected_monitor_clients": len(water_state.monitor_clients),
                "connected_admin_clients": len(water_state.admin_clients),
                "total_web_clients": water_state.get_web_client_count()  # NUEVO
            },
            "latest_reading": water_state.latest_reading.to_dict(),
            "stats": {
                **water_state.stats,
                "uptime_start": water_state.stats["uptime_start"].isoformat(),
                "last_arduino_connection": (
                    water_state.stats["last_arduino_connection"].isoformat() 
                    if water_state.stats["last_arduino_connection"] else None
                ),
                "connected_clients": water_state.get_web_client_count()  # CORREGIDO
            }
        }
        await websocket.send_json(initial_status)
        
        logger.info(f"🛠️ Cliente admin conectado y estado inicial enviado (conexión: {connection_id[:8]})")
        logger.info(f"📈 Estado actual: Admin clients: {len(water_state.admin_clients)}, Total web clients: {water_state.get_web_client_count()}")
        
        # Registrar conexión admin
        await system_monitor.record_event(SystemEvent(
            event_type=EventType.CONNECTION,
            timestamp=datetime.now(),
            source="admin_websocket",
            details={
                "client_type": "admin_panel",
                "protocol": "WebSocket",
                "explanation": "Panel admin usa WebSocket para control bidireccional del sistema",
                "connection_id": connection_id,
                "total_web_clients": water_state.get_web_client_count()  # NUEVO
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
                    stats_response = {
                        "type": "stats_response",
                        "stats": {
                            **water_state.stats,
                            "uptime_start": water_state.stats["uptime_start"].isoformat(),
                            "last_arduino_connection": (
                                water_state.stats["last_arduino_connection"].isoformat() 
                                if water_state.stats["last_arduino_connection"] else None
                            ),
                            "connected_clients": water_state.get_web_client_count()  # CORREGIDO
                        }
                    }
                    await websocket.send_json(stats_response)
                
                else:
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
        
        duration = (time.time() - connection_start_time) * 1000
        await system_monitor.record_event(SystemEvent(
            event_type=EventType.DISCONNECTION,
            timestamp=datetime.now(),
            source="admin_websocket",
            details={
                "client_type": "admin_panel",
                "reason": "websocket_closed",
                "session_duration_ms": duration,
                "connection_id": connection_id,
                "remaining_web_clients": water_state.get_web_client_count()  # NUEVO
            },
            duration_ms=duration
        ))

# Interfaz web de administración (sin cambios)
async def get_admin_dashboard():
    """Página Web del Dashboard de Administración"""
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

# Función principal de registro de rutas (sin cambios importantes)
def register_routes(app: FastAPI):
    """Registrar Todas las Rutas del Sistema de Monitoreo"""
    logger.info("🔗 Registrando rutas del sistema de monitoreo educativo...")
    
    # Configurar directorio de archivos estáticos
    static_dir = os.path.join(os.getcwd(), "static")
    if not os.path.exists(static_dir):
        os.makedirs(static_dir, exist_ok=True)
        logger.info(f"📁 Directorio estático creado: {static_dir}")
    
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    logger.info(f"📁 Archivos estáticos montados desde: {static_dir}")
    
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
    
    @app.post("/water-monitor/publish")
    async def arduino_http_route(request: Request):
        """Endpoint HTTP POST optimizado para Arduino IoT"""
        return await arduino_http_endpoint(request)
    
    @app.websocket("/water-monitor")
    async def monitor_websocket_route(websocket: WebSocket):
        """WebSocket para clientes de monitoreo del dashboard de agua"""
        await monitor_websocket_endpoint(websocket)
    
    @app.websocket("/admin-dashboard/ws")
    async def admin_websocket_route(websocket: WebSocket):
        """WebSocket para panel de administración del sistema"""
        await admin_websocket_endpoint(websocket)
    
    @app.on_event("startup")
    async def startup_water_monitor():
        """Inicializar sistema de monitoreo al arrancar"""
        logger.info("🚀 Iniciando sistema de monitoreo de agua educativo...")
        
        water_state.mock_task = asyncio.create_task(generate_mock_data())
        logger.info("🎭 Tarea de datos simulados iniciada para demos y desarrollo")
        
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
        
        if water_state.mock_task and not water_state.mock_task.done():
            water_state.mock_task.cancel()
            try:
                await water_state.mock_task
            except asyncio.CancelledError:
                logger.info("✅ Tarea de datos simulados cancelada")
        
        logger.info("✅ Sistema de monitoreo cerrado correctamente")
    
    logger.info("✅ Todas las rutas del sistema de monitoreo registradas")