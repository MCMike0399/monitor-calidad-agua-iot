/*
    Arduino Uno R4 WiFi - Sensor HTTP Client
    Actualizado para servidor Python en 18.100.40.23:8000

    Lee datos de sensores ADC (turbidez, pH, conductividad)
    y los envía a un servidor mediante peticiones HTTP POST.
*/

#include "WiFiS3.h"
#include <ArduinoJson.h>
#include "arduino_secrets.h"

// Definiciones para WiFi de arduino_secrets.h
char ssid[] = SECRET_SSID;
char pass[] = SECRET_PASS;

// Definición de pines ADC
#define TURBIDITY_PIN A0
#define PH_PIN A1
#define CONDUCT_PIN A2

#define USE_KEEP_ALIVE true
const unsigned long RECONNECT_INTERVAL = 60000; // 1 minute
unsigned long lastConnectionTime = 0;
bool isConnected = false;

// *** ACTUALIZADO: Configuración del servidor Python ***
const char *server_host = "18.100.40.23";  // Nueva IP del servidor
const int server_port = 8000;              // Puerto del servidor Python
const char *server_path = "/water-monitor/publish";  // Endpoint correcto

// Intervalo de actualización (milisegundos)
const unsigned long UPDATE_INTERVAL = 1000;

// Cliente WiFi
WiFiClient client;

// Variables globales
unsigned long lastUpdateTime = 0;
int status = WL_IDLE_STATUS;

// Prototipos de funciones
uint16_t leer_adc(uint8_t pin);
float convertir_turbidez(uint16_t raw);
float convertir_ph(uint16_t raw);
float convertir_salinidad(uint16_t raw);
void conectar_wifi();
void enviar_datos_sensores();

void setup()
{
    // Inicializar serial
    Serial.begin(9600);
    while (!Serial)
    {
        ; // Esperar a que el puerto serial se conecte
    }

    Serial.println("=== Monitor de Agua IoT - Arduino Uno R4 WiFi ===");
    Serial.print("Servidor destino: ");
    Serial.print(server_host);
    Serial.print(":");
    Serial.println(server_port);
    Serial.print("Endpoint: ");
    Serial.println(server_path);
    Serial.println("===============================================");

    // Configurar ADC para resolución de 12 bits
    analogReadResolution(12);

    // Conectar a WiFi
    conectar_wifi();
}

void loop()
{
    // Verificar conexión WiFi
    if (WiFi.status() != WL_CONNECTED)
    {
        Serial.println("⚠️ Reconectando a WiFi...");
        conectar_wifi();
        return;
    }

    // Check server connection periodically
    if (USE_KEEP_ALIVE && isConnected)
    {
        unsigned long currentTime = millis();
        if (currentTime - lastConnectionTime >= RECONNECT_INTERVAL)
        {
            client.stop();
            isConnected = false;
            lastConnectionTime = currentTime;
            Serial.println("🔄 Renovando conexión keep-alive...");
        }
    }

    // Verificar si es tiempo de enviar una actualización
    unsigned long currentTime = millis();
    if (currentTime - lastUpdateTime >= UPDATE_INTERVAL)
    {
        lastUpdateTime = currentTime;
        enviar_datos_sensores();
    }
}

void conectar_wifi()
{
    // Verificar el módulo WiFi
    if (WiFi.status() == WL_NO_MODULE)
    {
        Serial.println("❌ ¡Fallo en comunicación con módulo WiFi!");
        while (true)
            ; // No continuar
    }

    String fv = WiFi.firmwareVersion();
    if (fv < WIFI_FIRMWARE_LATEST_VERSION)
    {
        Serial.println("⚠️ Por favor actualice el firmware WiFi");
    }

    // Intentar conectar a la red WiFi
    while (status != WL_CONNECTED)
    {
        Serial.print("🔗 Intentando conectar a SSID: ");
        Serial.println(ssid);

        // Para redes abiertas (sin contraseña)
        if (strlen(pass) == 0)
        {
            status = WiFi.begin(ssid);
        }
        else
        {
            // Conectar a red WPA/WPA2
            status = WiFi.begin(ssid, pass);
        }

        // Esperar para la conexión
        delay(5000);
    }

    Serial.println("✅ Conectado a WiFi exitosamente!");
    Serial.print("📶 SSID: ");
    Serial.println(WiFi.SSID());
    IPAddress ip = WiFi.localIP();
    Serial.print("🌐 Dirección IP local: ");
    Serial.println(ip);
    Serial.print("📡 Servidor objetivo: ");
    Serial.print(server_host);
    Serial.print(":");
    Serial.println(server_port);
}

