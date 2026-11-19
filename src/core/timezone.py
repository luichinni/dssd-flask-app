from datetime import datetime, timedelta, timezone

ARGENTINA_TZ = timezone(timedelta(hours=-3), name="ART")


def ahora_ar() -> datetime:
    """Devuelve la fecha y hora actual en zona horaria de Argentina (UTC-3)."""
    return datetime.now(ARGENTINA_TZ)


def a_argentina(fecha: datetime | None) -> datetime | None:
    """Normaliza un datetime a zona horaria de Argentina (UTC-3)."""
    if fecha is None:
        return None
    if fecha.tzinfo is None:
        return fecha.replace(tzinfo=ARGENTINA_TZ)
    return fecha.astimezone(ARGENTINA_TZ)


def formatear_ar(fecha: datetime | None, fmt: str = "%d/%m/%Y %H:%M ART") -> str:
    """Formatea un datetime en hora de Argentina."""
    normalizada = a_argentina(fecha)
    if normalizada is None:
        return ""
    return normalizada.strftime(fmt)
