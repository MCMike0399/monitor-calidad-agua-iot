import logging
import colorlog
from datetime import datetime

def setup_logging():
    """
    Configura el sistema de logging para toda la aplicación.
    Solo logging a consola, sin archivos - AWS CloudWatch maneja la persistencia.

    Returns:
        logger: El logger raíz configurado
    """
    # Obtener logger raíz
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Eliminar handlers existentes para evitar duplicados
    if root_logger.handlers:
        for handler in root_logger.handlers:
            root_logger.removeHandler(handler)

    # Formato detallado para los logs
    log_format = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Formato con colores para la consola
    console_formatter = colorlog.ColoredFormatter(
        "%(log_color)s" + log_format,
        datefmt=date_format,
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red,bg_white",
        },
    )

    # Handler SOLO para consola con colores
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)

    # Log de inicio
    root_logger.info("=" * 70)
    root_logger.info(
        f"INICIO DE SESIÓN MONITOR AGUA TIEMPO REAL - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    root_logger.info("Logging configurado: SOLO CONSOLA (AWS CloudWatch maneja persistencia)")
    root_logger.info("=" * 70)

    return root_logger


def get_logger(name: str):
    """
    Obtiene un logger con el nombre especificado.

    Args:
        name: Nombre del logger (generalmente __name__)

    Returns:
        Un logger configurado
    """
    return logging.getLogger(name)
