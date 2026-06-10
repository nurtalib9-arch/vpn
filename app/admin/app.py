from fastapi import FastAPI, Depends, HTTPException, Request, Form, status, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import select, func, and_, update, desc
from app.core.database import async_session
from app.models.user import User
from app.models.payment import Payment
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.server import Server
from app.models.tariff import Tariff
from app.core.config import settings
from datetime import datetime, timezone, timedelta
from typing import Optional
import secrets
import logging
import hmac
import hashlib

logger = logging.getLogger(__name__)

admin_app = FastAPI(title="VPN Bot Admin Panel")
security = HTTPBasic()

# ─── Auth ─────────────────────────────────────────────────────────────────────

def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    is_correct_username = secrets.compare_digest(
        credentials.username.encode(), settings.ADMIN_USERNAME.encode()
    )
    is_correct_password = secrets.compare_digest(
        credentials.password.encode(), settings.ADMIN_PASSWORD.encode()
    )
    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


# ─── HTML Templates ───────────────────────────────────────────────────────────

def base_html(title: str, content: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} — VPN Admin</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                background: #0f0f13; color: #e2e8f0; min-height: 100vh; }}
        .nav {{ background: #1a1a2e; border-bottom: 1px solid #2d2d44; padding: 0 24px;
                display: flex; align-items: center; height: 60px; gap: 32px; }}
        .nav a {{ color: #94a3b8; text-decoration: none; font-size: 14px; font-weight: 500;
                  padding: 4px 0; border-bottom: 2px solid transparent; transition: .2s; }}
        .nav a:hover, .nav a.active {{ color: #818cf8; border-bottom-color: #818cf8; }}
        .nav .brand {{ color: #818cf8; font-size: 18px; font-weight: 700; margin-right: 16px; }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 32px 24px; }}
        h1 {{ font-size: 28px; font-weight: 700; margin-bottom: 24px; color: #f1f5f9; }}
        h2 {{ font-size: 20px; font-weight: 600; margin-bottom: 16px; color: #f1f5f9; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                       gap: 20px; margin-bottom: 32px; }}
        .stat-card {{ background: #1a1a2e; border: 1px solid #2d2d44; border-radius: 12px;
                      padding: 24px; }}
        .stat-card .label {{ font-size: 13px; color: #64748b; text-transform: uppercase;
                             letter-spacing: .05em; margin-bottom: 8px; }}
        .stat-card .value {{ font-size: 36px; font-weight: 700; color: #818cf8; }}
        .stat-card .sub {{ font-size: 13px; color: #64748b; margin-top: 4px; }}
        table {{ width: 100%; border-collapse: collapse; background: #1a1a2e;
                 border: 1px solid #2d2d44; border-radius: 12px; overflow: hidden; }}
        th {{ text-align: left; padding: 14px 16px; font-size: 12px; text-transform: uppercase;
              letter-spacing: .05em; color: #64748b; background: #12121f; border-bottom: 1px solid #2d2d44; }}
        td {{ padding: 14px 16px; font-size: 14px; border-bottom: 1px solid #1e1e30; }}
        tr:last-child td {{ border-bottom: none; }}
        tr:hover td {{ background: #1e1e30; }}
        .badge {{ display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 12px;
                  font-weight: 600; }}
        .badge-active {{ background: #064e3b; color: #34d399; }}
        .badge-expired {{ background: #4c0519; color: #f87171; }}
        .badge-pending {{ background: #422006; color: #fbbf24; }}
        .badge-success {{ background: #064e3b; color: #34d399; }}
        .badge-banned {{ background: #4c0519; color: #f87171; }}
        .badge-ok {{ background: #1e3a5f; color: #60a5fa; }}
        .btn {{ display: inline-block; padding: 8px 16px; border-radius: 8px; font-size: 13px;
                font-weight: 600; text-decoration: none; border: none; cursor: pointer;
                transition: .2s; }}
        .btn-sm {{ padding: 5px 12px; font-size: 12px; }}
        .btn-danger {{ background: #7f1d1d; color: #fca5a5; }}
        .btn-danger:hover {{ background: #991b1b; }}
        .btn-success {{ background: #064e3b; color: #6ee7b7; }}
        .btn-success:hover {{ background: #065f46; }}
        .btn-primary {{ background: #3730a3; color: #a5b4fc; }}
        .btn-primary:hover {{ background: #4338ca; }}
        .search-bar {{ display: flex; gap: 12px; margin-bottom: 20px; }}
        .search-bar input {{ flex: 1; background: #1a1a2e; border: 1px solid #2d2d44;
                             color: #e2e8f0; padding: 10px 16px; border-radius: 8px; font-size: 14px; }}
        .search-bar input:focus {{ outline: none; border-color: #818cf8; }}
        .pagination {{ display: flex; gap: 8px; margin-top: 20px; align-items: center; }}
        .pagination a {{ color: #818cf8; text-decoration: none; padding: 6px 12px;
                         border: 1px solid #2d2d44; border-radius: 6px; font-size: 13px; }}
        .pagination a:hover {{ background: #2d2d44; }}
        form.inline {{ display: inline; }}
        .form-card {{ background: #1a1a2e; border: 1px solid #2d2d44; border-radius: 12px; padding: 24px; margin-bottom: 24px; }}
        label {{ display: block; margin-bottom: 6px; font-size: 13px; color: #94a3b8; }}
        input[type=text], input[type=number], select, textarea {{
            width: 100%; background: #0f0f13; border: 1px solid #2d2d44; color: #e2e8f0;
            padding: 10px 14px; border-radius: 8px; font-size: 14px; margin-bottom: 16px; }}
        input:focus, select:focus, textarea:focus {{ outline: none; border-color: #818cf8; }}
    </style>
</head>
<body>
<nav class="nav">
    <span class="brand">🛡 VPN Admin</span>
    <a href="/">Дашборд</a>
    <a href="/users">Пользователи</a>
    <a href="/subscriptions">Подписки</a>
    <a href="/payments">Платежи</a>
    <a href="/servers">Серверы</a>
    <a href="/tariffs">Тарифы</a>
</nav>
<div class="container">
{content}
</div>
</body>
</html>"""


# ─── Dashboard ────────────────────────────────────────────────────────────────

@admin_app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, admin: str = Depends(verify_admin)):
    async with async_session() as session:
        total_users = (await session.execute(select(func.count(User.id)))).scalar() or 0
        total_revenue = (
            await session.execute(
                select(func.sum(Payment.amount)).where(Payment.status == "success")
            )
        ).scalar() or 0
        active_subs = (
            await session.execute(
                select(func.count(Subscription.id))
                .where(Subscription.status == SubscriptionStatus.ACTIVE)
            )
        ).scalar() or 0

        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
        today_revenue = (
            await session.execute(
                select(func.sum(Payment.amount))
                .where(
                    and_(
                        Payment.status == "success",
                        Payment.paid_at >= today_start,
                    )
                )
            )
        ).scalar() or 0

        new_users_7d = (
            await session.execute(
                select(func.count(User.id))
                .where(User.created_at >= datetime.now(timezone.utc) - timedelta(days=7))
            )
        ).scalar() or 0

        month_revenue = (
            await session.execute(
                select(func.sum(Payment.amount))
                .where(
                    and_(
                        Payment.status == "success",
                        Payment.paid_at >= datetime.now(timezone.utc) - timedelta(days=30),
                    )
                )
            )
        ).scalar() or 0

    content = f"""
<h1>📊 Дашборд</h1>
<div class="stats-grid">
    <div class="stat-card">
        <div class="label">Всего пользователей</div>
        <div class="value">{total_users:,}</div>
        <div class="sub">+{new_users_7d} за 7 дней</div>
    </div>
    <div class="stat-card">
        <div class="label">Активных подписок</div>
        <div class="value">{active_subs:,}</div>
    </div>
    <div class="stat-card">
        <div class="label">Выручка (всего)</div>
        <div class="value">{float(total_revenue):,.0f}₽</div>
    </div>
    <div class="stat-card">
        <div class="label">Выручка (30 дней)</div>
        <div class="value">{float(month_revenue):,.0f}₽</div>
        <div class="sub">Сегодня: {float(today_revenue):,.0f}₽</div>
    </div>
</div>
"""
    return base_html("Дашборд", content)


# ─── Users ────────────────────────────────────────────────────────────────────

@admin_app.get("/users", response_class=HTMLResponse)
async def users_list(
    request: Request,
    admin: str = Depends(verify_admin),
    page: int = Query(1, ge=1),
    search: str = Query("", alias="q"),
):
    limit = 50
    offset = (page - 1) * limit

    async with async_session() as session:
        base_query = select(User)
        if search:
            base_query = base_query.where(
                User.username.ilike(f"%{search}%")
                | User.first_name.ilike(f"%{search}%")
            )

        total = (
            await session.execute(select(func.count()).select_from(base_query.subquery()))
        ).scalar() or 0

        result = await session.execute(
            base_query.order_by(desc(User.created_at)).limit(limit).offset(offset)
        )
        users = result.scalars().all()

    rows = ""
    for u in users:
        banned_badge = '<span class="badge badge-banned">Бан</span>' if u.is_banned else '<span class="badge badge-ok">Активен</span>'
        admin_badge = ' <span class="badge badge-active">Admin</span>' if u.is_admin else ""
        ban_btn = (
            f'<form class="inline" method="post" action="/users/{u.telegram_id}/unban"><button class="btn btn-sm btn-success" type="submit">Разбан</button></form>'
            if u.is_banned
            else f'<form class="inline" method="post" action="/users/{u.telegram_id}/ban"><button class="btn btn-sm btn-danger" type="submit">Бан</button></form>'
        )
        date = u.created_at.strftime("%d.%m.%Y") if u.created_at else "—"
        rows += f"""<tr>
            <td>{u.id}</td>
            <td><code>{u.telegram_id}</code></td>
            <td>@{u.username or "—"}</td>
            <td>{u.first_name or ""} {u.last_name or ""}</td>
            <td><code>{u.referral_code}</code></td>
            <td>{banned_badge}{admin_badge}</td>
            <td>{date}</td>
            <td>{ban_btn}</td>
        </tr>"""

    pages = (total + limit - 1) // limit
    pagination = ""
    for p in range(max(1, page - 2), min(pages + 1, page + 3)):
        active = 'style="background:#2d2d44"' if p == page else ""
        pagination += f'<a href="/users?page={p}&q={search}" {active}>{p}</a>'

    content = f"""
<h1>👤 Пользователи ({total:,})</h1>
<div class="search-bar">
    <form method="get" style="display:flex;gap:12px;flex:1">
        <input type="text" name="q" value="{search}" placeholder="Поиск по username, имени...">
        <button class="btn btn-primary" type="submit">Найти</button>
    </form>
</div>
<table>
<thead><tr>
    <th>ID</th><th>Telegram ID</th><th>Username</th><th>Имя</th>
    <th>Реф. код</th><th>Статус</th><th>Регистрация</th><th>Действия</th>
</tr></thead>
<tbody>{rows}</tbody>
</table>
<div class="pagination">{pagination}</div>
"""
    return base_html("Пользователи", content)


@admin_app.post("/users/{telegram_id}/ban")
async def ban_user(telegram_id: int, admin: str = Depends(verify_admin)):
    from app.services.user_service import UserService
    await UserService().ban_user(telegram_id)
    return RedirectResponse("/users", status_code=303)


@admin_app.post("/users/{telegram_id}/unban")
async def unban_user(telegram_id: int, admin: str = Depends(verify_admin)):
    from app.services.user_service import UserService
    await UserService().unban_user(telegram_id)
    return RedirectResponse("/users", status_code=303)


# ─── Subscriptions ────────────────────────────────────────────────────────────

@admin_app.get("/subscriptions", response_class=HTMLResponse)
async def subscriptions_list(
    request: Request,
    admin: str = Depends(verify_admin),
    page: int = Query(1, ge=1),
    status_filter: str = Query("", alias="status"),
):
    limit = 50
    offset = (page - 1) * limit

    async with async_session() as session:
        base_query = select(Subscription, User).join(User)
        if status_filter:
            base_query = base_query.where(Subscription.status == status_filter)

        total = (
            await session.execute(select(func.count()).select_from(base_query.subquery()))
        ).scalar() or 0

        result = await session.execute(
            base_query.order_by(desc(Subscription.created_at)).limit(limit).offset(offset)
        )
        rows_data = result.all()

    rows = ""
    for sub, user in rows_data:
        status_badge = {
            "active": '<span class="badge badge-active">Активна</span>',
            "expired": '<span class="badge badge-expired">Истекла</span>',
            "pending": '<span class="badge badge-pending">Ожидание</span>',
            "cancelled": '<span class="badge badge-expired">Отменена</span>',
        }.get(sub.status, sub.status)

        end = sub.end_date.strftime("%d.%m.%Y") if sub.end_date else "—"
        tariff_name = sub.tariff.name if sub.tariff else "—"
        server_name = sub.server.name if sub.server else "—"
        username = f"@{user.username}" if user.username else f"ID {user.telegram_id}"
        marzban = sub.marzban_username or "—"

        rows += f"""<tr>
            <td>{sub.id}</td>
            <td>{username}</td>
            <td>{tariff_name}</td>
            <td>{server_name}</td>
            <td>{status_badge}</td>
            <td>{end}</td>
            <td><small><code>{marzban}</code></small></td>
        </tr>"""

    content = f"""
<h1>📋 Подписки ({total:,})</h1>
<div class="search-bar">
    <a href="/subscriptions" class="btn btn-sm {'btn-primary' if not status_filter else 'btn-success'}">Все</a>
    <a href="/subscriptions?status=active" class="btn btn-sm btn-success">Активные</a>
    <a href="/subscriptions?status=expired" class="btn btn-sm btn-danger">Истёкшие</a>
    <a href="/subscriptions?status=pending" class="btn btn-sm btn-primary">В ожидании</a>
</div>
<table>
<thead><tr>
    <th>ID</th><th>Пользователь</th><th>Тариф</th><th>Сервер</th>
    <th>Статус</th><th>До</th><th>Marzban</th>
</tr></thead>
<tbody>{rows}</tbody>
</table>
"""
    return base_html("Подписки", content)


# ─── Payments ─────────────────────────────────────────────────────────────────

@admin_app.get("/payments", response_class=HTMLResponse)
async def payments_list(
    request: Request,
    admin: str = Depends(verify_admin),
    page: int = Query(1, ge=1),
    provider_filter: str = Query("", alias="provider"),
):
    limit = 50
    offset = (page - 1) * limit

    async with async_session() as session:
        base_query = select(Payment, User).join(User)
        if provider_filter:
            base_query = base_query.where(Payment.provider == provider_filter)

        total = (
            await session.execute(select(func.count()).select_from(base_query.subquery()))
        ).scalar() or 0

        result = await session.execute(
            base_query.order_by(desc(Payment.created_at)).limit(limit).offset(offset)
        )
        rows_data = result.all()

    rows = ""
    for pay, user in rows_data:
        status_badge = {
            "success": '<span class="badge badge-active">Успешно</span>',
            "pending": '<span class="badge badge-pending">Ожидание</span>',
            "failed": '<span class="badge badge-expired">Ошибка</span>',
        }.get(pay.status, pay.status)
        date = pay.created_at.strftime("%d.%m.%Y %H:%M") if pay.created_at else "—"
        username = f"@{user.username}" if user.username else f"ID {user.telegram_id}"
        rows += f"""<tr>
            <td>{pay.id}</td>
            <td>{username}</td>
            <td><b>{pay.amount}₽</b></td>
            <td>{pay.provider}</td>
            <td>{status_badge}</td>
            <td>{date}</td>
            <td><small><code>{pay.provider_payment_id[:24]}...</code></small></td>
        </tr>"""

    content = f"""
<h1>💳 Платежи ({total:,})</h1>
<div class="search-bar">
    <a href="/payments" class="btn btn-sm btn-primary">Все</a>
    <a href="/payments?provider=yookassa" class="btn btn-sm btn-success">YooKassa</a>
    <a href="/payments?provider=cryptobot" class="btn btn-sm btn-success">CryptoBot</a>
</div>
<table>
<thead><tr>
    <th>ID</th><th>Пользователь</th><th>Сумма</th><th>Провайдер</th>
    <th>Статус</th><th>Дата</th><th>Payment ID</th>
</tr></thead>
<tbody>{rows}</tbody>
</table>
"""
    return base_html("Платежи", content)


# ─── Servers ──────────────────────────────────────────────────────────────────

@admin_app.get("/servers", response_class=HTMLResponse)
async def servers_list(request: Request, admin: str = Depends(verify_admin)):
    async with async_session() as session:
        result = await session.execute(select(Server).order_by(Server.id))
        servers = result.scalars().all()

    rows = ""
    for s in servers:
        active_badge = (
            '<span class="badge badge-active">Активен</span>'
            if s.is_active
            else '<span class="badge badge-expired">Выкл</span>'
        )
        load = f"{s.current_users}/{s.max_users}"
        rows += f"""<tr>
            <td>{s.id}</td>
            <td><b>{s.name}</b></td>
            <td><code>{s.host}</code></td>
            <td>{s.location or '—'}</td>
            <td>{load}</td>
            <td>{active_badge}</td>
            <td>{float(s.cpu_usage or 0):.1f}%</td>
            <td>{float(s.ram_usage or 0):.1f}%</td>
            <td>
                <a href="/servers/{s.id}/edit" class="btn btn-sm btn-primary">Ред.</a>
                <form class="inline" method="post" action="/servers/{s.id}/toggle">
                    <button class="btn btn-sm {'btn-danger' if s.is_active else 'btn-success'}" type="submit">
                        {'Выкл' if s.is_active else 'Вкл'}
                    </button>
                </form>
            </td>
        </tr>"""

    add_form = """
<div class="form-card">
    <h2>➕ Добавить сервер</h2>
    <form method="post" action="/servers/add">
        <label>Название</label>
        <input type="text" name="name" placeholder="Netherlands #1" required>
        <label>Host (домен или IP)</label>
        <input type="text" name="host" placeholder="nl1.vpn.example.com" required>
        <label>Локация</label>
        <input type="text" name="location" placeholder="🇳🇱 Нидерланды">
        <label>Max пользователей</label>
        <input type="number" name="max_users" value="100" required>
        <label>Marzban Node ID (опционально)</label>
        <input type="text" name="marzban_node_id" placeholder="node-uuid">
        <button class="btn btn-primary" type="submit">Добавить</button>
    </form>
</div>"""

    content = f"""
<h1>🖥 Серверы</h1>
{add_form}
<table>
<thead><tr>
    <th>ID</th><th>Название</th><th>Host</th><th>Локация</th>
    <th>Нагрузка</th><th>Статус</th><th>CPU</th><th>RAM</th><th>Действия</th>
</tr></thead>
<tbody>{rows}</tbody>
</table>
"""
    return base_html("Серверы", content)


@admin_app.post("/servers/add")
async def add_server(
    admin: str = Depends(verify_admin),
    name: str = Form(...),
    host: str = Form(...),
    location: str = Form(""),
    max_users: int = Form(100),
    marzban_node_id: str = Form(""),
):
    async with async_session() as session:
        server = Server(
            name=name,
            host=host,
            location=location or None,
            max_users=max_users,
            marzban_node_id=marzban_node_id or None,
        )
        session.add(server)
        await session.commit()
    return RedirectResponse("/servers", status_code=303)


@admin_app.post("/servers/{server_id}/toggle")
async def toggle_server(server_id: int, admin: str = Depends(verify_admin)):
    async with async_session() as session:
        server = await session.get(Server, server_id)
        if server:
            server.is_active = not server.is_active
            await session.commit()
    return RedirectResponse("/servers", status_code=303)


# ─── Tariffs ──────────────────────────────────────────────────────────────────

@admin_app.get("/tariffs", response_class=HTMLResponse)
async def tariffs_list(request: Request, admin: str = Depends(verify_admin)):
    async with async_session() as session:
        result = await session.execute(select(Tariff).order_by(Tariff.duration_months))
        tariffs = result.scalars().all()

    rows = ""
    for t in tariffs:
        active_badge = (
            '<span class="badge badge-active">Активен</span>'
            if t.is_active
            else '<span class="badge badge-expired">Скрыт</span>'
        )
        rows += f"""<tr>
            <td>{t.id}</td>
            <td><b>{t.name}</b></td>
            <td>{t.duration_months} мес.</td>
            <td><b>{t.price}₽</b></td>
            <td>{t.discount_percent}%</td>
            <td>{active_badge}</td>
            <td>
                <form class="inline" method="post" action="/tariffs/{t.id}/toggle">
                    <button class="btn btn-sm {'btn-danger' if t.is_active else 'btn-success'}" type="submit">
                        {'Скрыть' if t.is_active else 'Показать'}
                    </button>
                </form>
            </td>
        </tr>"""

    add_form = """
<div class="form-card">
    <h2>➕ Добавить тариф</h2>
    <form method="post" action="/tariffs/add">
        <label>Название</label>
        <input type="text" name="name" placeholder="1 месяц" required>
        <label>Длительность (месяцев)</label>
        <input type="number" name="duration_months" value="1" required>
        <label>Цена (₽)</label>
        <input type="number" name="price" value="249" step="0.01" required>
        <label>Скидка (%)</label>
        <input type="number" name="discount_percent" value="0">
        <label>Описание</label>
        <textarea name="description" rows="2"></textarea>
        <button class="btn btn-primary" type="submit">Добавить</button>
    </form>
</div>"""

    content = f"""
<h1>💰 Тарифы</h1>
{add_form}
<table>
<thead><tr>
    <th>ID</th><th>Название</th><th>Длительность</th>
    <th>Цена</th><th>Скидка</th><th>Статус</th><th>Действия</th>
</tr></thead>
<tbody>{rows}</tbody>
</table>
"""
    return base_html("Тарифы", content)


@admin_app.post("/tariffs/add")
async def add_tariff(
    admin: str = Depends(verify_admin),
    name: str = Form(...),
    duration_months: int = Form(...),
    price: float = Form(...),
    discount_percent: int = Form(0),
    description: str = Form(""),
):
    async with async_session() as session:
        tariff = Tariff(
            name=name,
            duration_months=duration_months,
            price=price,
            discount_percent=discount_percent,
            description=description or None,
        )
        session.add(tariff)
        await session.commit()
    return RedirectResponse("/tariffs", status_code=303)


@admin_app.post("/tariffs/{tariff_id}/toggle")
async def toggle_tariff(tariff_id: int, admin: str = Depends(verify_admin)):
    async with async_session() as session:
        tariff = await session.get(Tariff, tariff_id)
        if tariff:
            tariff.is_active = not tariff.is_active
            await session.commit()
    return RedirectResponse("/tariffs", status_code=303)


# ─── Telegram Auth ────────────────────────────────────────────────────────────

@admin_app.get("/auth/telegram")
async def telegram_auth(
    id: int = Query(...),
    first_name: str = Query(...),
    username: Optional[str] = Query(None),
    photo_url: Optional[str] = Query(None),
    auth_date: int = Query(...),
    hash: str = Query(...),
):
    if id not in settings.ADMIN_IDS:
        raise HTTPException(status_code=403, detail="Not authorized as admin")

    data = {"id": str(id), "first_name": first_name, "auth_date": str(auth_date)}
    if username:
        data["username"] = username
    if photo_url:
        data["photo_url"] = photo_url

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hashlib.sha256(settings.BOT_TOKEN.encode()).digest()
    expected = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, hash):
        raise HTTPException(status_code=401, detail="Invalid Telegram auth data")

    return JSONResponse({"status": "ok", "user_id": id})


# ─── API endpoints for stats ──────────────────────────────────────────────────

@admin_app.get("/api/stats")
async def api_stats(admin: str = Depends(verify_admin)):
    async with async_session() as session:
        total_users = (await session.execute(select(func.count(User.id)))).scalar() or 0
        active_subs = (
            await session.execute(
                select(func.count(Subscription.id))
                .where(Subscription.status == SubscriptionStatus.ACTIVE)
            )
        ).scalar() or 0
        total_revenue = (
            await session.execute(
                select(func.sum(Payment.amount)).where(Payment.status == "success")
            )
        ).scalar() or 0

    return {
        "total_users": total_users,
        "active_subscriptions": active_subs,
        "total_revenue": float(total_revenue),
    }
