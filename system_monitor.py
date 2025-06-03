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

# ============================================================================
# MODELOS DE DATOS PARA MONITOREO
# ============================================================================

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

# ============================================================================
# MONITOR DE SISTEMA DISTRIBUIDO
# ============================================================================

class DistributedSystemMonitor:
    """
    Monitor Avanzado de Sistema Distribuido
    ======================================
    
    Esta clase implementa un sistema de monitoreo completo que permite
    a los profesores y estudiantes ver en tiempo real:
    
    - Flujo de datos entre componentes
    - Métricas de performance del sistema
    - Eventos de conexión/desconexión
    - Latencia de comunicación
    - Uso de recursos del servidor
    
    Patrones Implementados:
    - Observer: Para notificar cambios
    - Publisher/Subscriber: Para eventos del sistema
    - Singleton: Una sola instancia de monitoreo
    """
    
    def __init__(self):
        # Almacén de eventos recientes (últimos 1000)
        self.recent_events: deque = deque(maxlen=1000)
        
        # Clientes conectados al monitor
        self.monitor_clients: List[WebSocket] = []
        
        # Métricas del sistema
        self.metrics_history: deque = deque(maxlen=100)  # Últimos 100 puntos
        
        # Contadores para estadísticas
        self.counters = {
            "total_connections": 0,
            "total_disconnections": 0,
            "total_data_messages": 0,
            "total_errors": 0,
            "bytes_sent": 0,
            "bytes_received": 0
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
        
        logger.info("🔍 Monitor de sistema distribuido inicializado")
    
    async def record_event(self, event: SystemEvent):
        """
        Registra un nuevo evento del sistema
        
        Args:
            event: Evento a registrar
        """
        self.recent_events.append(event)
        
        # Actualizar contadores
        if event.event_type == EventType.CONNECTION:
            self.counters["total_connections"] += 1
        elif event.event_type == EventType.DISCONNECTION:
            self.counters["total_disconnections"] += 1
        elif event.event_type in [EventType.DATA_RECEIVED, EventType.DATA_SENT]:
            self.counters["total_data_messages"] += 1
            if "bytes" in event.details:
                if event.event_type == EventType.DATA_SENT:
                    self.counters["bytes_sent"] += event.details["bytes"]
                else:
                    self.counters["bytes_received"] += event.details["bytes"]
        elif event.event_type == EventType.ERROR:
            self.counters["total_errors"] += 1
        
        # Notificar a clientes conectados
        await self._broadcast_event(event)
        
        logger.debug(f"📊 Evento registrado: {event.event_type.value} desde {event.source}")
    
    async def _broadcast_event(self, event: SystemEvent):
        """Envía el evento a todos los clientes conectados"""
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
        """
        Recolecta métricas del sistema en tiempo real
        """
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
                    active_connections=len(self.monitor_clients),
                    total_events=len(self.recent_events),
                    events_per_second=events_in_last_second
                )
                
                self.metrics_history.append(metrics)
                
                # Enviar métricas a clientes
                await self._broadcast_metrics(metrics)
                
                # Esperar antes de la siguiente recolección
                await asyncio.sleep(2)  # Cada 2 segundos
                
            except asyncio.CancelledError:
                logger.info("🛑 Recolección de métricas cancelada")
                break
            except Exception as e:
                logger.error(f"💥 Error recolectando métricas: {str(e)}")
                await asyncio.sleep(5)
    
    async def _broadcast_metrics(self, metrics: SystemMetrics):
        """Envía métricas a todos los clientes"""
        if not self.monitor_clients:
            return
        
        metrics_data = {
            "type": "system_metrics",
            "metrics": metrics.to_dict(),
            "counters": self.counters,
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
        """Registra un nuevo cliente de monitoreo"""
        self.monitor_clients.append(websocket)
        logger.info(f"🔍 Cliente de monitoreo conectado. Total: {len(self.monitor_clients)}")
    
    def remove_monitor_client(self, websocket: WebSocket):
        """Remueve un cliente de monitoreo"""
        if websocket in self.monitor_clients:
            self.monitor_clients.remove(websocket)
            logger.info(f"🔍 Cliente de monitoreo desconectado. Total: {len(self.monitor_clients)}")
    
    async def start_monitoring(self):
        """Inicia el monitoreo del sistema"""
        if not self.metrics_task or self.metrics_task.done():
            self.metrics_task = asyncio.create_task(self.collect_system_metrics())
            logger.info("🚀 Monitoreo de sistema iniciado")
    
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

# ============================================================================
# WEBSOCKET ENDPOINT PARA MONITOREO
# ============================================================================

async def system_monitor_websocket(websocket: WebSocket):
    """
    WebSocket para Monitoreo del Sistema Distribuido
    ===============================================
    
    Este endpoint proporciona acceso en tiempo real a:
    - Eventos del sistema
    - Métricas de performance
    - Estadísticas de comunicación
    - Información de debugging
    
    Args:
        websocket: Conexión WebSocket del cliente monitor
    """
    await websocket.accept()
    system_monitor.add_monitor_client(websocket)
    
    # Registrar evento de conexión
    await system_monitor.record_event(SystemEvent(
        event_type=EventType.CONNECTION,
        timestamp=datetime.now(),
        source="system_monitor",
        details={"client_type": "system_monitor", "endpoint": "/system-monitor/ws"}
    ))
    
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
            "recent_events": [event.to_dict() for event in list(system_monitor.recent_events)[-20:]],  # Últimos 20 eventos
            "metrics_history": [metrics.to_dict() for metrics in list(system_monitor.metrics_history)[-10:]]  # Últimos 10 puntos
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
                        
                    elif command.get("action") == "clear_events":
                        # Limpiar eventos (solo para testing)
                        system_monitor.recent_events.clear()
                        await websocket.send_json({"type": "events_cleared"})
                    
                    # Registrar evento de comando recibido
                    await system_monitor.record_event(SystemEvent(
                        event_type=EventType.DATA_RECEIVED,
                        timestamp=datetime.now(),
                        source="system_monitor_client",
                        details={"command": command.get("action", "unknown"), "bytes": len(message)}
                    ))
                    
                except json.JSONDecodeError:
                    logger.warning(f"🚨 JSON inválido del cliente monitor: {message}")
                    
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
        logger.info("🔌 Cliente de monitoreo desconectado")
    except Exception as e:
        logger.error(f"💥 Error en WebSocket de monitoreo: {str(e)}")
    finally:
        system_monitor.remove_monitor_client(websocket)
        
        # Registrar evento de desconexión
        await system_monitor.record_event(SystemEvent(
            event_type=EventType.DISCONNECTION,
            timestamp=datetime.now(),
            source="system_monitor",
            details={"client_type": "system_monitor", "reason": "websocket_closed"}
        ))

# ============================================================================
# INTERFAZ WEB DEL MONITOR DE SISTEMA
# ============================================================================

async def get_system_monitor_page():
    """
    Página Web del Monitor de Sistema Distribuido
    ============================================
    
    Carga la página desde el archivo HTML en static/
    """
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

# ============================================================================
# FUNCIONES PARA INTEGRACIÓN CON EL SISTEMA PRINCIPAL
# ============================================================================

def integrate_system_monitor(app: FastAPI):
    """
    Integra el monitor de sistema con la aplicación principal
    
    Args:
        app: Instancia de FastAPI
    """
    
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
        logger.info("🔍 Sistema de monitoreo integrado e iniciado")
    
    @app.on_event("shutdown")
    async def stop_system_monitoring():
        """Detener monitoreo del sistema"""
        await system_monitor.stop_monitoring()
        logger.info("🔍 Sistema de monitoreo detenido")

# ============================================================================
# DECORADORES PARA MONITOREO AUTOMÁTICO
# ============================================================================

def monitor_websocket_events(func):
    """
    Decorador para monitorear automáticamente eventos de WebSocket
    
    Args:
        func: Función de WebSocket a decorar
    
    Returns:
        Función decorada que registra eventos automáticamente
    """
    async def wrapper(websocket: WebSocket, *args, **kwargs):
        start_time = time.time()
        
        # Registrar evento de conexión
        await system_monitor.record_event(SystemEvent(
            event_type=EventType.CONNECTION,
            timestamp=datetime.now(),
            source=f"websocket_{func.__name__}",
            details={"endpoint": func.__name__, "client_ip": getattr(websocket.client, 'host', 'unknown')}
        ))
        
        try:
            # Ejecutar la función original
            result = await func(websocket, *args, **kwargs)
            return result
        except Exception as e:
            # Registrar error
            await system_monitor.record_event(SystemEvent(
                event_type=EventType.ERROR,
                timestamp=datetime.now(),
                source=f"websocket_{func.__name__}",
                details={"error": str(e), "error_type": type(e).__name__}
            ))
            raise
        finally:
            # Registrar desconexión
            duration = (time.time() - start_time) * 1000  # en milisegundos
            await system_monitor.record_event(SystemEvent(
                event_type=EventType.DISCONNECTION,
                timestamp=datetime.now(),
                source=f"websocket_{func.__name__}",
                details={"endpoint": func.__name__},
                duration_ms=duration
            ))
    
    return wrapper

# Exportar instancia global para uso en otros módulos
__all__ = ['system_monitor', 'SystemEvent', 'EventType', 'integrate_system_monitor', 'monitor_websocket_events']