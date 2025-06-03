const MAX_DATA_POINTS = 50;
const chartData = {
    time: [],
    turbidity: [],
    ph: [],
    conductivity: []
};

// Umbrales actualizados para alertas y estados basados en valores reales de sensores
const THRESHOLDS = {
    PH: {
        ideal: { min: 6.5, max: 7.5 },
        good: { min: 6.0, max: 8.0 },
        acceptable: { min: 5.0, max: 9.0 },
        warning: { min: 3, max: 11 },
        danger: { min: 2, max: 12 }
    },
    T: {
        ideal: { max: 10 },
        good: { max: 50 },
        acceptable: { max: 100 },
        warning: { max: 500 },
        danger: { max: 800 }
    },
    C: {
        ideal: { max: 300 },
        good: { max: 600 },
        acceptable: { max: 900 },
        warning: { max: 1200 },
        danger: { max: 1400 }
    }
};

// FUNCIÓN AUXILIAR: Validar y sanitizar valores numéricos
function validateAndSanitizeValue(value, defaultValue = 0, min = null, max = null) {
    // Convertir a número si es string
    let numValue = typeof value === 'string' ? parseFloat(value) : value;
    
    // Verificar si es un número válido
    if (isNaN(numValue) || !isFinite(numValue)) {
        console.warn(`⚠️ Valor inválido detectado: ${value}, usando valor por defecto: ${defaultValue}`);
        return defaultValue;
    }
    
    // Aplicar límites si se especifican
    if (min !== null && numValue < min) {
        console.warn(`⚠️ Valor ${numValue} por debajo del mínimo ${min}, ajustando`);
        return min;
    }
    
    if (max !== null && numValue > max) {
        console.warn(`⚠️ Valor ${numValue} por encima del máximo ${max}, ajustando`);
        return max;
    }
    
    return numValue;
}

// FUNCIÓN AUXILIAR: Validar estructura de datos recibidos
function validateDataStructure(data) {
    if (!data || typeof data !== 'object') {
        console.error('💥 Datos recibidos no son un objeto válido:', data);
        return false;
    }
    
    const requiredFields = ['T', 'PH', 'C'];
    const missingFields = requiredFields.filter(field => !(field in data));
    
    if (missingFields.length > 0) {
        console.error(`💥 Campos faltantes en los datos: ${missingFields.join(', ')}`);
        return false;
    }
    
    return true;
}

// Inicializar gráficos separados
function initCharts() {
    // Configuración común para todos los gráficos
    const config = {
        responsive: true,
        displayModeBar: false,
        staticPlot: true,
        scrollZoom: false,
        doubleClick: false
    };

    // Gráfico de Turbidez
    const turbidityTrace = {
        x: chartData.time,
        y: chartData.turbidity,
        name: 'Turbidez',
        type: 'scatter',
        line: {color: '#3498db', width: 2}
    };

    const turbidityLayout = {
        title: 'Turbidez en Tiempo Real',
        margin: { l: 50, r: 20, t: 50, b: 80 },
        xaxis: {
            title: { text: 'Tiempo' },
            showgrid: true,
            fixedrange: true
        },
        yaxis: {
            title: 'Turbidez (NTU)',
            titlefont: {color: '#3498db'},
            tickfont: {color: '#3498db'},
            range: [0, 1000],
            fixedrange: true
        }
    };

    Plotly.newPlot('turbidityChart', [turbidityTrace], turbidityLayout, config);

    // Gráfico de pH
    const phTrace = {
        x: chartData.time,
        y: chartData.ph,
        name: 'pH',
        type: 'scatter',
        line: {color: '#e74c3c', width: 2}
    };

    const phLayout = {
        title: 'pH en Tiempo Real',
        margin: { l: 50, r: 20, t: 50, b: 80 },
        xaxis: {
            title: { text: 'Tiempo' },
            showgrid: true,
            fixedrange: true
        },
        yaxis: {
            title: 'pH',
            titlefont: {color: '#e74c3c'},
            tickfont: {color: '#e74c3c'},
            range: [0, 14],
            fixedrange: true
        }
    };

    Plotly.newPlot('phChart', [phTrace], phLayout, config);

    // Gráfico de Conductividad
    const conductivityTrace = {
        x: chartData.time,
        y: chartData.conductivity,
        name: 'Conductividad',
        type: 'scatter',
        line: {color: '#2ecc71', width: 2}
    };

    const conductivityLayout = {
        title: 'Conductividad en Tiempo Real',
        margin: { l: 60, r: 20, t: 50, b: 80 },
        xaxis: {
            title: { text: 'Tiempo', standoff: 20 },
            showgrid: true,
            fixedrange: true
        },
        yaxis: {
            title: 'Conductividad (μS/cm)',
            titlefont: {color: '#2ecc71'},
            tickfont: {color: '#2ecc71'},
            range: [0, 1500],
            fixedrange: true
        }
    };

    Plotly.newPlot('conductivityChart', [conductivityTrace], conductivityLayout, config);
}

