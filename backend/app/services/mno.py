"""МНО (места накопления отходов): список+фильтры, карточка, создание, синхронизация.

ВАЖНО про синхронизацию с ФГИС: реальной интеграции с ФГИС УТКО НЕТ. sync_all/sync_one —
ЛОКАЛЬНАЯ ЗАГЛУШКА: помечают МНО как synced и проставляют placeholder-fgis_id вида
"STUB-xxxxxxxx". Никакие внешние запросы не выполняются. Когда появится боевая интеграция —
заглушка заменяется реальным клиентом ФГИС.
"""

import math
import uuid
from datetime import datetime, timezone

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.errors import NotFoundError, ValidationError
from ..models import Incident, Mno, Region
from ..schemas.base import Paginated
from ..schemas.mno import (
    MnoDetail,
    MnoFormPoint,
    MnoFormPointsResponse,
    MnoListItem,
    MnoPoint,
    MnoPointsResponse,
    MnoSyncResult,
    MnoVolunteerCreate,
)
from .audit import audit
from .geo import parse_bbox, parse_latlon
# Конвейер фото волонтёрского МНО (валидация/декод/ресайз/запись на диск) — общий
# с фото инцидентов. Импорт на уровне модуля безопасен: services/intake.py НЕ
# импортирует services/mno.py, цикла нет.
from .intake import process_mno_photos

# Максимум точек, отдаваемых карте за КАДР (bbox) или глобально (карта не грузит весь реестр).
MAX_POINTS = 2000

# Потолок точек МНО для ПУБЛИЧНОЙ формы (карта выбора площадки): меньше админ-карты —
# неавторизованный эндпоинт, кадр формы обычно узкий (позиция пользователя/улица).
FORM_MAX_POINTS = 500

# sort-ключ из API → колонка модели. region сортируется по коду субъекта.
_SORT_COLUMNS = {
    "name": Mno.name,
    "reg": Mno.reg,
    "region": Mno.region_code,
    "city": Mno.city,
    "address": Mno.address,
    "coords": Mno.coords,
}


def _search_clause(search: str):
    """ilike-OR по name/reg/city/address/coords/fgis_id."""
    term = f"%{search.strip()}%"
    return or_(
        Mno.name.ilike(term),
        Mno.reg.ilike(term),
        Mno.city.ilike(term),
        Mno.address.ilike(term),
        Mno.coords.ilike(term),
        Mno.fgis_id.ilike(term),
    )


def _filters(
    search: str | None,
    region: str | None,
    synced: bool | None,
    bbox: str | None = None,
) -> list:
    filters: list = []
    if search and search.strip():
        filters.append(_search_clause(search))
    if region and region.strip():
        filters.append(Mno.region_code == region.strip())
    if synced is not None:
        filters.append(Mno.synced.is_(synced))
    # bbox («minLat,minLon,maxLat,maxLon») — видимая область карты/гео: отдаём только МНО
    # текущего кадра (числовые lat/lon по индексу ix_mno_lat_lon), как в list_points.
    # Невалидный/пустой bbox игнорируется (список ведёт себя как раньше).
    box = parse_bbox(bbox)
    if box is not None:
        min_lat, min_lon, max_lat, max_lon = box
        filters.append(Mno.lat.is_not(None))
        filters.append(Mno.lat.between(min_lat, max_lat))
        filters.append(Mno.lon.between(min_lon, max_lon))
    return filters


async def _region_names(session: AsyncSession) -> dict[str, str]:
    """code → name по справочнику регионов (для region_name в выдаче)."""
    result = await session.execute(select(Region.code, Region.name))
    return {code: name for code, name in result.all()}


async def _incident_counts(session: AsyncSession, mno_ids: list) -> dict:
    """{mno_id: живой COUNT инцидентов} по ссылке incidents.mno_id, одним запросом.

    Счётчик обращений у МНО считается НА ЧТЕНИЕ (без дрейфа/инкрементов): для набора
    МНО из списка/детали берём COUNT(Incident.id) GROUP BY Incident.mno_id. МНО без
    обращений в словарь не попадают → у них 0 (см. .get(id, 0)). Пустой набор → без
    запроса к БД.
    """
    if not mno_ids:
        return {}
    stmt = (
        select(Incident.mno_id, func.count(Incident.id))
        .where(Incident.mno_id.in_(mno_ids))
        .group_by(Incident.mno_id)
    )
    result = await session.execute(stmt)
    return {mno_id: cnt for mno_id, cnt in result.all()}


