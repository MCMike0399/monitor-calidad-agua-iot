/*
    Arduino Uno R4 WiFi - Sensor HTTP Client

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

// Configuración del servidor
const char *server_host = "51.94.71.97";
const int server_port = 8000;
const char *server_path = "/water-monitor/publish";

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
        Serial.println("Reconectando a WiFi...");
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
        Serial.println("¡Fallo en comunicación con módulo WiFi!");
        while (true)
            ; // No continuar
    }

    String fv = WiFi.firmwareVersion();
    if (fv < WIFI_FIRMWARE_LATEST_VERSION)
    {
        Serial.println("Por favor actualice el firmware");
    }

    // Intentar conectar a la red WiFi
    while (status != WL_CONNECTED)
    {
        Serial.print("Intentando conectar a SSID: ");
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

    Serial.println("Conectado a WiFi");
    Serial.print("SSID: ");
    Serial.println(WiFi.SSID());
    IPAddress ip = WiFi.localIP();
    Serial.print("Dirección IP: ");
    Serial.println(ip);
}

void enviar_datos_sensores()
{
    // Read sensors (keep existing code)
    uint16_t turbidez_raw = leer_adc(TURBIDITY_PIN);
    uint16_t ph_raw = leer_adc(PH_PIN);
    uint16_t conductividad_raw = leer_adc(CONDUCT_PIN);

    // Convert values (keep existing code)
    float turbidez = convertir_turbidez(turbidez_raw);
    float ph = convertir_ph(ph_raw);
    float salinidad = convertir_salinidad(conductividad_raw);

    // Reduce serial output frequency
    static int print_counter = 0;
    if (++print_counter >= 5)
    {
        print_counter = 0;
        Serial.print("Datos: T:");
        Serial.print(turbidez, 2);
        Serial.print(";PH:");
        Serial.print(ph, 2);
        Serial.print(";C:");
        Serial.println(salinidad, 2);
    }

    StaticJsonDocument<200> doc;
    doc["T"] = round(turbidez * 100) / 100.0;
    doc["PH"] = round(ph * 100) / 100.0;
    doc["C"] = round(salinidad * 100) / 100.0;

    String json;
    serializeJson(doc, json);

    // Manage connection
    if (!isConnected)
    {
        if (!client.connect(server_host, server_port))
        {
            Serial.println("Fallo en conexión al servidor");
            return;
        }
        isConnected = true;
        Serial.println("Conectado al servidor");
    }

    // Minimized HTTP request
    client.print("POST ");
    client.print(server_path);
    client.println(" HTTP/1.1");
    client.print("Host: ");
    client.println(server_host);
    client.println(USE_KEEP_ALIVE ? "Connection: keep-alive" : "Connection: close");
    client.println("Content-Type: application/json");
    client.print("Content-Length: ");
    client.println(json.length());
    client.println(); // Blank line is crucial
    client.print(json);
    client.flush(); // Force data transmission

    // Minimal response processing
    unsigned long timeout = millis();
    bool headerEnded = false;

    while (client.connected() && (millis() - timeout < 1000))
    {
        if (client.available())
        {
            String line = client.readStringUntil('\n');
            if (line == "\r")
            {
                headerEnded = true;
                break;
            }
        }
    }

    // Drain any remaining response data
    while (client.available())
    {
        client.read();
    }

    // Handle connection based on keep-alive setting
    if (!USE_KEEP_ALIVE)
    {
        client.stop();
        isConnected = false;
    }
}

// Función para leer ADC con promedio
uint16_t leer_adc(uint8_t pin)
{
    uint32_t sum = 0;
    const int samples = 10;

    for (int i = 0; i < samples; i++)
    {
        sum += analogRead(pin);
        delay(2);
    }

    return sum / samples;
}

// Función para convertir valor raw de turbidez (invertido)
float convertir_turbidez(uint16_t raw)
{
    return 1000.0 * (1.0 - (float)raw / 4095.0);
}

// Función para convertir valor raw de pH
float convertir_ph(uint16_t raw)
{
    return 14.0 * ((float)raw / 4095.0);
}

// Función para convertir valor raw de salinidad
float convertir_salinidad(uint16_t raw)
{
    return 1500.0 * ((float)raw / 4095.0);
}