// Función para actualizar gráficos con nuevos datos (CON VALIDACIÓN)
function updateCharts(data) {
    const now = new Date();
    const timeStr = now.toLocaleTimeString();
    
    // VALIDAR Y SANITIZAR datos antes de agregar a los gráficos
    const turbidity = validateAndSanitizeValue(data.T, 25.0, 0, 1000);
    const ph = validateAndSanitizeValue(data.PH, 7.0, 0, 14);
    const conductivity = validateAndSanitizeValue(data.C, 300.0, 0, 1500);
    
    // Añadir nuevo punto de datos
    chartData.time.push(timeStr);
    chartData.turbidity.push(turbidity);
    chartData.ph.push(ph);
    chartData.conductivity.push(conductivity);
    
    // Limitar el número de puntos
    if (chartData.time.length > MAX_DATA_POINTS) {
        chartData.time.shift();
        chartData.turbidity.shift();
        chartData.ph.shift();
        chartData.conductivity.shift();
    }
    
    // Actualizar cada gráfico individualmente
    try {
        Plotly.update('turbidityChart', {
            x: [chartData.time],
            y: [chartData.turbidity]
        }, {}, [0]);
        
        Plotly.update('phChart', {
            x: [chartData.time],
            y: [chartData.ph]
        }, {}, [0]);
        
        Plotly.update('conductivityChart', {
            x: [chartData.time],
            y: [chartData.conductivity]
        }, {}, [0]);
    } catch (error) {
        console.error('💥 Error actualizando gráficos:', error);
    }
}

// Formatear valores para mostrar (CON VALIDACIÓN ROBUSTA)
function formatValues(data) {
    const turbidity = validateAndSanitizeValue(data.T, 25.0, 0, 1000);
    const ph = validateAndSanitizeValue(data.PH, 7.0, 0, 14);
    const conductivity = validateAndSanitizeValue(data.C, 300.0, 0, 1500);
    
    return {
        T: turbidity.toFixed(2),
        PH: ph.toFixed(2),
        C: Math.round(conductivity).toString()
    };
}

// Evaluar el estado del pH y devolver mensaje y clase CSS
function evaluatePh(ph) {
    const value = validateAndSanitizeValue(ph, 7.0, 0, 14);
    
    if (value >= THRESHOLDS.PH.ideal.min && value <= THRESHOLDS.PH.ideal.max) {
        return {
            status: "Ideal para la mayoría de organismos acuáticos",
            class: "alert-success"
        };
    } else if (value >= THRESHOLDS.PH.good.min && value <= THRESHOLDS.PH.good.max) {
        return {
            status: "Buen estado - Rango aceptable",
            class: "alert-success"
        };
    } else if (value >= THRESHOLDS.PH.acceptable.min && value <= THRESHOLDS.PH.acceptable.max) {
        return {
            status: "Aceptable - Monitorear",
            class: "alert-info"
        };
    } else if (value < THRESHOLDS.PH.warning.min && value >= THRESHOLDS.PH.danger.min) {
        return {
            status: "Advertencia: pH muy ácido",
            class: "alert-warning"
        };
    } else if (value > THRESHOLDS.PH.warning.max && value <= THRESHOLDS.PH.danger.max) {
        return {
            status: "Advertencia: pH muy alcalino",
            class: "alert-warning"
        };
    } else if (value < THRESHOLDS.PH.danger.min) {
        return {
            status: "PELIGRO: pH extremadamente ácido",
            class: "alert-danger"
        };
    } else if (value > THRESHOLDS.PH.danger.max) {
        return {
            status: "PELIGRO: pH extremadamente alcalino",
            class: "alert-danger"
        };
    } else {
        return {
            status: "Estado indeterminado",
            class: "alert-info"
        };
    }
}