void enviar_datos_sensores()
{
    // Leer sensores
    uint16_t turbidez_raw = leer_adc(TURBIDITY_PIN);
    uint16_t ph_raw = leer_adc(PH_PIN);
    uint16_t conductividad_raw = leer_adc(CONDUCT_PIN);

    // Convertir valores
    float turbidez = convertir_turbidez(turbidez_raw);
    float ph = convertir_ph(ph_raw);
    float salinidad = convertir_salinidad(conductividad_raw);

    // Logging reducido para mejor performance
    static int print_counter = 0;
    if (++print_counter >= 10) // Cada 10 lecturas (10 segundos)
    {
        print_counter = 0;
        Serial.print("📊 Datos leídos - Turbidez: ");
        Serial.print(turbidez, 2);
        Serial.print(" NTU, pH: ");
        Serial.print(ph, 2);
        Serial.print(", Conductividad: ");
        Serial.print(salinidad, 2);
        Serial.println(" μS/cm");
    }

    // Crear JSON con formato exacto esperado por el servidor Python
    StaticJsonDocument<200> doc;
    doc["T"] = round(turbidez * 100) / 100.0;    // Turbidez con 2 decimales
    doc["PH"] = round(ph * 100) / 100.0;         // pH con 2 decimales  
    doc["C"] = round(salinidad * 100) / 100.0;   // Conductividad con 2 decimales

    String json;
    serializeJson(doc, json);

    // Gestionar conexión al servidor
    if (!isConnected)
    {
        Serial.print("🔗 Conectando al servidor ");
        Serial.print(server_host);
        Serial.print(":");
        Serial.print(server_port);
        Serial.print("... ");
        
        if (!client.connect(server_host, server_port))
        {
            Serial.println("❌ FALLO");
            Serial.println("💡 Verificar que el servidor Python esté ejecutándose");
            return;
        }
        isConnected = true;
        Serial.println("✅ CONECTADO");
        Serial.println("📡 Conexión keep-alive establecida");
    }

    // Construir petición HTTP POST optimizada
    client.print("POST ");
    client.print(server_path);
    client.println(" HTTP/1.1");
    client.print("Host: ");
    client.println(server_host);
    client.println(USE_KEEP_ALIVE ? "Connection: keep-alive" : "Connection: close");
    client.println("Content-Type: application/json");
    client.print("Content-Length: ");
    client.println(json.length());
    client.println(); // Línea en blanco crucial para HTTP
    client.print(json);
    client.flush(); // Forzar transmisión de datos

    // Procesamiento mínimo de respuesta para mejor performance
    unsigned long timeout = millis();
    bool headerEnded = false;
    bool responseReceived = false;

    while (client.connected() && (millis() - timeout < 2000)) // 2 segundos timeout
    {
        if (client.available())
        {
            String line = client.readStringUntil('\n');
            
            // Buscar código de respuesta HTTP
            if (line.startsWith("HTTP/1.1"))
            {
                responseReceived = true;
                if (line.indexOf("200") > 0)
                {
                    // Solo mostrar confirmación cada 30 segundos
                    static unsigned long lastSuccessLog = 0;
                    if (millis() - lastSuccessLog > 30000)
                    {
                        lastSuccessLog = millis();
                        Serial.println("✅ Datos enviados exitosamente al servidor Python");
                    }
                }
                else if (line.indexOf("400") > 0)
                {
                    Serial.println("❌ Error 400: Datos inválidos enviados al servidor");
                }
                else if (line.indexOf("500") > 0)
                {
                    Serial.println("❌ Error 500: Error interno del servidor Python");
                }
            }
            
            // Detectar fin de headers
            if (line == "\r")
            {
                headerEnded = true;
                break;
            }
        }
    }

    if (!responseReceived)
    {
        Serial.println("⚠️ No se recibió respuesta del servidor (timeout)");
    }

    // Limpiar cualquier dato restante en el buffer
    while (client.available())
    {
        client.read();
    }

    // Manejar conexión basado en configuración keep-alive
    if (!USE_KEEP_ALIVE)
    {
        client.stop();
        isConnected = false;
    }
    else
    {
        lastConnectionTime = millis();
    }
}

// Función para leer ADC con promedio para reducir ruido
uint16_t leer_adc(uint8_t pin)
{
    uint32_t sum = 0;
    const int samples = 10;

    for (int i = 0; i < samples; i++)
    {
        sum += analogRead(pin);
        delay(2); // Pequeña pausa entre lecturas
    }

    return sum / samples;
}

// Función para convertir valor raw de turbidez (invertido para simular sensor real)
float convertir_turbidez(uint16_t raw)
{
    // Simula un sensor de turbidez donde 0V = agua muy turbia, 3.3V = agua clara
    return 1000.0 * (1.0 - (float)raw / 4095.0);
}

// Función para convertir valor raw de pH (escala 0-14)
float convertir_ph(uint16_t raw)
{
    // Mapea 0-4095 ADC a escala pH 0-14
    return 14.0 * ((float)raw / 4095.0);
}

// Función para convertir valor raw de conductividad/salinidad
float convertir_salinidad(uint16_t raw)
{
    // Mapea 0-4095 ADC a rango de conductividad 0-1500 μS/cm
    return 1500.0 * ((float)raw / 4095.0);
}