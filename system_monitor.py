"""
Monitor de Sistema Distribuido - Visualización Educativa
========================================================

Este módulo proporciona herramientas educativas para visualizar
y entender el funcionamiento de sistemas distribuidos en tiempo real.

Conceptos Demostrados:
=====================
Comunicación Asíncrona: WebSockets vs HTTP
Métricas de Sistema: Latencia, throughput, conexiones
Topología de Red: Visualización de conexiones
Performance Monitoring: CPU, memoria, red
Debug Tools: Logs estructurados, tracing
Real-time Updates: Actualizaciones instantáneas

Este módulo es especialmente útil para:
- Enseñar conceptos de sistemas distribuidos
- Debugging de aplicaciones IoT
- Monitoreo de performance en tiempo real
- Demostración de patrones de comunicación

"""

import asyncio
import json
import time
import psutil
import platform
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from collections import deque
from enum import Enum

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from logging_config import get_logger

logger = get_logger(__name__)

class EventType(Enum):
    """Tipos de eventos del sistema"""
    CONNECTION = "connection"
    DISCONNECTION = "disconnection"
    DATA_RECEIVED = "data_received"
    DATA_SENT = "data_sent"
    ERROR = "error"
    SYSTEM_METRIC = "system_metric"

@dataclass
class SystemEvent:
    """Evento del sistema con timestamp y detalles"""
    event_type: EventType
    timestamp: datetime
    source: str
    details: Dict[str, Any]
    duration_ms: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "details": self.details,
            "duration_ms": self.duration_ms
        }