// Evaluar el estado de la turbidez
function evaluateTurbidity(turbidity) {
    const value = validateAndSanitizeValue(turbidity, 25.0, 0, 1000);
    
    if (value <= THRESHOLDS.T.ideal.max) {
        return {
            status: "Excelente claridad del agua",
            class: "alert-success"
        };
    } else if (value <= THRESHOLDS.T.good.max) {
        return {
            status: "Buena claridad - Rango aceptable",
            class: "alert-success"
        };
    } else if (value <= THRESHOLDS.T.acceptable.max) {
        return {
            status: "Agua ligeramente turbia - Aceptable",
            class: "alert-info"
        };
    } else if (value <= THRESHOLDS.T.warning.max) {
        return {
            status: "Advertencia: Agua turbia",
            class: "alert-warning"
        };
    } else if (value > THRESHOLDS.T.danger.max) {
        return {
            status: "PELIGRO: Turbidez muy elevada",
            class: "alert-danger"
        };
    } else {
        return {
            status: "Estado indeterminado",
            class: "alert-info"
        };
    }
}

// Evaluar el estado de la conductividad
function evaluateConductivity(conductivity) {
    const value = validateAndSanitizeValue(conductivity, 300.0, 0, 1500);
    
    if (value <= THRESHOLDS.C.ideal.max) {
        return {
            status: "Excelente - Agua muy pura",
            class: "alert-success"
        };
    } else if (value <= THRESHOLDS.C.good.max) {
        return {
            status: "Buena calidad - Rango normal",
            class: "alert-success"
        };
    } else if (value <= THRESHOLDS.C.acceptable.max) {
        return {
            status: "Aceptable - Monitorear",
            class: "alert-info"
        };
    } else if (value <= THRESHOLDS.C.warning.max) {
        return {
            status: "Advertencia: Conductividad elevada",
            class: "alert-warning"
        };
    } else if (value > THRESHOLDS.C.danger.max) {
        return {
            status: "PELIGRO: Conductividad muy alta",
            class: "alert-danger"
        };
    } else {
        return {
            status: "Estado indeterminado",
            class: "alert-info"
        };
    }
}

// Comprobar valores contra umbrales y actualizar alertas principales
function checkThresholds(data) {
    const alertPanel = document.getElementById('alertPanel');
    const alertMessage = document.getElementById('alertMessage');
    
    // VALIDAR datos antes de usar
    const ph = validateAndSanitizeValue(data.PH, 7.0, 0, 14);
    const turbidity = validateAndSanitizeValue(data.T, 25.0, 0, 1000);
    const conductivity = validateAndSanitizeValue(data.C, 300.0, 0, 1500);
    
    // Actualizar indicadores de estado individuales
    const phEvaluation = evaluatePh(ph);
    const turbidityEvaluation = evaluateTurbidity(turbidity);
    const conductivityEvaluation = evaluateConductivity(conductivity);
    
    // Actualizar clase y mensaje de estado para cada sensor
    const phStatus = document.getElementById('phStatus');
    if (phStatus) {
        phStatus.textContent = phEvaluation.status;
        phStatus.className = `sensor-status ${phEvaluation.class}`;
    }
    
    const turbidityStatus = document.getElementById('turbidityStatus');
    if (turbidityStatus) {
        turbidityStatus.textContent = turbidityEvaluation.status;
        turbidityStatus.className = `sensor-status ${turbidityEvaluation.class}`;
    }
    
    const conductivityStatus = document.getElementById('conductivityStatus');
    if (conductivityStatus) {
        conductivityStatus.textContent = conductivityEvaluation.status;
        conductivityStatus.className = `sensor-status ${conductivityEvaluation.class}`;
    }
    
    // Si todos los valores están en rangos aceptables
    if (ph >= THRESHOLDS.PH.acceptable.min && ph <= THRESHOLDS.PH.acceptable.max &&
        turbidity <= THRESHOLDS.T.acceptable.max &&
        conductivity <= THRESHOLDS.C.acceptable.max) {
        
        // Si alguno está en rango ideal, mostrar mensaje positivo
        if ((ph >= THRESHOLDS.PH.ideal.min && ph <= THRESHOLDS.PH.ideal.max) ||
            turbidity <= THRESHOLDS.T.ideal.max ||
            conductivity <= THRESHOLDS.C.ideal.max) {
            
            if (alertPanel) {
                alertPanel.style.display = 'block';
                alertPanel.className = 'alert alert-success';
                if (alertMessage) {
                    alertMessage.textContent = 'Todos los parámetros se encuentran en rangos aceptables o ideales.';
                }
            }
            return;
        }
    }
    
    // Si llegamos aquí, no hay alertas principales activas
    if (alertPanel) {
        alertPanel.style.display = 'none';
    }
}

