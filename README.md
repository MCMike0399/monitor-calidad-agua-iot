# 🌊 Monitor IoT de Calidad de Agua - Sistema Didáctico Completo

## 📋 Descripción del Proyecto

Este proyecto implementa un **sistema completo de monitoreo de calidad de agua** usando tecnologías IoT modernas, diseñado específicamente para fines **educativos y demostrativos** en cursos de sistemas embebidos y sistemas distribuidos.

### 🎯 Objetivos Educativos

- **Sistemas Distribuidos**: Demostrar comunicación entre múltiples componentes
- **WebSockets**: Implementar comunicación bidireccional en tiempo real
- **IoT Architecture**: Mostrar arquitectura típica de dispositivos IoT
- **Docker Containers**: Containerización y despliegue en la nube
- **Real-time Data**: Procesamiento y visualización de datos en tiempo real
- **System Monitoring**: Monitoreo avanzado de sistemas distribuidos

## 🏗️ Arquitectura del Sistema

```
┌─────────────────┐    HTTP POST     ┌──────────────────┐    WebSocket     ┌─────────────────┐
│   Arduino UNO   │ ──────────────▶  │   FastAPI        │ ──────────────▶  │   Dashboard     │
│   R4 WiFi       │                  │   Servidor       │                  │   Web           │
│                 │                  │                  │                  │                 │
│ • Sensor pH     │                  │ • HTTP API       │                  │ • Gráficos      │
│ • Turbidez      │                  │ • WebSockets     │                  │ • Tiempo Real   │
│ • Conductividad │                  │ • State Mgmt     │                  │ • Alertas       │
└─────────────────┘                  └──────────────────┘                  └─────────────────┘
                                              │
                                              │ WebSocket
                                              ▼
                                      ┌──────────────────┐
                                      │  Admin Panel     │
                                      │                  │
                                      │ • Control Mock   │
                                      │ • Estadísticas   │
                                      │ • Configuración  │
                                      └──────────────────┘
                                              │
                                              │ WebSocket
                                              ▼
                                      ┌──────────────────┐
                                      │ System Monitor   │
                                      │                  │
                                      │ • Métricas CPU   │
                                      │ • Eventos Red    │
                                      │ • Logs Tiempo    │
                                      │   Real           │
                                      └──────────────────┘
```

## 📁 Estructura del Proyecto

```
proyecto-monitor-agua/
├── 📄 main.py                    # Servidor principal FastAPI
├── 📄 water_monitor.py           # Sistema de WebSockets y monitoreo
├── 📄 system_monitor.py          # Monitor avanzado de sistema distribuido
├── 📄 logging_config.py          # Configuración de logging
├── 📄 requirements.txt           # Dependencias Python
├── 📄 dockerfile                # Configuración Docker
├── 📄 .dockerignore             # Archivos a ignorar en Docker
├── 📄 .gitignore                # Archivos a ignorar en Git
├── 📄 .env                       # Variables de entorno (crear)
├── 📁 static/                   # Archivos estáticos web
│   ├── 📄 ws_client.html        # Dashboard principal de monitoreo
│   └── 📄 ws_client.js          # JavaScript del cliente
└── 📄 main.c                    # Código Arduino (sensores)
```

## 🚀 Instalación y Configuración

### 1. Prerrequisitos

- **Python 3.11+**
- **Docker** (opcional, para containerización)
- **Arduino IDE** (para programar el Arduino)
- **Arduino Uno R4 WiFi**
- **Sensores**: pH, turbidez, conductividad

### 2. Configuración del Entorno Python

```bash
# Clonar el repositorio
git clone <tu-repositorio>
cd proyecto-monitor-agua

# Crear entorno virtual
python -m venv myenv
source myenv/bin/activate  # En Windows: myenv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

### 3. Configuración de Variables de Entorno

Crear archivo `.env` en la raíz del proyecto:

```env
# Configuración del servidor
HOST=0.0.0.0
PORT=8000
DEBUG=True
ENVIRONMENT=development

# Configuración de logging
LOG_LEVEL=INFO
```

### 4. Ejecución del Sistema

#### Modo Desarrollo (Local)

```bash
# Ejecutar servidor con recarga automática
python main.py

# O usando uvicorn directamente
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

#### Modo Producción (Docker)

```bash
# Construir imagen Docker
docker build -t water-monitor .

# Ejecutar contenedor
docker run -p 8000:8000 water-monitor

# O usando docker-compose (crear docker-compose.yml)
docker-compose up -d
```

## 🌐 Interfaces Web Disponibles

Una vez que el servidor esté ejecutándose, accede a:

