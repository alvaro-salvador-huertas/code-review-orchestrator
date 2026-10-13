def clasificar_ejecucion(codigo_salida, respuesta, tiempo_agotado=False):
    if tiempo_agotado:
        return "tiempo_agotado"
    if codigo_salida is None or codigo_salida != 0:
        return "fallo_ejecucion"
    return "completada"
