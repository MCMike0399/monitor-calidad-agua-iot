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

// Definición de pines ADC (sin cambio)
#define TURBIDITY_PIN A0
#define PH_PIN A1
#define CONDUCT_PIN A2

#define USE_KEEP_ALIVE true
const unsigned long RECONNECT_INTERVAL = 120000; // 2 minutos
unsigned long lastConnectionTime = 0;
bool isConnected = false;

// *** CONFIGURACIÓN DEL SERVIDOR  ***
const char *server_host = "18.101.239.100";
const int server_port = 8000;
const char *server_path = "/water-monitor/publish";

// Intervalo de actualización más conservador para pruebas
const unsigned long UPDATE_INTERVAL = 1000; 

// Variables para monitoreo de conexión
unsigned long lastSuccessfulSend = 0;
int consecutiveTimeouts = 0;
const int MAX_CONSECUTIVE_TIMEOUTS = 3; // Después de 3 timeouts, reconectar

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
    // Verificar conexión WiFi periódicamente
    if (WiFi.status() != WL_CONNECTED)
    {
        Serial.println("⚠️ Conexión WiFi perdida - Reconectando...");
        conectar_wifi();
        
        // Reset estado de conexión HTTP
        isConnected = false;
        if (client.connected()) {
            client.stop();
        }
        
        return; // Salir temprano si no hay WiFi
    }

    // Verificar estado de salud de la conexión HTTP
    unsigned long currentTime = millis();
    
    // Si han pasado muchos timeouts consecutivos, forzar reconexión
    if (consecutiveTimeouts >= MAX_CONSECUTIVE_TIMEOUTS) {
        Serial.println("🔄 Demasiados timeouts - forzando reconexión completa...");
        
        if (client.connected()) {
            client.stop();
        }
        isConnected = false;
        consecutiveTimeouts = 0;
        lastConnectionTime = 0; // Forzar nueva conexión
        
        // Pausa breve antes de reintentar
        delay(2000);
        return;
    }

    //  Manejo de keep-alive 
    if (USE_KEEP_ALIVE && isConnected)
    {
        // Verificar si la conexión sigue activa
        if (!client.connected()) {
            Serial.println("🔌 Conexión keep-alive perdida - marcando para reconexión");
            isConnected = false;
            lastConnectionTime = currentTime;
        }
        // Renovar conexión periódicamente para evitar timeouts del servidor
        else if (currentTime - lastConnectionTime >= RECONNECT_INTERVAL) {
            Serial.println("🔄 Renovando conexión keep-alive periódicamente...");
            client.stop();
            isConnected = false;
            lastConnectionTime = currentTime;
        }
    }

    // Verificar si es tiempo de enviar una actualización
    if (currentTime - lastUpdateTime >= UPDATE_INTERVAL)
    {
        lastUpdateTime = currentTime;
        
        // Monitoreo de salud de conexión
        unsigned long timeSinceLastSuccess = currentTime - lastSuccessfulSend;
        
        // Advertencia si hace mucho que no se envía exitosamente
        if (lastSuccessfulSend > 0 && timeSinceLastSuccess > 30000) { // 30 segundos
            static unsigned long lastWarning = 0;
            if (currentTime - lastWarning > 60000) { // Advertir cada minuto
                lastWarning = currentTime;
                Serial.print("⚠️ Sin envío exitoso por ");
                Serial.print(timeSinceLastSuccess / 1000);
                Serial.println(" segundos");
            }
        }
        
        enviar_datos_sensores();
    }
    
    // Pequeña pausa para no saturar el CPU
    delay(10);
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
    doc["T"] = round(turbidez * 100) / 100.0;  // Turbidez con 2 decimales
    doc["PH"] = round(ph * 100) / 100.0;       // pH con 2 decimales
    doc["C"] = round(salinidad * 100) / 100.0; // Conductividad con 2 decimales

    String json;
    serializeJson(doc, json);

    bool connection_success = false;

    // Si no hay conexión activa o ha pasado tiempo desde la última conexión
    if (!isConnected || (millis() - lastConnectionTime) > RECONNECT_INTERVAL)
    {
        // Cerrar conexión anterior si existe
        if (client.connected())
        {
            client.stop();
        }
        isConnected = false;

        Serial.print("🔗 (Re)conectando al servidor ");
        Serial.print(server_host);
        Serial.print(":");
        Serial.print(server_port);
        Serial.print("... ");

        // Timeout generoso para conexión inicial
        unsigned long connect_start = millis();
        while (!client.connect(server_host, server_port) && (millis() - connect_start) < 5000)
        {
            delay(100); // Pequeña pausa entre intentos
        }

        if (client.connected())
        {
            isConnected = true;
            connection_success = true;
            lastConnectionTime = millis();
            Serial.println("✅ CONECTADO");
        }
        else
        {
            Serial.println("❌ FALLO DE CONEXIÓN");
            Serial.println("💡 Verificar que el servidor Python esté ejecutándose");
            return;
        }
    }
    else
    {
        connection_success = client.connected();
    }

    if (!connection_success)
    {
        Serial.println("❌ Sin conexión válida al servidor");
        isConnected = false;
        return;
    }

    // Construir petición HTTP optimizada con headers mejorados
    client.print("POST ");
    client.print(server_path);
    client.println(" HTTP/1.1");
    client.print("Host: ");
    client.println(server_host);
    client.println("User-Agent: Arduino-UnoR4WiFi/1.0");
    client.println("Connection: keep-alive");
    client.println("Content-Type: application/json");
    client.print("Content-Length: ");
    client.println(json.length());
    client.println(); // Línea en blanco crucial para HTTP
    client.print(json);
    client.flush(); // Forzar transmisión de datos

    // Procesamiento de respuesta con timeout extendido
    unsigned long timeout_start = millis();
    bool headerEnded = false;
    bool responseReceived = false;
    String statusLine = "";
    int responseCode = 0;

    // Timeout aumentado a 5 segundos para respuesta
    while (client.connected() && (millis() - timeout_start < 5000))
    {
        if (client.available())
        {
            String line = client.readStringUntil('\n');
            line.trim(); // Remover espacios y \r

            // Leer la primera línea para obtener el status code
            if (line.startsWith("HTTP/1.1") && statusLine.isEmpty())
            {
                statusLine = line;
                responseReceived = true;

                // Extraer código de respuesta
                int spaceIndex = line.indexOf(' ');
                if (spaceIndex > 0)
                {
                    int secondSpaceIndex = line.indexOf(' ', spaceIndex + 1);
                    if (secondSpaceIndex > 0)
                    {
                        responseCode = line.substring(spaceIndex + 1, secondSpaceIndex).toInt();
                    }
                }

                // Log basado en código de respuesta
                if (responseCode == 200)
                {
                    // Solo mostrar confirmación cada 30 segundos para requests exitosos
                    static unsigned long lastSuccessLog = 0;
                    if (millis() - lastSuccessLog > 30000)
                    {
                        lastSuccessLog = millis();
                        Serial.println("✅ Datos enviados exitosamente al servidor Python");
                    }
                }
                else if (responseCode == 202)
                {
                    static unsigned long lastMockLog = 0;
                    if (millis() - lastMockLog > 60000)
                    { // Log cada minuto en modo mock
                        lastMockLog = millis();
                        Serial.println("🎭 Servidor en modo simulado - datos del Arduino ignorados");
                    }
                }
                else if (responseCode >= 400)
                {
                    Serial.print("❌ Error del servidor: ");
                    Serial.println(responseCode);
                }
            }

            // Detectar fin de headers HTTP
            if (line.length() == 0)
            {
                headerEnded = true;
                break; // No necesitamos leer el body para este caso
            }
        }

        //  Pequeña pausa para no saturar el CPU
        delay(1);
    }

    //  Verificación de timeout más detallada
    if (!responseReceived)
    {
        unsigned long elapsed = millis() - timeout_start;
        Serial.print("⚠️ No se recibió respuesta del servidor (timeout ");
        Serial.print(elapsed);
        Serial.println("ms)");

        // Si el timeout es muy largo, probablemente hay un problema de red
        if (elapsed >= 4000)
        {
            Serial.println("🔌 Timeout muy largo - cerrando conexión para reintentar");
            client.stop();
            isConnected = false;
        }
    }
    else
    {
        // Actualizar tiempo de última comunicación exitosa
        lastConnectionTime = millis();
    }

    // Limpiar buffer
    int bytesCleared = 0;
    while (client.available() && bytesCleared < 512)
    { // Límite para evitar bucle infinito
        client.read();
        bytesCleared++;
    }

    // Manejo de keep-alive 
    if (USE_KEEP_ALIVE)
    {
        // Verificar que la conexión sigue activa
        if (!client.connected())
        {
            Serial.println("🔌 Conexión perdida - marcando para reconexión");
            isConnected = false;
        }
        else
        {
            // Actualizar tiempo de última actividad
            lastConnectionTime = millis();
        }
    }
    else
    {
        // Sin keep-alive, cerrar conexión
        client.stop();
        isConnected = false;
    }
    // contadores de exito y errores basado en el resultado
    if (responseReceived && responseCode == 200) {
        // Envío exitoso
        lastSuccessfulSend = millis();
        consecutiveTimeouts = 0; // Reset contador de timeouts
        
        // Log de debug cada 5 minutos para mostrar estadísticas
        static unsigned long lastStatsLog = 0;
        if (millis() - lastStatsLog > 300000) { // 5 minutos
            lastStatsLog = millis();
            Serial.println("📈 Estadísticas de conexión:");
            Serial.print("   ✅ Último envío exitoso: hace ");
            Serial.print((millis() - lastSuccessfulSend) / 1000);
            Serial.println(" segundos");
            Serial.print("   🔗 Conexión keep-alive: ");
            Serial.println(isConnected ? "ACTIVA" : "INACTIVA");
            Serial.print("   📡 Estado WiFi: ");
            Serial.println(WiFi.status() == WL_CONNECTED ? "CONECTADO" : "DESCONECTADO");
        }
    } else if (!responseReceived) {
        // Timeout ocurrido
        consecutiveTimeouts++;
        Serial.print("⚠️ Timeout #");
        Serial.print(consecutiveTimeouts);
        Serial.print(" de ");
        Serial.println(MAX_CONSECUTIVE_TIMEOUTS);
        
        if (consecutiveTimeouts >= MAX_CONSECUTIVE_TIMEOUTS) {
            Serial.println("🚨 Demasiados timeouts - se forzará reconexión en próximo ciclo");
        }
    } else if (responseCode >= 400) {
        // Error del servidor - no contar como timeout pero sí como problema
        Serial.print("🚨 Error del servidor ");
        Serial.print(responseCode);
        Serial.println(" - no es problema de timeout");
        
        // Reset timeouts ya que el servidor sí respondió
        consecutiveTimeouts = 0;
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
    // Simula un sensor de turbidez donde 0V = agua muy turbia, 5.0V = agua clara
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