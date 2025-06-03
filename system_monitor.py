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
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from collections import deque
from enum import Enum

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
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
    
    Interfaz educativa que muestra:
    - Eventos en tiempo real
    - Gráficos de métricas del sistema
    - Topología de conexiones
    - Logs estructurados
    - Estadísticas de comunicación
    """
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🔍 Monitor de Sistema Distribuido - IoT Water Monitor</title>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: #0f0f23; color: #cccccc; min-height: 100vh;
            }
            .header { 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 20px; text-align: center; color: white;
            }
            .dashboard { padding: 20px; max-width: 1600px; margin: 0 auto; }
            .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }
            .grid-full { grid-column: 1 / -1; }
            .card { 
                background: #1a1a2e; border-radius: 10px; padding: 20px;
                border: 1px solid #333; box-shadow: 0 4px 8px rgba(0,0,0,0.3);
            }
            .card h3 { color: #4ade80; margin-bottom: 15px; display: flex; align-items: center; }
            .metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
            .metric-item { 
                background: #0f0f23; padding: 15px; border-radius: 8px; text-align: center;
                border: 1px solid #333;
            }
            .metric-value { font-size: 24px; font-weight: bold; color: #4ade80; margin: 5px 0; }
            .metric-label { font-size: 12px; opacity: 0.7; }
            .event-log { 
                background: #0f0f23; height: 300px; overflow-y: auto; padding: 10px;
                font-family: 'Courier New', monospace; font-size: 12px; border-radius: 8px;
                border: 1px solid #333;
            }
            .event-item { 
                padding: 5px; margin: 2px 0; border-radius: 4px; display: flex;
                align-items: center; border-left: 3px solid #4ade80;
            }
            .event-time { color: #60a5fa; margin-right: 10px; min-width: 80px; }
            .event-source { color: #fbbf24; margin-right: 10px; min-width: 120px; }
            .event-details { color: #cccccc; }
            .chart-container { height: 300px; background: #0f0f23; border-radius: 8px; border: 1px solid #333; }
            .status-indicator { 
                display: inline-block; width: 10px; height: 10px; border-radius: 50%;
                margin-right: 8px; animation: pulse 2s infinite;
            }
            .online { background: #4ade80; }
            .offline { background: #f87171; }
            @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
            .controls { margin: 15px 0; }
            .btn { 
                background: #4ade80; color: #0f0f23; border: none; padding: 8px 15px;
                border-radius: 5px; cursor: pointer; margin-right: 10px; font-size: 12px;
            }
            .btn:hover { background: #22c55e; }
            .topology { 
                background: #0f0f23; height: 200px; border-radius: 8px; border: 1px solid #333;
                display: flex; align-items: center; justify-content: center; position: relative;
                overflow: hidden;
            }
            .node { 
                width: 60px; height: 60px; border-radius: 50%; display: flex;
                align-items: center; justify-content: center; color: white; font-size: 12px;
                text-align: center; position: absolute; border: 2px solid;
            }
            .arduino-node { background: #f97316; border-color: #ea580c; top: 20px; left: 50px; }
            .server-node { background: #8b5cf6; border-color: #7c3aed; top: 50%; left: 50%; transform: translate(-50%, -50%); }
            .client-node { background: #06b6d4; border-color: #0891b2; top: 20px; right: 50px; }
            .admin-node { background: #ef4444; border-color: #dc2626; bottom: 20px; left: 50px; }
            .monitor-node { background: #10b981; border-color: #059669; bottom: 20px; right: 50px; }
            .connection-line { 
                position: absolute; height: 2px; background: #4ade80;
                transform-origin: left center; opacity: 0.6;
            }
            @media (max-width: 1200px) { .grid { grid-template-columns: 1fr; } }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🔍 Monitor de Sistema Distribuido</h1>
            <p>Visualización en Tiempo Real de Comunicación IoT - Arduino + FastAPI + WebSockets</p>
            <div>
                <span id="connectionStatus" class="status-indicator offline"></span>
                <span id="connectionText">Conectando al sistema...</span>
            </div>
        </div>
        
        <div class="dashboard">
            <div class="grid">
                <!-- Métricas del Sistema -->
                <div class="card">
                    <h3>📊 Métricas del Sistema</h3>
                    <div class="metric-grid" id="metricsGrid">
                        <div class="metric-item">
                            <div class="metric-label">CPU</div>
                            <div id="cpuMetric" class="metric-value">--</div>
                            <div class="metric-label">%</div>
                        </div>
                        <div class="metric-item">
                            <div class="metric-label">Memoria</div>
                            <div id="memoryMetric" class="metric-value">--</div>
                            <div class="metric-label">%</div>
                        </div>
                        <div class="metric-item">
                            <div class="metric-label">Conexiones</div>
                            <div id="connectionsMetric" class="metric-value">--</div>
                            <div class="metric-label">activas</div>
                        </div>
                        <div class="metric-item">
                            <div class="metric-label">Eventos/seg</div>
                            <div id="eventsPerSecMetric" class="metric-value">--</div>
                            <div class="metric-label">eps</div>
                        </div>
                    </div>
                </div>
                
                <!-- Topología de Red -->
                <div class="card">
                    <h3>🌐 Topología del Sistema</h3>
                    <div class="topology" id="networkTopology">
                        <div class="node arduino-node" title="Arduino Uno R4 WiFi">Arduino<br>Sensores</div>
                        <div class="node server-node" title="Servidor FastAPI">FastAPI<br>Server</div>
                        <div class="node client-node" title="Cliente Web">Web<br>Client</div>
                        <div class="node admin-node" title="Panel Admin">Admin<br>Panel</div>
                        <div class="node monitor-node" title="System Monitor">System<br>Monitor</div>
                    </div>
                </div>
            </div>
            
            <!-- Gráficos de Performance -->
            <div class="grid">
                <div class="card">
                    <h3>📈 CPU y Memoria</h3>
                    <div class="chart-container" id="performanceChart"></div>
                </div>
                <div class="card">
                    <h3>📡 Tráfico de Red</h3>
                    <div class="chart-container" id="networkChart"></div>
                </div>
            </div>
            
            <!-- Estadísticas de Comunicación -->
            <div class="card grid-full">
                <h3>📊 Estadísticas de Comunicación</h3>
                <div class="metric-grid">
                    <div class="metric-item">
                        <div class="metric-label">Total Conexiones</div>
                        <div id="totalConnections" class="metric-value">0</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">Total Desconexiones</div>
                        <div id="totalDisconnections" class="metric-value">0</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">Mensajes de Datos</div>
                        <div id="totalDataMessages" class="metric-value">0</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">Errores</div>
                        <div id="totalErrors" class="metric-value">0</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">Bytes Enviados</div>
                        <div id="bytesSent" class="metric-value">0</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">Bytes Recibidos</div>
                        <div id="bytesReceived" class="metric-value">0</div>
                    </div>
                </div>
            </div>
            
            <!-- Log de Eventos -->
            <div class="card grid-full">
                <h3>📝 Log de Eventos en Tiempo Real</h3>
                <div class="controls">
                    <button class="btn" onclick="clearEventLog()">🗑️ Limpiar Log</button>
                    <button class="btn" onclick="requestFullHistory()">📜 Historial Completo</button>
                    <label style="color: #cccccc;">
                        <input type="checkbox" id="autoScroll" checked> Auto-scroll
                    </label>
                </div>
                <div class="event-log" id="eventLog">
                    <div class="event-item">
                        <span class="event-time">--:--:--</span>
                        <span class="event-source">SYSTEM</span>
                        <span class="event-details">Conectando al monitor de sistema...</span>
                    </div>
                </div>
            </div>
        </div>

        <script>
            let socket = null;
            let performanceData = { time: [], cpu: [], memory: [] };
            let networkData = { time: [], bytesIn: [], bytesOut: [] };
            
            function connectWebSocket() {
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const wsUrl = `${protocol}//${window.location.host}/system-monitor/ws`;
                
                socket = new WebSocket(wsUrl);
                
                socket.onopen = function() {
                    document.getElementById('connectionStatus').className = 'status-indicator online';
                    document.getElementById('connectionText').textContent = 'Conectado al monitor';
                    addEventToLog('SYSTEM', 'Monitor conectado exitosamente', 'connection');
                };
                
                socket.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    
                    if (data.type === 'initial_state') {
                        handleInitialState(data);
                    } else if (data.type === 'system_event') {
                        handleSystemEvent(data.event);
                    } else if (data.type === 'system_metrics') {
                        handleSystemMetrics(data);
                    } else if (data.type === 'full_history') {
                        handleFullHistory(data);
                    }
                };
                
                socket.onclose = function() {
                    document.getElementById('connectionStatus').className = 'status-indicator offline';
                    document.getElementById('connectionText').textContent = 'Desconectado - Reconectando...';
                    addEventToLog('SYSTEM', 'Conexión perdida, reconectando...', 'error');
                    setTimeout(connectWebSocket, 3000);
                };
                
                socket.onerror = function(error) {
                    addEventToLog('SYSTEM', 'Error de conexión WebSocket', 'error');
                };
            }
            
            function handleInitialState(data) {
                // Actualizar estadísticas iniciales
                if (data.counters) {
                    updateCounters(data.counters);
                }
                
                // Mostrar eventos recientes
                if (data.recent_events) {
                    data.recent_events.forEach(event => {
                        addEventToLog(event.source, JSON.stringify(event.details), event.event_type);
                    });
                }
                
                // Inicializar gráficos con datos históricos
                if (data.metrics_history) {
                    data.metrics_history.forEach(metric => {
                        updateCharts(metric);
                    });
                }
                
                addEventToLog('SYSTEM', 'Estado inicial cargado', 'connection');
            }
            
            function handleSystemEvent(event) {
                addEventToLog(event.source, JSON.stringify(event.details), event.event_type);
            }
            
            function handleSystemMetrics(data) {
                // Actualizar métricas en tiempo real
                if (data.metrics) {
                    document.getElementById('cpuMetric').textContent = data.metrics.cpu_percent;
                    document.getElementById('memoryMetric').textContent = data.metrics.memory_percent;
                    document.getElementById('connectionsMetric').textContent = data.metrics.active_connections;
                    document.getElementById('eventsPerSecMetric').textContent = data.metrics.events_per_second;
                    
                    updateCharts(data.metrics);
                }
                
                // Actualizar contadores
                if (data.counters) {
                    updateCounters(data.counters);
                }
            }
            
            function updateCounters(counters) {
                document.getElementById('totalConnections').textContent = counters.total_connections;
                document.getElementById('totalDisconnections').textContent = counters.total_disconnections;
                document.getElementById('totalDataMessages').textContent = counters.total_data_messages;
                document.getElementById('totalErrors').textContent = counters.total_errors;
                document.getElementById('bytesSent').textContent = formatBytes(counters.bytes_sent);
                document.getElementById('bytesReceived').textContent = formatBytes(counters.bytes_received);
            }
            
            function updateCharts(metrics) {
                const time = new Date(metrics.timestamp).toLocaleTimeString();
                
                // Actualizar datos de performance
                performanceData.time.push(time);
                performanceData.cpu.push(metrics.cpu_percent);
                performanceData.memory.push(metrics.memory_percent);
                
                // Mantener solo los últimos 50 puntos
                if (performanceData.time.length > 50) {
                    performanceData.time.shift();
                    performanceData.cpu.shift();
                    performanceData.memory.shift();
                }
                
                // Actualizar gráfico de performance
                Plotly.react('performanceChart', [
                    { x: performanceData.time, y: performanceData.cpu, name: 'CPU %', type: 'scatter', line: {color: '#f97316'} },
                    { x: performanceData.time, y: performanceData.memory, name: 'Memoria %', type: 'scatter', line: {color: '#8b5cf6'} }
                ], {
                    plot_bgcolor: '#0f0f23', paper_bgcolor: '#0f0f23',
                    font: {color: '#cccccc'}, showlegend: true,
                    xaxis: {showgrid: false, color: '#666'}, yaxis: {showgrid: true, gridcolor: '#333', range: [0, 100]}
                }, {displayModeBar: false});
                
                // Actualizar datos de red si están disponibles
                if (metrics.network_io) {
                    networkData.time.push(time);
                    networkData.bytesIn.push(metrics.network_io.bytes_recv);
                    networkData.bytesOut.push(metrics.network_io.bytes_sent);
                    
                    if (networkData.time.length > 50) {
                        networkData.time.shift();
                        networkData.bytesIn.shift();
                        networkData.bytesOut.shift();
                    }
                    
                    // Actualizar gráfico de red
                    Plotly.react('networkChart', [
                        { x: networkData.time, y: networkData.bytesIn, name: 'Bytes In', type: 'scatter', line: {color: '#4ade80'} },
                        { x: networkData.time, y: networkData.bytesOut, name: 'Bytes Out', type: 'scatter', line: {color: '#06b6d4'} }
                    ], {
                        plot_bgcolor: '#0f0f23', paper_bgcolor: '#0f0f23',
                        font: {color: '#cccccc'}, showlegend: true,
                        xaxis: {showgrid: false, color: '#666'}, yaxis: {showgrid: true, gridcolor: '#333'}
                    }, {displayModeBar: false});
                }
            }
            
            function addEventToLog(source, details, eventType = 'info') {
                const log = document.getElementById('eventLog');
                const timestamp = new Date().toLocaleTimeString();
                
                const eventItem = document.createElement('div');
                eventItem.className = 'event-item';
                
                const eventTypeColors = {
                    'connection': '#4ade80',
                    'disconnection': '#f87171',
                    'data_received': '#60a5fa',
                    'data_sent': '#8b5cf6',
                    'error': '#f87171',
                    'system_metric': '#fbbf24'
                };
                
                eventItem.style.borderLeftColor = eventTypeColors[eventType] || '#4ade80';
                
                eventItem.innerHTML = `
                    <span class="event-time">${timestamp}</span>
                    <span class="event-source">${source.toUpperCase()}</span>
                    <span class="event-details">${details}</span>
                `;
                
                log.appendChild(eventItem);
                
                // Auto-scroll si está habilitado
                if (document.getElementById('autoScroll').checked) {
                    log.scrollTop = log.scrollHeight;
                }
                
                // Limitar a 500 entradas
                while (log.children.length > 500) {
                    log.removeChild(log.firstChild);
                }
            }
            
            function clearEventLog() {
                document.getElementById('eventLog').innerHTML = '';
                addEventToLog('SYSTEM', 'Log de eventos limpiado', 'info');
            }
            
            function requestFullHistory() {
                if (socket && socket.readyState === WebSocket.OPEN) {
                    socket.send(JSON.stringify({action: 'get_full_history'}));
                }
            }
            
            function formatBytes(bytes) {
                if (bytes === 0) return '0 B';
                const k = 1024;
                const sizes = ['B', 'KB', 'MB', 'GB'];
                const i = Math.floor(Math.log(bytes) / Math.log(k));
                return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
            }
            
            // Inicializar cuando se carga la página
            window.onload = function() {
                connectWebSocket();
                
                // Inicializar gráficos vacíos
                Plotly.newPlot('performanceChart', [], {
                    plot_bgcolor: '#0f0f23', paper_bgcolor: '#0f0f23',
                    font: {color: '#cccccc'}
                }, {displayModeBar: false});
                
                Plotly.newPlot('networkChart', [], {
                    plot_bgcolor: '#0f0f23', paper_bgcolor: '#0f0f23',
                    font: {color: '#cccccc'}
                }, {displayModeBar: false});
            };
        </script>
    </body>
    </html>
    """)

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