@dataclass
class SystemMetrics:
    """Métricas del sistema en tiempo real"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    network_io: Dict[str, int]
    active_connections: int
    total_events: int
    events_per_second: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "cpu_percent": round(self.cpu_percent, 2),
            "memory_percent": round(self.memory_percent, 2),
            "network_io": self.network_io,
            "active_connections": self.active_connections,
            "total_events": self.total_events,
            "events_per_second": round(self.events_per_second, 2)
        }

class DistributedSystemMonitor:
    """
    Monitor Avanzado de Sistema Distribuido - CORREGIDO
    =================================================
    
    CAMBIOS IMPORTANTES:
    - Separación clara entre conexiones del sistema de monitoreo y clientes web reales
    - Solo cuenta como "active_connections" las conexiones de clientes web (dashboard + admin)
    - Las conexiones del sistema de monitoreo se rastrean por separado para debugging
    """
    
    def __init__(self):
        # Almacén de eventos recientes
        self.recent_events: deque = deque(maxlen=1000)
        
        # CORREGIDO: Separación clara entre tipos de conexiones
        self.monitor_clients: List[WebSocket] = []  # Solo conexiones del sistema de monitoreo
        
        # Métricas del sistema
        self.metrics_history: deque = deque(maxlen=100)
        
        # Contadores para estadísticas
        self.counters = {
            "total_connections": 0,
            "total_disconnections": 0,
            "total_data_messages": 0,
            "total_errors": 0,
            "bytes_sent": 0,
            "bytes_received": 0
        }
        
        # CORREGIDO: Rastreo específico de conexiones por tipo
        self.connection_registry = {
            "water_monitor_clients": set(),    # IDs únicos de clientes del dashboard de agua
            "admin_clients": set(),            # IDs únicos de clientes admin  
            "system_monitor_clients": set(),   # IDs únicos del sistema de monitoreo (NO se cuenta en active_connections)
            "arduino_active": False,          # Estado del Arduino
            "last_arduino_ping": None         # Última vez que Arduino envió datos
        }
        
        # Información del sistema
        self.system_info = {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_count": psutil.cpu_count(),
            "memory_total": psutil.virtual_memory().total,
            "start_time": datetime.now()
        }
        
        # Tarea de monitoreo de métricas
        self.metrics_task: Optional[asyncio.Task] = None
        
        logger.info("🔍 Monitor de sistema distribuido inicializado con conteo de conexiones corregido")
    
    def generate_connection_id(self, websocket: WebSocket, client_type: str) -> str:
        """Genera un ID único para cada conexión WebSocket"""
        client_host = getattr(websocket.client, 'host', 'unknown') if websocket.client else 'unknown'
        client_port = getattr(websocket.client, 'port', 0) if websocket.client else 0
        timestamp = int(time.time() * 1000)
        return f"{client_type}_{client_host}_{client_port}_{timestamp}"
    
    def get_web_client_count(self) -> int:
        """
        NUEVO: Función específica para contar SOLO clientes web reales
        
        Returns:
            int: Número total de clientes web conectados (dashboard + admin, excluyendo sistema de monitoreo)
        """
        return len(self.connection_registry["water_monitor_clients"]) + len(self.connection_registry["admin_clients"])
    
    async def record_event(self, event: SystemEvent):
        """Registra un nuevo evento del sistema con logging educativo mejorado"""
        self.recent_events.append(event)
        
        # Actualizar contadores
        if event.event_type == EventType.CONNECTION:
            self.counters["total_connections"] += 1
            
            # CORREGIDO: Logging educativo específico con separación de tipos
            if "websocket_monitor_websocket" in event.source.lower():
                logger.info(f"🌊 Cliente del dashboard de agua conectado via WebSocket (total dashboard: {len(self.connection_registry['water_monitor_clients'])})")
            elif "admin_websocket" in event.source.lower():
                logger.info(f"🛠️ Panel de administración conectado via WebSocket (total admin: {len(self.connection_registry['admin_clients'])})")
            elif "system_monitor" in event.source.lower():
                logger.info(f"🔍 Monitor de sistema conectado para observabilidad (NO cuenta como cliente web)")
            else:
                logger.info(f"🔗 Nueva conexión de tipo desconocido: {event.source}")
                
        elif event.event_type == EventType.DISCONNECTION:
            self.counters["total_disconnections"] += 1
            
            if "websocket_monitor_websocket" in event.source.lower():
                logger.info(f"🔌 Cliente del dashboard desconectado (quedan {len(self.connection_registry['water_monitor_clients'])} dashboard activos)")
            elif "admin_websocket" in event.source.lower():
                logger.info(f"🛠️ Panel de administración desconectado (quedan {len(self.connection_registry['admin_clients'])} admin activos)")
            elif "system_monitor" in event.source.lower():
                logger.info(f"🔍 Monitor de sistema desconectado")
                
        elif event.event_type in [EventType.DATA_RECEIVED, EventType.DATA_SENT]:
            self.counters["total_data_messages"] += 1
            if "bytes" in event.details:
                if event.event_type == EventType.DATA_SENT:
                    self.counters["bytes_sent"] += event.details["bytes"]
                else:
                    self.counters["bytes_received"] += event.details["bytes"]
                    
            # CORREGIDO: Logging educativo para datos con información de conexiones web
            if event.event_type == EventType.DATA_RECEIVED and "arduino" in event.source.lower():
                self.connection_registry["arduino_active"] = True
                self.connection_registry["last_arduino_ping"] = datetime.now()
                web_clients = self.get_web_client_count()
                logger.info(f"📡 Datos del Arduino recibidos via HTTP POST: {event.details.get('bytes', 0)} bytes (distribuir a {web_clients} clientes web)")
                
        elif event.event_type == EventType.ERROR:
            self.counters["total_errors"] += 1
            logger.warning(f"💥 Error en el sistema: {event.details.get('error', 'Error desconocido')}")
        
        # Notificar a clientes conectados al sistema de monitoreo
        await self._broadcast_event(event)
        
        logger.debug(f"📊 Evento registrado: {event.event_type.value} desde {event.source}")
    
    async def record_connection(self, websocket: WebSocket, client_type: str):
        """CORREGIDO: Registra una nueva conexión con categorización apropiada"""
        connection_id = self.generate_connection_id(websocket, client_type)
        
        # CORREGIDO: Categorizar conexiones apropiadamente
        if client_type == "monitor":
            # Cliente del dashboard de agua (SÍ cuenta como cliente web)
            self.connection_registry["water_monitor_clients"].add(connection_id)
        elif client_type == "admin":
            # Cliente del panel admin (SÍ cuenta como cliente web)
            self.connection_registry["admin_clients"].add(connection_id)
        elif client_type == "system_monitor":
            # Monitor de sistema (NO cuenta como cliente web)
            self.connection_registry["system_monitor_clients"].add(connection_id)
        else:
            logger.warning(f"⚠️ Tipo de cliente desconocido: {client_type}")
            
        # Registrar evento con información detallada
        web_client_count = self.get_web_client_count()
        await self.record_event(SystemEvent(
            event_type=EventType.CONNECTION,
            timestamp=datetime.now(),
            source=f"websocket_{client_type}",
            details={
                "client_type": client_type,
                "connection_id": connection_id,
                "client_ip": getattr(websocket.client, 'host', 'unknown') if websocket.client else 'unknown',
                "total_web_connections": web_client_count,  # CORREGIDO: Solo clientes web
                "is_web_client": client_type in ["monitor", "admin"],  # NUEVO: Flag para identificar
                "breakdown": {  # NUEVO: Desglose detallado
                    "dashboard_clients": len(self.connection_registry["water_monitor_clients"]),
                    "admin_clients": len(self.connection_registry["admin_clients"]),
                    "system_monitor_clients": len(self.connection_registry["system_monitor_clients"])
                }
            }
        ))
        
        return connection_id
    
    async def record_disconnection(self, connection_id: str, client_type: str, duration_ms: float = 0.0):
        """CORREGIDO: Registra una desconexión con categorización apropiada"""
        
        # CORREGIDO: Remover de la categoría apropiada
        if client_type == "monitor" and connection_id in self.connection_registry["water_monitor_clients"]:
            self.connection_registry["water_monitor_clients"].remove(connection_id)
        elif client_type == "admin" and connection_id in self.connection_registry["admin_clients"]:
            self.connection_registry["admin_clients"].remove(connection_id)
        elif client_type == "system_monitor" and connection_id in self.connection_registry["system_monitor_clients"]:
            self.connection_registry["system_monitor_clients"].remove(connection_id)
            
        # Registrar evento con información detallada
        web_client_count = self.get_web_client_count()
        await self.record_event(SystemEvent(
            event_type=EventType.DISCONNECTION,
            timestamp=datetime.now(),
            source=f"websocket_{client_type}",
            details={
                "client_type": client_type,
                "connection_id": connection_id,
                "total_web_connections": web_client_count,  # CORREGIDO: Solo clientes web
                "is_web_client": client_type in ["monitor", "admin"],  # NUEVO
                "breakdown": {  # NUEVO: Desglose detallado
                    "dashboard_clients": len(self.connection_registry["water_monitor_clients"]),
                    "admin_clients": len(self.connection_registry["admin_clients"]),
                    "system_monitor_clients": len(self.connection_registry["system_monitor_clients"])
                }
            },
            duration_ms=duration_ms
        ))
    
    async def record_arduino_data(self, data_size: int):
        """Registra datos recibidos del Arduino"""
        self.connection_registry["arduino_active"] = True
        self.connection_registry["last_arduino_ping"] = datetime.now()
        
        await self.record_event(SystemEvent(
            event_type=EventType.DATA_RECEIVED,
            timestamp=datetime.now(),
            source="arduino_data",
            details={
                "bytes": data_size,
                "protocol": "HTTP_POST",
                "explanation": "Arduino usa HTTP POST porque consume menos RAM que WebSocket",
                "web_clients_to_notify": self.get_web_client_count()  # NUEVO
            }
        ))
    
    async def _broadcast_event(self, event: SystemEvent):
        """Envía el evento a todos los clientes conectados del sistema de monitoreo"""
        if not self.monitor_clients:
            return
        
        event_data = {
            "type": "system_event",
            "event": event.to_dict()
        }
        
        disconnected_clients = []
        for client in self.monitor_clients:
            try:
                await client.send_json(event_data)
            except Exception as e:
                logger.warning(f"🔌 Cliente de monitor desconectado: {str(e)}")
                disconnected_clients.append(client)
        
        # Limpiar clientes desconectados
        for client in disconnected_clients:
            self.monitor_clients.remove(client)
    
    async def collect_system_metrics(self):
        """Recolecta métricas del sistema en tiempo real"""
        logger.info("📊 Iniciando recolección de métricas del sistema cada 2 segundos")
        
        while True:
            try:
                # Obtener métricas del sistema
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                network = psutil.net_io_counters()
                
                # Calcular eventos por segundo
                current_time = datetime.now()
                events_in_last_second = len([
                    e for e in self.recent_events 
                    if (current_time - e.timestamp).total_seconds() <= 1
                ])
                
                # CORREGIDO: Contar SOLO conexiones web reales, excluyendo sistema de monitoreo
                active_web_connections = self.get_web_client_count()
                
                # Verificar si Arduino sigue activo (timeout de 10 segundos)
                if (self.connection_registry["last_arduino_ping"] and 
                    (current_time - self.connection_registry["last_arduino_ping"]).total_seconds() > 10):
                    self.connection_registry["arduino_active"] = False
                
                metrics = SystemMetrics(
                    timestamp=current_time,
                    cpu_percent=cpu_percent,
                    memory_percent=memory.percent,
                    network_io={
                        "bytes_sent": network.bytes_sent,
                        "bytes_recv": network.bytes_recv,
                        "packets_sent": network.packets_sent,
                        "packets_recv": network.packets_recv
                    },
                    active_connections=active_web_connections,  # CORREGIDO: Solo clientes web
                    total_events=len(self.recent_events),
                    events_per_second=events_in_last_second
                )
                
                self.metrics_history.append(metrics)
                
                # Enviar métricas a clientes del sistema de monitoreo
                await self._broadcast_metrics(metrics)
                
                # Esperar antes de la siguiente recolección
                await asyncio.sleep(2)
                
            except asyncio.CancelledError:
                logger.info("🛑 Recolección de métricas cancelada")
                break
            except Exception as e:
                logger.error(f"💥 Error recolectando métricas: {str(e)}")
                await asyncio.sleep(5)
    
    async def _broadcast_metrics(self, metrics: SystemMetrics):
        """Envía métricas a todos los clientes del sistema de monitoreo"""
        if not self.monitor_clients:
            return
        
        metrics_data = {
            "type": "system_metrics",
            "metrics": metrics.to_dict(),
            "counters": self.counters,
            "connection_states": {
                "arduino_active": self.connection_registry["arduino_active"],
                # CORREGIDO: Información detallada y precisa sobre conexiones
                "water_monitor_clients": len(self.connection_registry["water_monitor_clients"]),
                "admin_clients": len(self.connection_registry["admin_clients"]),
                "system_monitor_clients": len(self.connection_registry["system_monitor_clients"]),
                "total_web_clients": self.get_web_client_count(),  # NUEVO: Total correcto
                "last_arduino_ping": self.connection_registry["last_arduino_ping"].isoformat() if self.connection_registry["last_arduino_ping"] else None
            },
            "system_info": {
                **self.system_info,
                "start_time": self.system_info["start_time"].isoformat(),
                "uptime_seconds": (datetime.now() - self.system_info["start_time"]).total_seconds()
            }
        }
        
        disconnected_clients = []
        for client in self.monitor_clients:
            try:
                await client.send_json(metrics_data)
            except Exception:
                disconnected_clients.append(client)
        
        # Limpiar clientes desconectados
        for client in disconnected_clients:
            self.monitor_clients.remove(client)
    
    def add_monitor_client(self, websocket: WebSocket):
        """Registra un nuevo cliente de monitoreo del sistema (NO es cliente web)"""
        self.monitor_clients.append(websocket)
        logger.info(f"🔍 Cliente de monitoreo de SISTEMA conectado. Monitor clients: {len(self.monitor_clients)} (NO cuenta como cliente web)")
    
    def remove_monitor_client(self, websocket: WebSocket):
        """Remueve un cliente de monitoreo del sistema"""
        if websocket in self.monitor_clients:
            self.monitor_clients.remove(websocket)
            logger.info(f"🔍 Cliente de monitoreo de SISTEMA desconectado. Monitor clients: {len(self.monitor_clients)}")
    
    async def start_monitoring(self):
        """Inicia el monitoreo del sistema"""
        if not self.metrics_task or self.metrics_task.done():
            self.metrics_task = asyncio.create_task(self.collect_system_metrics())
            logger.info("🚀 Monitoreo de sistema iniciado")
            
            # Evento inicial
            await self.record_event(SystemEvent(
                event_type=EventType.CONNECTION,
                timestamp=datetime.now(),
                source="system_startup",
                details={"message": "Sistema de monitoreo distribuido iniciado correctamente"}
            ))
    
    async def stop_monitoring(self):
        """Detiene el monitoreo del sistema"""
        if self.metrics_task and not self.metrics_task.done():
            self.metrics_task.cancel()
            try:
                await self.metrics_task
            except asyncio.CancelledError:
                logger.info("✅ Monitoreo de sistema detenido")

# Instancia global del monitor
system_monitor = DistributedSystemMonitor()

async def system_monitor_websocket(websocket: WebSocket):
    """
    WebSocket para Monitoreo del Sistema Distribuido - CORREGIDO
    ==========================================================
    
    IMPORTANTE: Este WebSocket es para el sistema de monitoreo interno,
    NO cuenta como cliente web en las estadísticas.
    """
    await websocket.accept()
    system_monitor.add_monitor_client(websocket)
    
    # CORREGIDO: Registrar como conexión del sistema de monitoreo (no cliente web)
    connection_id = await system_monitor.record_connection(websocket, "system_monitor")
    
    connection_start_time = time.time()
    
    try:
        # Enviar datos iniciales
        initial_data = {
            "type": "initial_state",
            "system_info": {
                **system_monitor.system_info,
                "start_time": system_monitor.system_info["start_time"].isoformat(),
                "uptime_seconds": (datetime.now() - system_monitor.system_info["start_time"]).total_seconds()
            },
            "counters": system_monitor.counters,
            "connection_states": {
                "arduino_active": system_monitor.connection_registry["arduino_active"],
                # CORREGIDO: Información precisa sobre tipos de conexiones
                "water_monitor_clients": len(system_monitor.connection_registry["water_monitor_clients"]),
                "admin_clients": len(system_monitor.connection_registry["admin_clients"]),
                "system_monitor_clients": len(system_monitor.connection_registry["system_monitor_clients"]),
                "total_web_clients": system_monitor.get_web_client_count(),  # NUEVO
            },
            "recent_events": [event.to_dict() for event in list(system_monitor.recent_events)[-20:]],
            "metrics_history": [metrics.to_dict() for metrics in list(system_monitor.metrics_history)[-10:]]
        }
        await websocket.send_json(initial_data)
        
        # Mantener conexión activa
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                
                # Procesar comandos del cliente
                try:
                    command = json.loads(message)
                    
                    if command.get("action") == "get_full_history":
                        # Enviar historial completo
                        history_data = {
                            "type": "full_history",
                            "events": [event.to_dict() for event in system_monitor.recent_events],
                            "metrics": [metrics.to_dict() for metrics in system_monitor.metrics_history]
                        }
                        await websocket.send_json(history_data)
                        
                        # Log educativo
                        await system_monitor.record_event(SystemEvent(
                            event_type=EventType.DATA_SENT,
                            timestamp=datetime.now(),
                            source="system_monitor",
                            details={
                                "action": "full_history_sent",
                                "events_count": len(system_monitor.recent_events),
                                "metrics_count": len(system_monitor.metrics_history),
                                "bytes": len(json.dumps(history_data)),
                                "web_clients_active": system_monitor.get_web_client_count()  # NUEVO
                            }
                        ))
                        
                    elif command.get("action") == "clear_events":
                        # Limpiar eventos (solo para testing)
                        system_monitor.recent_events.clear()
                        await websocket.send_json({"type": "events_cleared"})
                        
                        await system_monitor.record_event(SystemEvent(
                            event_type=EventType.DATA_RECEIVED,
                            timestamp=datetime.now(),
                            source="system_monitor",
                            details={"action": "events_cleared_by_user"}
                        ))
                    
                    # Registrar evento de comando recibido
                    await system_monitor.record_event(SystemEvent(
                        event_type=EventType.DATA_RECEIVED,
                        timestamp=datetime.now(),
                        source="system_monitor_client",
                        details={
                            "command": command.get("action", "unknown"), 
                            "bytes": len(message),
                            "protocol": "WebSocket",
                            "explanation": "Cliente del sistema de monitoreo usa WebSocket para comandos interactivos"
                        }
                    ))
                    
                except json.JSONDecodeError:
                    logger.warning(f"🚨 JSON inválido del cliente monitor: {message}")
                    
            except asyncio.TimeoutError:
                # Verificar que la conexión sigue activa enviando un mensaje de heartbeat
                try:
                    await websocket.send_json({
                        "type": "heartbeat",
                        "timestamp": datetime.now().isoformat(),
                        "system_status": "active",
                        "connections": {
                            "water_monitor": len(system_monitor.connection_registry["water_monitor_clients"]),
                            "admin": len(system_monitor.connection_registry["admin_clients"]),
                            "system_monitor": len(system_monitor.connection_registry["system_monitor_clients"]),
                            "arduino": system_monitor.connection_registry["arduino_active"],
                            "total_web_clients": system_monitor.get_web_client_count()  # NUEVO
                        }
                    })
                    logger.debug("🏓 Heartbeat enviado al cliente de monitoreo")
                except:
                    logger.info("💔 Conexión de monitoreo perdida (heartbeat falló)")
                    break
                
    except WebSocketDisconnect:
        logger.info("🔌 Cliente de monitoreo desconectado")
    except Exception as e:
        logger.error(f"💥 Error en WebSocket de monitoreo: {str(e)}")
    finally:
        system_monitor.remove_monitor_client(websocket)
        
        # Registrar evento de desconexión con duración
        duration = (time.time() - connection_start_time) * 1000
        await system_monitor.record_disconnection(connection_id, "system_monitor", duration)

async def get_system_monitor_page():
    """Página Web del Monitor de Sistema Distribuido"""
    html_path = os.path.join("static", "system_monitor.html")
    if os.path.exists(html_path):
        logger.info("🔍 Sirviendo monitor de sistema desde archivo")
        return FileResponse(html_path)
    else:
        logger.warning("⚠️ Archivo system_monitor.html no encontrado")
        return HTMLResponse(
            "<html><body><h1>❌ Monitor de Sistema no encontrado</h1>"
            "<p>El archivo system_monitor.html no existe en static/</p></body></html>",
            status_code=404
        )

def integrate_system_monitor(app: FastAPI):
    """Integra el monitor de sistema con la aplicación principal"""
    
    @app.get("/system-monitor")
    async def get_system_monitor_route():
        """Página del monitor de sistema"""
        return await get_system_monitor_page()
    
    @app.websocket("/system-monitor/ws")
    async def system_monitor_ws_route(websocket: WebSocket):
        """WebSocket del monitor de sistema"""
        await system_monitor_websocket(websocket)
    
    @app.on_event("startup")
    async def start_system_monitoring():
        """Iniciar monitoreo del sistema"""
        await system_monitor.start_monitoring()
        logger.info("🔍 Sistema de monitoreo integrado e iniciado con conteo de conexiones corregido")
    
    @app.on_event("shutdown")
    async def stop_system_monitoring():
        """Detener monitoreo del sistema"""
        await system_monitor.stop_monitoring()
        logger.info("🔍 Sistema de monitoreo detenido")

def monitor_websocket_events(func):
    """
    Decorador para monitorear automáticamente eventos de WebSocket - CORREGIDO
    """
    async def wrapper(websocket: WebSocket, *args, **kwargs):
        start_time = time.time()
        client_type = "unknown"
        connection_id = None
        
        # CORREGIDO: Determinar tipo de cliente apropiadamente
        if "monitor_websocket" in func.__name__ and "admin" not in func.__name__:
            client_type = "monitor"  # Cliente del dashboard de agua (SÍ cuenta como web)
        elif "admin" in func.__name__:
            client_type = "admin"    # Cliente del panel admin (SÍ cuenta como web)
        elif "system_monitor" in func.__name__:
            client_type = "system_monitor"  # Sistema de monitoreo (NO cuenta como web)
        
        # Registrar conexión con tipo correcto
        connection_id = await system_monitor.record_connection(websocket, client_type)
        
        try:
            result = await func(websocket, *args, **kwargs)
            return result
        except Exception as e:
            # Registrar error
            await system_monitor.record_event(SystemEvent(
                event_type=EventType.ERROR,
                timestamp=datetime.now(),
                source=f"websocket_{func.__name__}",
                details={
                    "error": str(e), 
                    "error_type": type(e).__name__,
                    "function": func.__name__,
                    "client_type": client_type
                }
            ))
            raise
        finally:
            # Registrar desconexión
            if connection_id:
                duration = (time.time() - start_time) * 1000
                await system_monitor.record_disconnection(connection_id, client_type, duration)
    
    return wrapper

# Exportar instancia global para uso en otros módulos
__all__ = ['system_monitor', 'SystemEvent', 'EventType', 'integrate_system_monitor', 'monitor_websocket_events']