| URL | Descripción | Propósito Educativo |
|-----|-------------|-------------------|
| `http://localhost:8000/` | **Página Principal** | Introducción al sistema |
| `http://localhost:8000/water-monitor` | **Dashboard de Monitoreo** | Visualización de datos en tiempo real |
| `http://localhost:8000/admin-dashboard` | **Panel de Administración** | Control del sistema y configuración |
| `http://localhost:8000/system-monitor` | **Monitor de Sistema** | Análisis profundo de comunicaciones |
| `http://localhost:8000/docs` | **Documentación API** | Swagger UI automático |
| `http://localhost:8000/redoc` | **Documentación ReDoc** | Documentación alternativa |

## 🔧 Configuración del Arduino

### 1. Preparar el Arduino Uno R4 WiFi

```cpp
// Archivo: arduino_secrets.h (crear este archivo)
#define SECRET_SSID "TU_WIFI_SSID"
#define SECRET_PASS "TU_WIFI_PASSWORD"
```

### 2. Conexiones de Sensores

| Sensor | Pin Arduino | Descripción |
|--------|-------------|-------------|
| **Turbidez** | A0 | Sensor de turbidez (NTU) |
| **pH** | A1 | Sensor de pH (0-14) |
| **Conductividad** | A2 | Sensor de conductividad (μS/cm) |

### 3. Programar el Arduino

1. Abrir `main.c` en Arduino IDE
2. Crear archivo `arduino_secrets.h` con credenciales WiFi
3. Instalar bibliotecas necesarias:
   - `WiFiS3` (incluida con Arduino R4)
   - `ArduinoJson`
4. Compilar y subir al Arduino

## 📊 Funcionalidades Educativas

### 1. **Dashboard de Monitoreo Principal**
- 📈 Gráficos en tiempo real con Plotly.js
- 🚨 Sistema de alertas basado en umbrales
- 📱 Diseño responsive
- 🔄 Actualizaciones automáticas cada 3 segundos

### 2. **Panel de Administración**
- 🎛️ Control de modo (datos reales vs simulados)
- 📊 Estadísticas del sistema
- 🔍 Monitoreo de conexiones activas
- ⚙️ Configuración en tiempo real

### 3. **Monitor de Sistema Distribuido**
- 📡 Visualización de eventos de red
- 💻 Métricas de CPU y memoria
- 📋 Log de eventos en tiempo real
- 🌐 Topología de red interactiva
- 📈 Gráficos de performance

### 4. **Simulación de Datos**
- 🎭 Modo mock para testing sin hardware
- 🔄 Generación automática de datos realistas
- 📊 Patrones de datos configurables
- 🧪 Perfecto para demos y desarrollo

## 🔍 Conceptos Técnicos Demostrados

### 1. **WebSockets vs HTTP**

**HTTP (Arduino → Servidor):**
```python
# Endpoint optimizado para IoT
@app.post("/water-monitor/publish")
async def arduino_http_endpoint(request: Request):
    # Procesamiento mínimo para conservar batería del Arduino
    # Respuesta rápida y eficiente
```

**WebSocket (Servidor ↔ Cliente Web):**
```python
# Comunicación bidireccional en tiempo real
@app.websocket("/water-monitor")
async def monitor_websocket_endpoint(websocket: WebSocket):
    # Envío automático de datos cuando hay actualizaciones
    # Manejo de múltiples clientes simultáneos
```

### 2. **Patrón Publisher/Subscriber**
```python
# Estado global compartido
class WaterMonitorState:
    async def update_reading(self, reading: SensorReading):
        # Actualizar datos
        self.latest_reading = reading
        # Notificar a TODOS los suscriptores
        await self._broadcast_to_clients()
```

### 3. **Manejo de Estado Distribuido**
```python
# Sincronización entre múltiples clientes
water_state = WaterMonitorState()  # Singleton
# Todos los clientes ven los mismos datos
# Estado consistente en todo el sistema
```

### 4. **Monitoreo de Sistema en Tiempo Real**
```python
# Métricas de sistema automáticas
async def collect_system_metrics(self):
    cpu_percent = psutil.cpu_percent()
    memory = psutil.virtual_memory()
    # Broadcast a todos los monitores
```

## 🧪 Casos de Uso Educativos

### Para Profesores:

1. **Demostración de WebSockets:**
   - Abrir múltiples ventanas del dashboard
   - Mostrar cómo los cambios se propagan instantáneamente
   - Explicar diferencias con polling HTTP tradicional

2. **Sistemas Distribuidos:**
   - Usar el monitor de sistema para mostrar comunicación
   - Demostrar tolerancia a fallos desconectando clientes
   - Mostrar escalabilidad con múltiples conexiones