def _to_list_item(
    m: Mno, region_names: dict[str, str], incidents: int | None = None
) -> MnoListItem:
    """Строка/карточка МНО. incidents=None → статичное поле модели (create/sync);
    заданный incidents ПЕРЕКРЫВАЕТ его живым COUNT (списки/деталь на чтение)."""
    return MnoListItem(
        id=m.id,
        reg=m.reg,
        name=m.name,
        region_code=m.region_code,
        region_name=region_names.get(m.region_code, m.region_code),
        city=m.city,
        address=m.address,
        coords=m.coords,
        source=m.source,
        fgis_id=m.fgis_id,
        synced=m.synced,
        sync_date=m.sync_date,
        incidents=m.incidents if incidents is None else incidents,
    )


async def _count(
    session: AsyncSession,
    *,
    search: str | None,
    region: str | None,
    synced: bool | None,
    bbox: str | None = None,
) -> int:
    """COUNT(*) по тем же фильтрам, что и список (для пагинации/карты)."""
    filters = _filters(search, region, synced, bbox)
    stmt = select(func.count(Mno.id))
    if filters:
        stmt = stmt.where(*filters)
    return (await session.execute(stmt)).scalar_one()


async def _query(
    session: AsyncSession,
    *,
    search: str | None,
    region: str | None,
    synced: bool | None,
    sort: str,
    order: str,
    offset: int | None = None,
    limit: int | None = None,
    bbox: str | None = None,
) -> list[Mno]:
    """Ядро фильтра/сортировки: сырые строки Mno.

    offset/limit опциональны — None означает «весь набор» (используется экспортом).
    """
    filters = _filters(search, region, synced, bbox)
    stmt = select(Mno)
    if filters:
        stmt = stmt.where(*filters)
    sort_col = _SORT_COLUMNS.get(sort, Mno.name)
    direction = asc if order == "asc" else desc
    stmt = stmt.order_by(direction(sort_col), direction(Mno.id))
    if offset is not None:
        stmt = stmt.offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_mno(
    session: AsyncSession,
    *,
    search: str | None = None,
    region: str | None = None,
    synced: bool | None = None,
    sort: str = "name",
    order: str = "asc",
    page: int = 1,
    page_size: int = 100,
    bbox: str | None = None,
) -> Paginated[MnoListItem]:
    """Пагинированный реестр МНО с фильтрами region/synced/search + bbox + сортировкой.

    bbox («minLat,minLon,maxLat,maxLon») — видимая область карты/гео: список отдаёт только
    МНО текущего кадра (как /mno/points), чтобы приложение получало ближайшие площадки, а не
    весь реестр. Без bbox — прежнее поведение (весь отфильтрованный реестр постранично).
    """
    total = await _count(
        session, search=search, region=region, synced=synced, bbox=bbox
    )
    rows = await _query(
        session,
        search=search,
        region=region,
        synced=synced,
        sort=sort,
        order=order,
        offset=(page - 1) * page_size,
        limit=page_size,
        bbox=bbox,
    )
    region_names = await _region_names(session)
    counts = await _incident_counts(session, [m.id for m in rows])
    items = [_to_list_item(m, region_names, counts.get(m.id, 0)) for m in rows]
    pages = math.ceil(total / page_size) if total > 0 else 0
    return Paginated[MnoListItem](
        items=items, total=total, page=page, page_size=page_size, pages=pages
    )