// Actualizar interfaz con nuevos valores (CON VALIDACIÓN COMPLETA)
function updateInterface(data) {
    try {
        // VALIDAR estructura de datos antes de procesar
        if (!validateDataStructure(data)) {
            console.error('💥 Datos recibidos tienen estructura inválida, ignorando actualización');
            return;
        }
        
        // Solo formatear los valores para mostrar (con validación robusta)
        const formattedData = formatValues(data);
        
        // Actualizar indicadores con verificación de existencia de elementos
        const turbidityElement = document.getElementById('turbidity');
        const phElement = document.getElementById('ph');
        const conductivityElement = document.getElementById('conductivity');
        
        if (turbidityElement) turbidityElement.textContent = formattedData.T;
        if (phElement) phElement.textContent = formattedData.PH;
        if (conductivityElement) conductivityElement.textContent = formattedData.C;
        
        // Comprobar valores contra umbrales
        checkThresholds(formattedData);
        
        // Actualizar timestamp
        const now = new Date();
        const lastUpdateElement = document.getElementById('lastUpdate');
        if (lastUpdateElement) {
            lastUpdateElement.textContent = `Última actualización: ${now.toLocaleTimeString()}`;
        }
        
        // Actualizar gráficos con datos validados
        updateCharts(data);
        
        console.log('✅ Interfaz actualizada exitosamente con datos validados');
        
    } catch (error) {
        console.error('💥 Error actualizando interfaz:', error);
        console.error('📊 Datos problemáticos:', data);
    }
}

// Conectar WebSocket
function connectWebSocket() {
    const statusElement = document.getElementById('connection');
    
    if (statusElement) {
        statusElement.textContent = 'Conectando...';
    }
    
    const ws = new WebSocket('ws://' + window.location.host + '/water-monitor');
    
    ws.onopen = function() {
        if (statusElement) {
            statusElement.textContent = 'Conectado';
            statusElement.className = 'status connected';
        }
        console.log('✅ WebSocket conectado exitosamente');
    };
    
    ws.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            console.log('📊 Datos recibidos del servidor:', data);
            
            // VALIDACIÓN ADICIONAL: Verificar que tenemos un objeto válido
            if (data && typeof data === 'object') {
                updateInterface(data);
            } else {
                console.warn('⚠️ Datos recibidos no tienen formato esperado:', data);
            }
            
        } catch (parseError) {
            console.error('💥 Error parseando datos JSON del WebSocket:', parseError);
            console.error('📄 Datos crudos recibidos:', event.data);
        }
    };
    
    ws.onclose = function(event) {
        if (statusElement) {
            statusElement.textContent = 'Desconectado - Reconectando...';
            statusElement.className = 'status disconnected';
        }
        
        console.log(`🔌 WebSocket cerrado (código: ${event.code}). Reconectando en 2 segundos...`);
        
        // Reconectar después de 2 segundos
        setTimeout(connectWebSocket, 2000);
    };
    
    ws.onerror = function(err) {
        console.error('💥 Error en WebSocket:', err);
        
        if (statusElement) {
            statusElement.textContent = 'Error de conexión';
            statusElement.className = 'status disconnected';
        }
        
        // Forzar cierre para activar reconexión
        ws.close();
    };
}

// Inicializar cuando la página cargue
window.addEventListener('load', function() {
    console.log('🚀 Iniciando cliente de monitoreo de agua...');
    
    try {
        // Inicializar gráficos
        initCharts();
        console.log('📊 Gráficos inicializados exitosamente');
        
        // Conectar WebSocket
        connectWebSocket();
        console.log('🔗 Conexión WebSocket iniciada');
        
        // Manejar el redimensionamiento de la ventana
        window.addEventListener('resize', function() {
            try {
                Plotly.Plots.resize('turbidityChart');
                Plotly.Plots.resize('phChart');
                Plotly.Plots.resize('conductivityChart');
            } catch (resizeError) {
                console.warn('⚠️ Error redimensionando gráficos:', resizeError);
            }
        });
        
        console.log('✅ Cliente de monitoreo inicializado completamente');
        
    } catch (initError) {
        console.error('💥 Error crítico inicializando cliente:', initError);
    }
});