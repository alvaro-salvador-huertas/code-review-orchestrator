def calcular_totales_por_asignatura(sesiones):
    totales = {}
    for sesion in sesiones:
        asignatura = sesion["asignatura"]
        totales[asignatura] = totales.get(asignatura, 0) + sesion["minutos"]
    return totales