async def list_by_volunteer(
    session: AsyncSession,
    volunteer_id: uuid.UUID,
    *,
    page: int = 1,
    page_size: int = 50,
) -> Paginated[MnoDetail]:
    """«Мои МНО»: площадки, добавленные этим волонтёром из приложения.

    Фильтр — Mno.volunteer_id == volunteer_id (мягкая привязка авторства). Свежие
    первыми (created_at DESC, вторичный ключ id для стабильности). МНО с
    volunteer_id=NULL (ФГИС/ручные/старые) сюда НЕ попадают. Для каждой строки собираем
    полную карточку MnoDetail (живой COUNT обращений + comment/photo_urls), как в get_mno.
    Пагинация (COUNT + offset/limit) зеркалит list_mno.
    """
    total = (
        await session.execute(
            select(func.count(Mno.id)).where(Mno.volunteer_id == volunteer_id)
        )
    ).scalar_one()

    stmt = (
        select(Mno)
        .where(Mno.volunteer_id == volunteer_id)
        .order_by(desc(Mno.created_at), desc(Mno.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = list((await session.execute(stmt)).scalars().all())

    region_names = await _region_names(session)
    counts = await _incident_counts(session, [m.id for m in rows])
    items = [
        MnoDetail(
            **_to_list_item(m, region_names, counts.get(m.id, 0)).model_dump(),
            comment=m.comment,
            photo_urls=(m.photo_urls or []),
        )
        for m in rows
    ]
    pages = math.ceil(total / page_size) if total > 0 else 0
    return Paginated[MnoDetail](
        items=items, total=total, page=page, page_size=page_size, pages=pages
    )


async def list_for_export(
    session: AsyncSession,
    *,
    search: str | None = None,
    region: str | None = None,
    synced: bool | None = None,
    sort: str = "name",
    order: str = "asc",
) -> list[MnoListItem]:
    """Полный отфильтрованный реестр для .xlsx (БЕЗ пагинации — весь набор)."""
    rows = await _query(
        session, search=search, region=region, synced=synced, sort=sort, order=order
    )
    region_names = await _region_names(session)
    counts = await _incident_counts(session, [m.id for m in rows])
    return [_to_list_item(m, region_names, counts.get(m.id, 0)) for m in rows]


async def list_points(
    session: AsyncSession,
    *,
    search: str | None = None,
    region: str | None = None,
    synced: bool | None = None,
    bbox: str | None = None,
) -> MnoPointsResponse:
    """Лёгкие координаты МНО для карты: те же фильтры, без имён регионов.

    bbox («minLat,minLon,maxLat,maxLon») — видимая область карты: при зуме/панораме
    фронт перезапрашивает точки текущего кадра, так постепенно виден весь регион.
      - bbox задан и валиден → фильтр по числовым lat/lon (индекс ix_mno_lat_lon) +
        существующие фильтры; total = COUNT по этому кадру.
      - bbox не задан/битый → прежнее поведение: все МНО по фильтрам с непустыми coords.
    В обоих случаях points — первые MAX_POINTS строк; capped=True — total превысил лимит.
    """
    filters = _filters(search, region, synced)
    box = parse_bbox(bbox)
    if box is not None:
        min_lat, min_lon, max_lat, max_lon = box
        filters.append(Mno.lat.is_not(None))
        filters.append(Mno.lat.between(min_lat, max_lat))
        filters.append(Mno.lon.between(min_lon, max_lon))
        total = (
            await session.execute(select(func.count(Mno.id)).where(*filters))
        ).scalar_one()
    else:
        total = await _count(session, search=search, region=region, synced=synced)
        filters.append(Mno.coords != "")
    stmt = (
        select(Mno.id, Mno.coords, Mno.name)
        .where(*filters)
        .order_by(asc(Mno.id))
        .limit(MAX_POINTS)
    )
    result = await session.execute(stmt)
    points = [
        MnoPoint(id=row.id, coords=row.coords, name=row.name) for row in result.all()
    ]
    return MnoPointsResponse(points=points, total=total, capped=total > MAX_POINTS)


async def list_form_points(
    session: AsyncSession, *, bbox: str | None
) -> MnoFormPointsResponse:
    """Точки МНО в видимой области карты для ПУБЛИЧНОЙ формы выбора площадки.

    Отдаёт reg/address (для подстановки в форму) + coords/name. bbox ОБЯЗАТЕЛЕН:
    без валидного bbox отдаём пусто — не тянем весь реестр в неавторизованный
    эндпоинт (в отличие от админского list_points, который без bbox грузит всё
    по фильтрам). Фильтр по числовым lat/lon (индекс ix_mno_lat_lon), как в
    list_points; total — COUNT по кадру; points — первые FORM_MAX_POINTS;
    capped=True — total превысил лимит (пользователю стоит приблизить карту).
    """
    box = parse_bbox(bbox)
    if box is None:
        # bbox не задан/битый → пусто (без обращения к БД: не тянем весь реестр).
        return MnoFormPointsResponse(points=[], total=0, capped=False)

    min_lat, min_lon, max_lat, max_lon = box
    filters = [
        Mno.lat.is_not(None),
        Mno.lat.between(min_lat, max_lat),
        Mno.lon.between(min_lon, max_lon),
    ]
    total = (
        await session.execute(select(func.count(Mno.id)).where(*filters))
    ).scalar_one()
    stmt = (
        select(
            Mno.id, Mno.coords, Mno.reg, Mno.address, Mno.name, Mno.city,
            Region.name.label("region_name"),
        )
        # LEFT JOIN за именем субъекта (region_code → Region.code); нет региона в справочнике
        # → region пустой, точка всё равно возвращается.
        .outerjoin(Region, Mno.region_code == Region.code)
        .where(*filters)
        .order_by(asc(Mno.id))
        .limit(FORM_MAX_POINTS)
    )
    result = await session.execute(stmt)
    points = [
        MnoFormPoint(
            id=row.id,
            coords=row.coords,
            reg=row.reg,
            address=row.address,
            name=row.name,
            region=row.region_name or "",
            city=row.city or "",
        )
        for row in result.all()
    ]
    return MnoFormPointsResponse(
        points=points, total=total, capped=total > FORM_MAX_POINTS
    )


async def _get(session: AsyncSession, mno_id: uuid.UUID) -> Mno:
    result = await session.execute(select(Mno).where(Mno.id == mno_id))
    mno = result.scalar_one_or_none()
    if mno is None:
        raise NotFoundError("МНО")
    return mno


async def get_mno(session: AsyncSession, mno_id: uuid.UUID) -> MnoDetail:
    """Карточка МНО (incidents — живой COUNT обращений по ссылке mno_id)."""
    mno = await _get(session, mno_id)
    region_names = await _region_names(session)
    counts = await _incident_counts(session, [mno.id])
    item = _to_list_item(mno, region_names, counts.get(mno.id, 0))
    # comment/photo_urls есть только у волонтёрских МНО; у ФГИС/ручных — NULL/[].
    return MnoDetail(
        **item.model_dump(), comment=mno.comment, photo_urls=mno.photo_urls or []
    )


async def create_mno(
    session: AsyncSession,
    data,
    actor_user_id: uuid.UUID | None,
    source: str = "fgis",
) -> MnoDetail:
    """Создаёт МНО вручную: synced=False, fgis_id=None, incidents=0.

    source — происхождение: 'fgis' (админ вручную) | 'volunteer' (добавил волонтёр из
    приложения) → в админке бейдж «Добавлен волонтёром». actor_user_id=None — создатель
    не пользователь админки (волонтёр); аудит пишет системного актора.
    Появится в ФГИС только после синхронизации (заглушки). Аудит — на создание.
    """
    coords = data.coords.strip()
    # Числовые lat/lon для bbox-фильтра карты (NULL, если coords пусты/невалидны).
    lat, lon = parse_latlon(coords)
    mno = Mno(
        name=data.name.strip(),
        coords=coords,
        lat=lat,
        lon=lon,
        reg=(data.reg or "").strip(),
        region_code=(data.region_code or "").strip(),
        city=(data.city or "").strip(),
        address=(data.address or "").strip(),
        # Происхождение: 'fgis' (админ вручную) | 'volunteer' (создал волонтёр). Ставим явно:
        # server_default применяется на стороне БД, а _to_list_item ниже читает атрибут
        # синхронно ДО refresh (иначе source=None → ошибка схемы).
        source=source,
        fgis_id=None,
        synced=False,
        sync_date=None,
        incidents=0,
    )
    session.add(mno)
    await session.flush()
    await audit(
        session,
        action="create",
        entity_type="mno",
        entity_id=mno.id,
        after={
            "name": mno.name,
            "reg": mno.reg,
            "region_code": mno.region_code,
            "coords": mno.coords,
            "synced": mno.synced,
        },
        actor_user_id=actor_user_id,
    )
    region_names = await _region_names(session)
    item = _to_list_item(mno, region_names)
    return MnoDetail(**item.model_dump())


async def create_mno_from_volunteer(
    session: AsyncSession,
    data: MnoVolunteerCreate,
    photo_files: list | None = None,
    volunteer_id: uuid.UUID | None = None,
) -> MnoDetail:
    """Создаёт МНО, добавленное волонтёром на ПУБЛИЧНОЙ форме (source='volunteer').

    Публичный приём (без auth, в ряду с /intake/form): если нужного МНО нет на карте,
    волонтёр добавляет новое. Помечаем source='volunteer' (в отличие от 'fgis' —
    синхронизированных из ФГИС), чтобы эколог в админке видел бейдж «Добавлен
    волонтёром» и мог проверить точку. Проставляем: synced=False, fgis_id=None,
    reg='' (офиц. реестрового № нет), incidents=0.

    address и coords ОБЯЗАТЕЛЬНЫ: пустые → ValidationError (400 VALIDATION_ERROR).
    Мусорные coords → lat/lon=None (parse_latlon не бросает — точка просто не на карте).
    Тексты подрезаются под ширину колонок (публичный ввод не должен ронять INSERT):
    name[:500], city[:255], region_code[:8], coords[:64], comment[:500]; address —
    TEXT, не режем. photo_files (необязательны) — фото нового МНО: валидируются и
    сохраняются в {STORAGE_DIR}/mno/{id}/ (как у инцидентов), url'ы → mno.photo_urls;
    невалидное фото (тип/размер/>3) → ValidationError (400) ДО commit. comment/photo_urls
    есть только у волонтёрских МНО (у ФГИС/ручных — NULL/[]). Аудит — системный
    (actor_type='system': действующего пользователя нет). flush() здесь, commit() — в роутере.
    """
    address = (data.address or "").strip()
    coords = (data.coords or "").strip()
    if not address or not coords:
        raise ValidationError(
            "Адрес и координаты обязательны",
            details={"address": bool(address), "coords": bool(coords)},
        )
    coords = coords[:64]
    # Комментарий волонтёра (необязателен) — стрипнутый, ≤500 символов; пусто → NULL.
    comment_value = (data.comment or "").strip()[:500] or None
    # Числовые lat/lon для bbox-фильтра карты (NULL, если coords невалидны — не бросаем).
    lat, lon = parse_latlon(coords)
    mno = Mno(
        source="volunteer",
        reg="",  # официального реестрового № у волонтёрского МНО нет
        name=(data.name or "").strip()[:500],
        region_code=(data.region_code or "").strip()[:8],
        city=(data.city or "").strip()[:255],
        address=address,  # TEXT — не режем
        coords=coords,
        lat=lat,
        lon=lon,
        comment=comment_value,
        # Автор МНО из мобильного приложения (опциональный volunteer-токен на публичном
        # POST /intake/mno). NULL — аноним/веб-форма (см. get_optional_volunteer).
        volunteer_id=volunteer_id,
        fgis_id=None,
        synced=False,
        sync_date=None,
        incidents=0,
    )
    session.add(mno)
    await session.flush()  # → mno.id
    # Фото волонтёрского МНО (после flush — нужен mno.id): валидация/ресайз/запись на
    # диск, url'ы → mno.photo_urls. Невалидное фото → ValidationError (400) до commit.
    if photo_files:
        photo_urls, _count = await process_mno_photos(mno.id, photo_files)
        if photo_urls:
            mno.photo_urls = photo_urls
            await session.flush()
    await audit(
        session,
        action="create",
        entity_type="mno",
        entity_id=mno.id,
        after={
            "name": mno.name,
            "address": mno.address,
            "coords": mno.coords,
            "source": mno.source,
            "synced": mno.synced,
            "photos": len(mno.photo_urls or []),
        },
        actor_user_id=None,
        actor_type="system",
    )
    region_names = await _region_names(session)
    item = _to_list_item(mno, region_names)
    # comment/photo_urls есть только у волонтёрских МНО — отдаём их в карточке.
    return MnoDetail(
        **item.model_dump(), comment=mno.comment, photo_urls=(mno.photo_urls or [])
    )


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Расстояние между двумя точками на сфере (метры), формула гаверсинуса.

    Без внешних зависимостей (math). Радиус Земли — 6371 км. Точность достаточна
    для «ближайшие МНО в радиусе десятков км».
    """
    r = 6_371_000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(a))


async def nearest_mno(
    session: AsyncSession,
    lat: float,
    lon: float,
    *,
    limit: int = 5,
    max_km: float = 30.0,
) -> list[dict]:
    """Ближайшие к точке (lat, lon) МНО в радиусе max_km км, по возрастанию расстояния.

    Двухступенчато: сперва грубый bbox-предфильтр по индексу ix_mno_lat_lon (рамка
    ±max_km в градусах: dlat=max_km/111, dlon с поправкой на cos(lat)) — чтобы не
    тянуть весь реестр; затем точный haversine в питоне, отсечение по радиусу,
    сортировка по расстоянию и срез limit. МНО без числовых координат (lat/lon IS
    NULL) не участвуют. Возврат — список dict: id(str), name, address, city, coords,
    lat, lon, distance_m(int, метры).
    """
    dlat = max_km / 111.0
    cos_lat = math.cos(math.radians(lat))
    # У полюсов cos(lat)→0: не делим на ноль — берём максимально широкую рамку по
    # долготе (haversine ниже всё равно отсечёт лишнее по реальному радиусу).
    dlon = 360.0 if abs(cos_lat) < 1e-6 else max_km / (111.0 * abs(cos_lat))

    stmt = select(Mno).where(
        Mno.lat.is_not(None),
        Mno.lon.is_not(None),
        Mno.lat.between(lat - dlat, lat + dlat),
        Mno.lon.between(lon - dlon, lon + dlon),
    )
    rows = list((await session.execute(stmt)).scalars().all())

    scored: list[tuple[float, Mno]] = []
    for m in rows:
        # Страховка: строки без координат в выборку не должны попадать (SQL is_not),
        # но проверяем и здесь — точка без координат не измеряется.
        if m.lat is None or m.lon is None:
            continue
        dist = _haversine_m(lat, lon, m.lat, m.lon)
        if dist <= max_km * 1000.0:
            scored.append((dist, m))
    scored.sort(key=lambda t: t[0])

    out: list[dict] = []
    for dist, m in scored[: max(0, limit)]:
        out.append(
            {
                "id": str(m.id),
                "name": m.name,
                "address": m.address,
                "city": m.city,
                "coords": m.coords,
                "lat": m.lat,
                "lon": m.lon,
                "distance_m": int(round(dist)),
            }
        )
    return out


def _stub_fgis_id() -> str:
    """Placeholder-идентификатор ФГИС (реальной интеграции нет)."""
    return f"STUB-{uuid.uuid4().hex[:8]}"


def _apply_sync(mno: Mno, now: datetime) -> None:
    """Помечает одно МНО синхронизированным (заглушка): synced + sync_date + fgis_id."""
    mno.synced = True
    mno.sync_date = now
    if not mno.fgis_id:
        mno.fgis_id = _stub_fgis_id()


async def sync_all(session: AsyncSession, actor_user_id: uuid.UUID) -> MnoSyncResult:
    """ЗАГЛУШКА синхронизации с ФГИС: помечает ВСЕ ещё-не-synced МНО.

    Реальной интеграции с ФГИС УТКО НЕТ — внешних запросов не делаем. Каждому
    несинхронизированному МНО проставляем synced=True, sync_date=now и placeholder
    fgis_id ("STUB-…"). Возвращает {synced: сколько помечено, total: всего МНО}.
    Пишет один системный (actor_type='system') аудит-итог.
    """
    now = datetime.now(timezone.utc)
    total = (await session.execute(select(func.count(Mno.id)))).scalar_one()

    result = await session.execute(select(Mno).where(Mno.synced.is_(False)))
    pending = result.scalars().all()
    for mno in pending:
        _apply_sync(mno, now)
    await session.flush()

    await audit(
        session,
        action="fgis_sync_all",
        entity_type="mno",
        entity_id=None,
        after={"synced": len(pending), "total": total},
        actor_user_id=actor_user_id,
        actor_type="system",
    )
    return MnoSyncResult(synced=len(pending), total=total)


async def sync_one(
    session: AsyncSession, mno_id: uuid.UUID, actor_user_id: uuid.UUID
) -> MnoDetail:
    """ЗАГЛУШКА синхронизации одного МНО с ФГИС (без внешних запросов).

    Идемпотентно: уже синхронизированное МНО лишь обновляет sync_date. Аудит — системный.
    """
    mno = await _get(session, mno_id)
    before = {"synced": mno.synced, "fgis_id": mno.fgis_id}
    _apply_sync(mno, datetime.now(timezone.utc))
    await session.flush()
    await audit(
        session,
        action="fgis_sync_one",
        entity_type="mno",
        entity_id=mno.id,
        before=before,
        after={"synced": mno.synced, "fgis_id": mno.fgis_id},
        actor_user_id=actor_user_id,
        actor_type="system",
    )
    region_names = await _region_names(session)
    item = _to_list_item(mno, region_names)
    return MnoDetail(**item.model_dump())