3. **IoT Architecture:**
   - Arduino como edge device con limitaciones
   - Servidor como gateway/broker
   - Clientes web como interfaces de usuario

4. **Performance Monitoring:**
   - Observar métricas de CPU/memoria en tiempo real
   - Analizar patrones de tráfico de red
   - Correlacionar eventos con performance

### Para Estudiantes:

1. **Desarrollo Incremental:**
   - Empezar con datos mock
   - Agregar Arduino gradualmente
   - Expandir con nuevos sensores

2. **Debugging Avanzado:**
   - Usar logs estructurados
   - Monitorear eventos en tiempo real
   - Analizar patrones de comunicación

3. **Optimización:**
   - Medir latencia de comunicación
   - Optimizar frecuencia de actualizaciones
   - Balancear precisión vs performance

## 🛠️ Desarrollo y Extensión

### Agregar Nuevos Sensores

1. **En el Arduino:**
```cpp
// Agregar nueva lectura
float temperatura = leer_sensor_temperatura(A3);

// Incluir en JSON
doc["TEMP"] = temperatura;
```

2. **En el Servidor:**
```python
# Extender modelo de datos
@dataclass
class SensorReading:
    turbidity: float
    ph: float
    conductivity: float
    temperature: float  # Nuevo campo
```

3. **En el Frontend:**
```javascript
// Agregar nuevo gráfico
const tempTrace = {
    x: chartData.time,
    y: chartData.temperature,
    name: 'Temperatura',
    type: 'scatter'
};
```

### Personalización de Umbrales

```python
# En water_monitor.py - Personalizar rangos
THRESHOLDS = {
    "PH": {"ideal": {"min": 6.5, "max": 7.5}},
    "T": {"ideal": {"max": 10}},
    # Agregar nuevos parámetros
}
```

## 🚀 Despliegue en Producción

### AWS EC2 + Docker

```bash
# En la instancia EC2
sudo yum update -y
sudo yum install docker -y
sudo service docker start

# Clonar y ejecutar
git clone <repo>
cd proyecto-monitor-agua
sudo docker build -t water-monitor .
sudo docker run -d -p 80:8000 water-monitor
```

### Variables de Entorno para Producción

```env
HOST=0.0.0.0
PORT=8000
DEBUG=False
ENVIRONMENT=production
LOG_LEVEL=WARNING
```

## 📚 Referencias y Recursos Adicionales

### Documentación Técnica:
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [WebSockets RFC 6455](https://tools.ietf.org/html/rfc6455)
- [Arduino Uno R4 WiFi Guide](https://docs.arduino.cc/hardware/uno-r4-wifi)

### Conceptos Teóricos:
- Sistemas Distribuidos: Tanenbaum & van Steen
- Real-time Systems: Liu
- IoT Architecture Patterns: Microsoft Azure

### Librerías Utilizadas:
- `fastapi`: Framework web moderno y rápido
- `uvicorn`: Servidor ASGI de alto rendimiento  
- `websockets`: Implementación WebSocket para Python
- `plotly.js`: Visualización interactiva de datos
- `psutil`: Métricas de sistema multiplataforma

## 🤝 Contribución y Mejoras

### Ideas para Extensiones:

1. **Base de Datos:**
   - Agregar PostgreSQL/MongoDB para persistencia
   - Histórico de datos a largo plazo
   - Análisis de tendencias

2. **Machine Learning:**
   - Predicción de calidad de agua
   - Detección de anomalías
   - Modelos de forecasting

3. **Escalabilidad:**
   - Múltiples dispositivos Arduino
   - Load balancing
   - Microservicios

4. **Seguridad:**
   - Autenticación JWT
   - HTTPS/WSS
   - Rate limiting

5. **Mobile App:**
   - React Native / Flutter
   - Notificaciones push
   - Modo offline

## 📞 Soporte y Contacto

Para dudas, sugerencias o reportar problemas:

- 📧 Email: [tu-email@universidad.edu]
- 📚 Wiki del Proyecto: [link-a-wiki]
- 🐛 Issues: [link-a-github-issues]

---

## 📄 Licencia

Este proyecto está desarrollado con fines educativos para el curso de Sistemas Embebidos.

**Uso permitido:**
- ✅ Fines educativos y académicos
- ✅ Modificación y extensión
- ✅ Distribución en contextos educativos

**Atribución:**
Por favor, menciona este proyecto si lo usas como base para otros trabajos académicos.

---

*Desarrollado con ❤️ para la educación en Sistemas Embebidos e IoT*