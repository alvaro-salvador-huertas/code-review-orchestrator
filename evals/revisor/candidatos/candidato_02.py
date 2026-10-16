def calcular_totales_por_asignatura(sesiones):
    totales = {}
    nombres = {}
    for sesion in sesiones:
        asignatura = sesion["asignatura"]
        clave = nombres.setdefault(asignatura.lower(), asignatura)
        totales[clave] = totales.get(clave, 0) + sesion["minutos"]
    return totales
