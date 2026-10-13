def calcular_totales_por_asignatura(sesiones):
    """Versión inicial del caso, con un defecto intencionado de acumulación."""
    totales = {}
    for sesion in sesiones:
        # Defecto intencionado: sobrescribe en lugar de acumular los minutos.
        totales[sesion["asignatura"]] = sesion["minutos"]
    return totales
