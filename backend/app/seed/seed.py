"""Idempotent seed data — PLAN.md §7, data-model.md §4/§5/§5.1 (T136/T137).

Run: ``python -m app.seed.seed`` (quickstart.md §3; ``docker compose exec backend
python -m app.seed.seed`` in the compose stack).

Idempotency: every row's primary key is a deterministic UUIDv5 derived from a fixed namespace
plus a stable text key (``sid(...)`` below), or — for the two rows that must line up with the
running system's own configuration — ``settings.SYSTEM_DEFAULT_BRANCH_ID`` /
``SYSTEM_DEFAULT_DEPARTMENT_ID``. Every insert is ``ON CONFLICT (id) DO NOTHING``, so re-running
this module against an already-seeded database is a no-op: identical row counts before and after
(T137). No row's identity is derived from anything read off the OS or the shell — the two rows a
prior manual test corrupted to literal ``?`` were victims of a Windows console codepage passing
Arabic through an argument/stdin round trip; every string here is a Python source-level literal
in this UTF-8 file, never constructed from ``sys.argv``, environment strings, or piped input.

Scoping note: `categories`/`priorities`/`ticket_statuses`/`status_transitions` are all pattern S2
(``branch_id`` NOT NULL — data-model.md §0.7). PLAN.md §7's headline counts ("4 priorities",
"7 statuses") describe one branch's catalog shape; both seeded branches get their own physical
copy of each; otherwise the second branch could never legally hold a ticket (`TicketService.
_validate_taxonomy` requires `priority.branch_id == ticket.branch_id`, and the tenant-scoping
constitution principle (C4/C5) forbids a ticket silently borrowing another branch's reference
data). SLA policies and quick replies are seeded once, against the primary branch only, matching
PLAN.md §7's literal counts (3 and 8) exactly — they are demo-path assets, not something every
branch's ticket needs to have set.

Role note: "5 users covering all four roles" (PLAN.md §7) means the four *role rows* — admin,
lead, agent, customer — all exist (`roles.code`'s CHECK). Only three of them are ever assigned to
a `users` row here: the `customer` role belongs to the portal's unauthenticated actor (PLAN.md
§1.1, data-model.md §5.1), which is a `customers` row, never a `users`/`user_roles` row.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import bindparam, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.chunking import chunk_text
from app.ai.embeddings import get_embedding_model
from app.config import settings
from app.core.security import hash_password
from app.db import async_session_factory
from app.models.category import Category
from app.models.channel_config import ChannelConfig
from app.models.customer import ContactMethod, Customer
from app.models.department import Department
from app.models.branch import Branch
from app.models.kb_article import KbArticle, KbArticleChunk
from app.models.priority import Priority
from app.models.quick_reply import QuickReply
from app.models.role import Permission, Role, RolePermission
from app.models.sla_policy import SlaPolicy
from app.models.status_transition import StatusTransition
from app.models.ticket import Ticket
from app.models.ticket_event import TicketEvent
from app.models.ticket_status import TicketStatus
from app.models.user import User
from app.models.user_role import UserRole
from app.repositories.scoped_repository import TenantScope
from app.services.sla_service import SlaService

SEED_NAMESPACE = uuid.UUID("2f9a6f0e-2b7a-4b7a-9c0b-2f0f6b6e9a10")
ARABIC_BLOCK = range(0x0600, 0x0700)


def sid(*parts: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, ":".join(parts))


async def upsert(session: AsyncSession, model, rows: list[dict]) -> None:
    if not rows:
        return
    stmt = pg_insert(model).values(rows).on_conflict_do_nothing(index_elements=["id"])
    await session.execute(stmt)


# --------------------------------------------------------------------------------------------
# Branches / departments
# --------------------------------------------------------------------------------------------

BRANCH_A_ID = settings.SYSTEM_DEFAULT_BRANCH_ID  # Cairo — also the system-default branch
BRANCH_B_ID = sid("branch", "riyadh")

DEPT_CAI_SUPPORT_ID = settings.SYSTEM_DEFAULT_DEPARTMENT_ID  # also the system-default department
DEPT_CAI_SALES_ID = sid("department", "cairo", "sales")
DEPT_RUH_SUPPORT_ID = sid("department", "riyadh", "support")


async def seed_branches(session: AsyncSession) -> None:
    rows = [
        dict(
            id=BRANCH_A_ID, code="CAI", label_ar="فرع القاهرة", label_en="Cairo Branch",
            timezone="Africa/Cairo", is_active=True,
            business_hours={
                "sun": {"open": "09:00", "close": "17:00"},
                "mon": {"open": "09:00", "close": "17:00"},
                "tue": {"open": "09:00", "close": "17:00"},
                "wed": {"open": "09:00", "close": "17:00"},
                "thu": {"open": "09:00", "close": "17:00"},
            },
        ),
        dict(
            id=BRANCH_B_ID, code="RUH", label_ar="فرع الرياض", label_en="Riyadh Branch",
            timezone="Asia/Riyadh", is_active=True,
            business_hours={
                "sun": {"open": "08:00", "close": "16:00"},
                "mon": {"open": "08:00", "close": "16:00"},
                "tue": {"open": "08:00", "close": "16:00"},
                "wed": {"open": "08:00", "close": "16:00"},
                "thu": {"open": "08:00", "close": "16:00"},
            },
        ),
    ]
    await upsert(session, Branch, rows)


async def seed_departments(session: AsyncSession) -> None:
    rows = [
        dict(id=DEPT_CAI_SUPPORT_ID, branch_id=BRANCH_A_ID, code="SUPPORT",
             label_ar="دعم العملاء", label_en="Customer Support", is_active=True),
        dict(id=DEPT_CAI_SALES_ID, branch_id=BRANCH_A_ID, code="SALES",
             label_ar="المبيعات", label_en="Sales", is_active=True),
        dict(id=DEPT_RUH_SUPPORT_ID, branch_id=BRANCH_B_ID, code="SUPPORT",
             label_ar="دعم العملاء", label_en="Customer Support", is_active=True),
    ]
    await upsert(session, Department, rows)


# --------------------------------------------------------------------------------------------
# Roles / permissions / role_permissions (data-model.md §5, §5.1)
# --------------------------------------------------------------------------------------------

ROLE_LABELS = {
    "admin": ("مدير النظام", "Administrator"),
    "lead": ("رئيس الفريق", "Team Lead"),
    "agent": ("موظف الدعم", "Agent"),
    "customer": ("العميل", "Customer"),
}
ROLE_IDS = {code: sid("role", code) for code in ROLE_LABELS}

# code -> (label_ar, label_en, [role codes granted at seed time])
PERMISSIONS: dict[str, tuple[str, str, list[str]]] = {
    "admin.config": ("تهيئة الإدارة", "Admin Configuration", ["admin"]),
    "branch.read": ("عرض الفروع", "View Branches", ["agent", "lead", "admin"]),
    "department.read": ("عرض الأقسام", "View Departments", ["agent", "lead", "admin"]),
    "user.read": ("عرض المستخدمين", "View Users", ["agent", "lead", "admin"]),
    "role.read": ("عرض الأدوار", "View Roles", ["agent", "lead", "admin"]),
    "category.read": ("عرض التصنيفات", "View Categories", ["agent", "lead", "admin"]),
    "priority.read": ("عرض الأولويات", "View Priorities", ["agent", "lead", "admin"]),
    "ticket_status.read": ("عرض حالات التذاكر", "View Ticket Statuses", ["agent", "lead", "admin"]),
    "status_transition.read": (
        "عرض انتقالات الحالة", "View Status Transitions", ["agent", "lead", "admin"],
    ),
    "sla_policy.read": (
        "عرض سياسات اتفاقية مستوى الخدمة", "View SLA Policies", ["agent", "lead", "admin"],
    ),
    "quick_reply.read": ("عرض الردود السريعة", "View Quick Replies", ["agent", "lead", "admin"]),
    "team.read": ("عرض الفرق", "View Teams", ["agent", "lead", "admin"]),
    "ticket.read": ("عرض التذاكر", "View Tickets", ["agent", "lead", "admin"]),
    "ticket.create": ("إنشاء تذكرة", "Create Ticket", ["agent", "lead", "admin"]),
    "ticket.close": ("إغلاق التذاكر", "Close Tickets", ["agent", "lead", "admin"]),
    "ticket.own": ("امتلاك التذاكر", "Own Tickets", ["agent", "lead", "admin"]),
    "ticket.assign": ("إسناد التذاكر", "Assign Tickets", ["lead", "admin"]),
    "ticket.reopen": ("إعادة فتح التذاكر", "Reopen Tickets", ["lead", "admin"]),
    "ticket.sla_override": (
        "تجاوز سياسة اتفاقية مستوى الخدمة", "Override SLA Policy", ["lead", "admin"],
    ),
    "customer.read": ("عرض العملاء", "View Customers", ["agent", "lead", "admin"]),
    "customer.create": ("إنشاء عميل", "Create Customer", ["agent", "lead", "admin"]),
    "customer.delete": ("إلغاء تفعيل العميل", "Deactivate Customer", ["admin"]),
    "report.cross_branch": ("تقارير عبر الفروع", "Cross-Branch Reports", ["admin"]),
    "audit.read": ("عرض سجل التدقيق", "View Audit Log", ["admin"]),
    # F06 (Batch 4g) — data-model.md §5's generic {entity}.read/.create convention. `read` is
    # granted as broadly as ticket.read (an agent must be able to search the KB while handling a
    # ticket, FR-042); authoring/publishing content is a lead/admin curation task, matching how
    # ticket.assign/ticket.reopen are lead+admin-only elsewhere in this table.
    "kb_article.read": ("عرض مقالات قاعدة المعرفة", "View KB Articles", ["agent", "lead", "admin"]),
    "kb_article.create": ("إنشاء/تعديل مقالات قاعدة المعرفة", "Create/Edit KB Articles", ["lead", "admin"]),
    "kb_article.publish": ("نشر مقالات قاعدة المعرفة", "Publish KB Articles", ["lead", "admin"]),
}


async def seed_roles(session: AsyncSession) -> None:
    rows = [
        dict(id=ROLE_IDS[code], code=code, label_ar=ar, label_en=en)
        for code, (ar, en) in ROLE_LABELS.items()
    ]
    await upsert(session, Role, rows)


async def seed_permissions(session: AsyncSession) -> dict[str, uuid.UUID]:
    perm_ids = {code: sid("permission", code) for code in PERMISSIONS}
    rows = [
        dict(id=perm_ids[code], code=code, label_ar=ar, label_en=en)
        for code, (ar, en, _roles) in PERMISSIONS.items()
    ]
    await upsert(session, Permission, rows)

    rp_rows = [
        dict(
            id=sid("role_permission", role_code, code),
            role_id=ROLE_IDS[role_code],
            permission_id=perm_ids[code],
        )
        for code, (_ar, _en, roles) in PERMISSIONS.items()
        for role_code in roles
    ]
    await upsert(session, RolePermission, rp_rows)
    return perm_ids


# --------------------------------------------------------------------------------------------
# Users / user_roles
# --------------------------------------------------------------------------------------------

SEED_PASSWORD = "ChangeMe#2026"  # dev/demo seed only — see quickstart.md §4

USERS = [
    dict(
        key="admin", email="admin@azm-crm.example",
        full_name_ar="مدير النظام", full_name_en="System Administrator",
        branch_id=BRANCH_A_ID, department_id=None, locale="ar", role="admin",
        assignments=[
            (BRANCH_A_ID, DEPT_CAI_SUPPORT_ID),
            (BRANCH_A_ID, DEPT_CAI_SALES_ID),
            (BRANCH_B_ID, DEPT_RUH_SUPPORT_ID),
        ],
    ),
    dict(
        key="lead", email="mona.elsherif@azm-crm.example",
        full_name_ar="منى الشريف", full_name_en="Mona El-Sherif",
        branch_id=BRANCH_A_ID, department_id=DEPT_CAI_SUPPORT_ID, locale="ar", role="lead",
        assignments=[(BRANCH_A_ID, DEPT_CAI_SUPPORT_ID)],
    ),
    dict(
        key="agent_cai_support", email="ahmed.hassan@azm-crm.example",
        full_name_ar="أحمد حسن", full_name_en="Ahmed Hassan",
        branch_id=BRANCH_A_ID, department_id=DEPT_CAI_SUPPORT_ID, locale="ar", role="agent",
        assignments=[(BRANCH_A_ID, DEPT_CAI_SUPPORT_ID)],
    ),
    dict(
        key="agent_cai_sales", email="layla.mahmoud@azm-crm.example",
        full_name_ar="ليلى محمود", full_name_en="Layla Mahmoud",
        branch_id=BRANCH_A_ID, department_id=DEPT_CAI_SALES_ID, locale="ar", role="agent",
        assignments=[(BRANCH_A_ID, DEPT_CAI_SALES_ID)],
    ),
    dict(
        key="agent_ruh_support", email="khalid.alotaibi@azm-crm.example",
        full_name_ar="خالد العتيبي", full_name_en="Khalid Al-Otaibi",
        branch_id=BRANCH_B_ID, department_id=DEPT_RUH_SUPPORT_ID, locale="ar", role="agent",
        assignments=[(BRANCH_B_ID, DEPT_RUH_SUPPORT_ID)],
    ),
]
USER_IDS = {u["key"]: sid("user", u["key"]) for u in USERS}


async def seed_users(session: AsyncSession) -> None:
    password_hash = hash_password(SEED_PASSWORD)
    rows = [
        dict(
            id=USER_IDS[u["key"]], branch_id=u["branch_id"], department_id=u["department_id"],
            email=u["email"], password_hash=password_hash,
            full_name_ar=u["full_name_ar"], full_name_en=u["full_name_en"],
            phone=None, locale=u["locale"], is_active=True,
        )
        for u in USERS
    ]
    await upsert(session, User, rows)

    ur_rows = [
        dict(
            id=sid("user_role", u["key"], str(branch_id), str(dept_id)),
            branch_id=branch_id, department_id=dept_id,
            user_id=USER_IDS[u["key"]], role_id=ROLE_IDS[u["role"]],
        )
        for u in USERS
        for branch_id, dept_id in u["assignments"]
    ]
    await upsert(session, UserRole, ur_rows)


# --------------------------------------------------------------------------------------------
# Categories — 3-level tree, seeded once per branch (S2, see module docstring)
# --------------------------------------------------------------------------------------------

def _category_rows(branch_id: uuid.UUID, prefix: str) -> tuple[list[dict], dict[str, uuid.UUID]]:
    ids = {
        "tech": sid("category", prefix, "tech"),
        "login": sid("category", prefix, "tech", "login"),
        "password": sid("category", prefix, "tech", "login", "password"),
        "billing": sid("category", prefix, "billing"),
        "refund": sid("category", prefix, "billing", "refund"),
        "general": sid("category", prefix, "general"),
    }
    rows = [
        dict(id=ids["tech"], branch_id=branch_id, department_id=None, parent_id=None,
             label_ar="المشاكل التقنية", label_en="Technical Issues", is_active=True, sort_order=1),
        dict(id=ids["login"], branch_id=branch_id, department_id=None, parent_id=ids["tech"],
             label_ar="مشاكل تسجيل الدخول", label_en="Login Issues", is_active=True, sort_order=1),
        dict(id=ids["password"], branch_id=branch_id, department_id=None, parent_id=ids["login"],
             label_ar="نسيان كلمة المرور", label_en="Forgotten Password", is_active=True, sort_order=1),
        dict(id=ids["billing"], branch_id=branch_id, department_id=None, parent_id=None,
             label_ar="الفواتير والمدفوعات", label_en="Billing & Payments", is_active=True, sort_order=2),
        dict(id=ids["refund"], branch_id=branch_id, department_id=None, parent_id=ids["billing"],
             label_ar="استرداد الأموال", label_en="Refunds", is_active=True, sort_order=1),
        dict(id=ids["general"], branch_id=branch_id, department_id=None, parent_id=None,
             label_ar="استفسارات عامة", label_en="General Inquiries", is_active=True, sort_order=3),
    ]
    return rows, ids


async def seed_categories(session: AsyncSession) -> dict[str, dict[str, uuid.UUID]]:
    rows_a, ids_a = _category_rows(BRANCH_A_ID, "cai")
    rows_b, ids_b = _category_rows(BRANCH_B_ID, "ruh")
    await upsert(session, Category, rows_a + rows_b)
    return {"CAI": ids_a, "RUH": ids_b}


# --------------------------------------------------------------------------------------------
# Priorities — seeded once per branch (S2, see module docstring)
# --------------------------------------------------------------------------------------------

PRIORITY_DEFS = [
    ("urgent", "حرجة", "Critical", 1, "#dc2626"),
    ("high", "عالية", "High", 2, "#ea580c"),
    ("medium", "متوسطة", "Medium", 3, "#ca8a04"),
    ("low", "منخفضة", "Low", 4, "#16a34a"),
]


def _priority_rows(branch_id: uuid.UUID, prefix: str) -> tuple[list[dict], dict[str, uuid.UUID]]:
    ids = {code: sid("priority", prefix, code) for code, *_ in PRIORITY_DEFS}
    rows = [
        dict(id=ids[code], branch_id=branch_id, department_id=None, code=code,
             severity=severity, color=color, label_ar=ar, label_en=en)
        for code, ar, en, severity, color in PRIORITY_DEFS
    ]
    return rows, ids


async def seed_priorities(session: AsyncSession) -> dict[str, dict[str, uuid.UUID]]:
    rows_a, ids_a = _priority_rows(BRANCH_A_ID, "cai")
    rows_b, ids_b = _priority_rows(BRANCH_B_ID, "ruh")
    await upsert(session, Priority, rows_a + rows_b)
    return {"CAI": ids_a, "RUH": ids_b}


# --------------------------------------------------------------------------------------------
# Ticket statuses + the full status_transitions table — seeded once per branch, department=NULL
# default workflow (data-model.md §4)
# --------------------------------------------------------------------------------------------

STATUS_DEFS = [
    ("new", "جديدة", "New", False, False, 1),
    ("open", "مفتوحة", "Open", False, False, 2),
    ("in_progress", "قيد المعالجة", "In Progress", False, False, 3),
    ("pending_customer", "بانتظار العميل", "Pending Customer", False, True, 4),
    ("resolved", "تم الحل", "Resolved", False, False, 5),
    ("closed", "مغلقة", "Closed", True, False, 6),
    ("reopened", "أعيد فتحها", "Reopened", False, False, 7),
]

TRANSITION_DEFS = [
    ("new", "open", False, None),
    ("new", "in_progress", False, None),
    ("new", "closed", True, None),
    ("open", "in_progress", False, None),
    ("open", "pending_customer", False, None),
    ("open", "resolved", False, None),
    ("open", "closed", False, None),
    ("in_progress", "open", False, None),
    ("in_progress", "pending_customer", False, None),
    ("in_progress", "resolved", False, None),
    ("pending_customer", "in_progress", False, None),
    ("pending_customer", "resolved", False, None),
    ("pending_customer", "closed", False, None),
    ("resolved", "closed", False, None),
    ("resolved", "reopened", False, "ticket.reopen"),
    ("closed", "reopened", False, "ticket.reopen"),
    ("reopened", "in_progress", False, None),
    ("reopened", "resolved", False, None),
]


def _status_rows(branch_id: uuid.UUID, prefix: str) -> tuple[list[dict], dict[str, uuid.UUID]]:
    ids = {code: sid("status", prefix, code) for code, *_ in STATUS_DEFS}
    rows = [
        dict(id=ids[code], branch_id=branch_id, department_id=None, code=code,
             is_terminal=terminal, pauses_sla=pauses, sort_order=order, label_ar=ar, label_en=en)
        for code, ar, en, terminal, pauses, order in STATUS_DEFS
    ]
    return rows, ids


def _transition_rows(
    branch_id: uuid.UUID, prefix: str, status_ids: dict[str, uuid.UUID]
) -> list[dict]:
    return [
        dict(
            id=sid("transition", prefix, from_code, to_code),
            branch_id=branch_id, department_id=None,
            from_status_id=status_ids[from_code], to_status_id=status_ids[to_code],
            required_permission=required_permission, requires_reason=requires_reason,
        )
        for from_code, to_code, requires_reason, required_permission in TRANSITION_DEFS
    ]


async def seed_statuses_and_transitions(session: AsyncSession) -> dict[str, dict[str, uuid.UUID]]:
    rows_a, ids_a = _status_rows(BRANCH_A_ID, "cai")
    rows_b, ids_b = _status_rows(BRANCH_B_ID, "ruh")
    await upsert(session, TicketStatus, rows_a + rows_b)

    t_rows = _transition_rows(BRANCH_A_ID, "cai", ids_a) + _transition_rows(BRANCH_B_ID, "ruh", ids_b)
    await upsert(session, StatusTransition, t_rows)
    return {"CAI": ids_a, "RUH": ids_b}


# --------------------------------------------------------------------------------------------
# SLA policies (3, branch A only — a demo-path asset, see module docstring)
# --------------------------------------------------------------------------------------------

async def seed_sla_policies(
    session: AsyncSession,
    category_ids: dict[str, dict[str, uuid.UUID]],
    priority_ids: dict[str, dict[str, uuid.UUID]],
) -> dict[str, uuid.UUID]:
    cai_cat = category_ids["CAI"]
    cai_pri = priority_ids["CAI"]
    defs = {
        "urgent": dict(
            id=sid("sla", "urgent-default"), branch_id=BRANCH_A_ID, department_id=None,
            category_id=None, priority_id=cai_pri["urgent"],
            first_response_minutes=15, resolution_minutes=120, business_hours_only=False,
            label_ar="سياسة الأولوية الحرجة", label_en="Critical Priority Policy",
        ),
        "standard": dict(
            id=sid("sla", "standard-default"), branch_id=BRANCH_A_ID, department_id=None,
            category_id=None, priority_id=None,
            first_response_minutes=60, resolution_minutes=1440, business_hours_only=True,
            label_ar="السياسة القياسية", label_en="Standard Policy",
        ),
        "refund": dict(
            id=sid("sla", "billing-refund"), branch_id=BRANCH_A_ID, department_id=None,
            category_id=cai_cat["refund"], priority_id=None,
            first_response_minutes=30, resolution_minutes=480, business_hours_only=True,
            label_ar="سياسة استرداد الأموال", label_en="Refund Policy",
        ),
    }
    await upsert(session, SlaPolicy, list(defs.values()))
    return {key: row["id"] for key, row in defs.items()}


# --------------------------------------------------------------------------------------------
# Quick replies (8, branch A / Customer Support only — a demo-path asset)
# --------------------------------------------------------------------------------------------

QUICK_REPLY_DEFS = [
    ("greeting", "الترحيب بالعميل", "Customer Greeting",
     "مرحباً {{customer_name}}، شكراً لتواصلك معنا. رقم تذكرتك هو {{reference_no}} وسنقوم بالرد "
     "عليك في أقرب وقت.",
     "Hello {{customer_name}}, thank you for contacting us. Your ticket reference is "
     "{{reference_no}} and we will respond shortly."),
    ("ack", "تأكيد الاستلام", "Acknowledge Receipt",
     "تم استلام طلبك بخصوص التذكرة {{reference_no}} وجاري العمل عليه من قبل {{agent_name}}.",
     "We have received your request for ticket {{reference_no}} and {{agent_name}} is now "
     "working on it."),
    ("more_info", "طلب مزيد من المعلومات", "Request More Info",
     "مرحباً {{customer_name}}، هل يمكنك تزويدنا بمزيد من التفاصيل حول المشكلة لمساعدتك بشكل أفضل؟",
     "Hello {{customer_name}}, could you provide more details about the issue so we can assist "
     "you better?"),
    ("resolved", "إشعار الحل", "Resolution Notice",
     "مرحباً {{customer_name}}، تم حل التذكرة {{reference_no}}. نأمل أن تكون راضياً عن الخدمة.",
     "Hello {{customer_name}}, ticket {{reference_no}} has been resolved. We hope you are "
     "satisfied with our service."),
    ("escalate", "إشعار التصعيد", "Escalation Notice",
     "تم تصعيد التذكرة {{reference_no}} إلى فريق مختص وسيتواصل معك {{agent_name}} قريباً.",
     "Ticket {{reference_no}} has been escalated to a specialist team and {{agent_name}} will "
     "follow up soon."),
    ("delay", "اعتذار عن التأخير", "Delay Apology",
     "نعتذر عن التأخير في الرد على التذكرة {{reference_no}}، ونعمل حالياً على حل المشكلة.",
     "We apologize for the delay in responding to ticket {{reference_no}}; we are actively "
     "working on a resolution."),
    ("closing", "إغلاق التذكرة", "Closing Ticket",
     "مرحباً {{customer_name}}، سيتم إغلاق التذكرة {{reference_no}} الآن. لا تتردد في التواصل "
     "معنا لأي استفسار آخر.",
     "Hello {{customer_name}}, ticket {{reference_no}} will now be closed. Feel free to reach "
     "out for any further questions."),
    ("thanks", "شكر العميل", "Thank the Customer",
     "شكراً لك {{customer_name}} على صبرك وتعاونك معنا في التذكرة {{reference_no}}.",
     "Thank you {{customer_name}} for your patience and cooperation on ticket {{reference_no}}."),
]


async def seed_quick_replies(session: AsyncSession) -> None:
    rows = [
        dict(
            id=sid("quick_reply", code), branch_id=BRANCH_A_ID, department_id=DEPT_CAI_SUPPORT_ID,
            body_ar=body_ar, body_en=body_en, category_id=None, label_ar=label_ar, label_en=label_en,
        )
        for code, label_ar, label_en, body_ar, body_en in QUICK_REPLY_DEFS
    ]
    await upsert(session, QuickReply, rows)


# --------------------------------------------------------------------------------------------
# Channel configs (2, one per branch's support department)
# --------------------------------------------------------------------------------------------

async def seed_channel_configs(
    session: AsyncSession, category_ids: dict[str, dict[str, uuid.UUID]]
) -> None:
    rows = [
        dict(
            id=sid("channel_config", "cai-email"), branch_id=BRANCH_A_ID,
            department_id=DEPT_CAI_SUPPORT_ID, channel="email",
            identifier="support@azm-crm.example",
            default_category_id=category_ids["CAI"]["general"], is_active=True,
        ),
        dict(
            id=sid("channel_config", "ruh-email"), branch_id=BRANCH_B_ID,
            department_id=DEPT_RUH_SUPPORT_ID, channel="email",
            identifier="support-ksa@azm-crm.example",
            default_category_id=category_ids["RUH"]["general"], is_active=True,
        ),
    ]
    await upsert(session, ChannelConfig, rows)


# --------------------------------------------------------------------------------------------
# Customers (20, bilingual, split 7 / 7 / 6 across the three departments) + contact methods
# --------------------------------------------------------------------------------------------

DEPT_BY_KEY = {
    "CAI_SUPPORT": (BRANCH_A_ID, DEPT_CAI_SUPPORT_ID),
    "CAI_SALES": (BRANCH_A_ID, DEPT_CAI_SALES_ID),
    "RUH_SUPPORT": (BRANCH_B_ID, DEPT_RUH_SUPPORT_ID),
}

# (full_name_ar, full_name_en, customer_type, organization_name_ar|None, phone, preferred_locale, dept_key)
CUSTOMERS = [
    ("أحمد عبد الله السيد", "Ahmed Abdullah El-Sayed", "individual", None, "+20 100 111 2223", "ar", "CAI_SUPPORT"),
    ("فاطمة محمود حسن", "Fatma Mahmoud Hassan", "individual", None, "+20 100 222 3334", "ar", "CAI_SUPPORT"),
    ("محمد إبراهيم يوسف", "Mohamed Ibrahim Youssef", "individual", None, "+20 100 333 4445", "ar", "CAI_SUPPORT"),
    ("مريم علي عبد الرحمن", "Mariam Ali Abdel Rahman", "individual", None, "+20 100 444 5556", "ar", "CAI_SUPPORT"),
    ("يوسف كريم الشريف", "Youssef Karim El-Sherif", "individual", None, "+20 100 555 6667", "en", "CAI_SUPPORT"),
    ("نور الهدى طارق", "Nour El-Huda Tarek", "individual", None, "+20 100 666 7778", "ar", "CAI_SUPPORT"),
    ("عمر سامي النجار", "Omar Sami El-Naggar", "individual", None, "+20 100 777 8889", "ar", "CAI_SUPPORT"),
    ("سارة حسام الدين", "Sara Hossam El-Din", "individual", None, "+20 101 111 2223", "ar", "CAI_SALES"),
    ("خالد فؤاد رمضان", "Khaled Fouad Ramadan", "individual", None, "+20 101 222 3334", "ar", "CAI_SALES"),
    ("هدى عاطف الجندي", "Hoda Atef El-Gendy", "individual", None, "+20 101 333 4445", "en", "CAI_SALES"),
    ("إبراهيم عادل قاسم", "Ibrahim Adel Kassem", "individual", None, "+20 101 444 5556", "ar", "CAI_SALES"),
    ("ليلى منصور فهمي", "Layla Mansour Fahmy", "individual", None, "+20 101 555 6667", "ar", "CAI_SALES"),
    ("شركة النور للتجارة", "Al-Nour Trading Company", "organization", "شركة النور للتجارة", "+20 101 666 7778", "ar", "CAI_SALES"),
    ("مؤسسة الأمل للخدمات", "Al-Amal Services Establishment", "organization", "مؤسسة الأمل للخدمات", "+20 101 777 8889", "ar", "CAI_SALES"),
    ("حسن سالم القحطاني", "Hassan Salem Al-Qahtani", "individual", None, "+966 50 111 2223", "ar", "RUH_SUPPORT"),
    ("رنا فيصل الدوسري", "Rana Faisal Al-Dosari", "individual", None, "+966 50 222 3334", "ar", "RUH_SUPPORT"),
    ("طارق ناصر الحربي", "Tarek Nasser Al-Harbi", "individual", None, "+966 50 333 4445", "en", "RUH_SUPPORT"),
    ("دينا وليد المطيري", "Dina Walid Al-Mutairi", "individual", None, "+966 50 444 5556", "ar", "RUH_SUPPORT"),
    ("ياسر عبد العزيز الشمري", "Yasser Abdulaziz Al-Shammari", "individual", None, "+966 50 555 6667", "ar", "RUH_SUPPORT"),
    ("ندى سعيد العنزي", "Nada Saeed Al-Anzi", "individual", None, "+966 50 666 7778", "ar", "RUH_SUPPORT"),
]


def _customer_email(full_name_en: str) -> str:
    return full_name_en.lower().replace(" ", ".").replace("-", "") + "@example.com"


async def seed_customers(session: AsyncSession) -> dict[str, list[dict]]:
    cust_rows = []
    contact_rows = []
    grouped: dict[str, list[dict]] = {"CAI": [], "RUH": []}

    for idx, (name_ar, name_en, ctype, org_ar, phone, locale, dept_key) in enumerate(CUSTOMERS):
        cust_id = sid("customer", str(idx))
        branch_id, department_id = DEPT_BY_KEY[dept_key]
        cust_rows.append(dict(
            id=cust_id, branch_id=branch_id, department_id=department_id,
            customer_type=ctype, full_name_ar=name_ar, full_name_en=name_en,
            national_id=None, organization_name=org_ar, preferred_locale=locale,
            notes=None, is_active=True,
        ))
        contact_rows.append(dict(
            id=sid("contact", str(idx), "phone"), customer_id=cust_id,
            kind="phone", value=phone, is_primary=True, is_verified=True,
        ))
        contact_rows.append(dict(
            id=sid("contact", str(idx), "email"), customer_id=cust_id,
            kind="email", value=_customer_email(name_en), is_primary=False, is_verified=False,
        ))
        branch_key = "CAI" if branch_id == BRANCH_A_ID else "RUH"
        grouped[branch_key].append({"id": cust_id, "department_id": department_id})

    await upsert(session, Customer, cust_rows)
    await upsert(session, ContactMethod, contact_rows)
    return grouped


# --------------------------------------------------------------------------------------------
# Knowledge base articles (10 — 5 topics x 2 branches, fully bilingual, published)
# --------------------------------------------------------------------------------------------

# (slug, title_ar, title_en, body_ar, body_en, category leaf key)
KB_TOPICS = [
    ("password-reset", "كيفية إعادة تعيين كلمة المرور", "How to Reset Your Password",
     "لإعادة تعيين كلمة المرور، انتقل إلى صفحة تسجيل الدخول واضغط على رابط نسيت كلمة المرور، ثم "
     "اتبع التعليمات المرسلة إلى بريدك الإلكتروني المسجل.",
     "To reset your password, go to the login page and click Forgot Password, then follow the "
     "instructions sent to your registered email address.",
     "password"),
    ("monthly-invoice", "فهم فاتورتك الشهرية", "Understanding Your Monthly Invoice",
     "توضح هذه المقالة كيفية قراءة بنود الفاتورة الشهرية والتعرف على الرسوم الأساسية والإضافية.",
     "This article explains how to read your monthly invoice line items and identify base and "
     "additional charges.",
     "general"),
    ("refund-policy", "سياسة استرداد الأموال", "Our Refund Policy",
     "يمكن استرداد المبالغ المدفوعة خلال أربعة عشر يوماً من تاريخ الدفع بشرط تقديم طلب عبر التذاكر.",
     "Payments can be refunded within fourteen days of the payment date, provided a request is "
     "submitted via a support ticket.",
     "refund"),
    ("app-unresponsive", "حل مشكلة عدم استجابة تطبيق الجوال", "Fixing an Unresponsive Mobile App",
     "إذا توقف التطبيق عن الاستجابة، أغلقه تماماً ثم أعد فتحه، وتأكد من تحديثه إلى أحدث إصدار متاح.",
     "If the app becomes unresponsive, close it completely and reopen it, and make sure it is "
     "updated to the latest available version.",
     "password"),
    ("subscription-plans", "البدء السريع مع خطط الاشتراك", "Getting Started with Subscription Plans",
     "تقدم هذه المقالة نظرة عامة على خطط الاشتراك المتاحة والفروقات بينها لمساعدتك على اختيار "
     "الأنسب.",
     "This article gives an overview of the available subscription plans and their differences "
     "to help you choose the right one.",
     "general"),
]


async def seed_kb_articles(
    session: AsyncSession, category_ids: dict[str, dict[str, uuid.UUID]]
) -> None:
    rows = [
        dict(
            id=sid("kb", branch_key, slug), branch_id=branch_id, department_id=None, slug=slug,
            title_ar=title_ar, title_en=title_en, body_ar=body_ar, body_en=body_en,
            category_id=category_ids[branch_key][leaf_key],
            is_published=True, view_count=0, helpful_count=0,
        )
        for branch_id, branch_key in ((BRANCH_A_ID, "CAI"), (BRANCH_B_ID, "RUH"))
        for slug, title_ar, title_en, body_ar, body_en, leaf_key in KB_TOPICS
    ]
    await upsert(session, KbArticle, rows)


async def seed_kb_article_embeddings(session: AsyncSession) -> None:
    """F06 (Batch 4g) backfill — the 10 articles `seed_kb_articles` just wrote were inserted
    directly via `upsert()`, bypassing `KbService.create_article`, so they carry no
    `kb_article_chunks` of their own. This chunks (~500 tokens/50 overlap, `KB_CHUNK_TOKENS`/
    `KB_CHUNK_OVERLAP_TOKENS`) and embeds (fixed `BAAI/bge-m3`, `EMBEDDING_MODEL`) every published
    article that doesn't already have chunks, so the batch 4g gate — a bilingual query against
    the seeded set — has real semantic-half data to search, not lexical-only.

    Skipped per-article, not just on `ON CONFLICT DO NOTHING` at insert time: a second run must
    not re-invoke the embedding model at all for an article already chunked (T137's idempotency
    check is about row counts, but re-embedding 10 articles' worth of chunks on every seed run
    would make `docker compose exec backend python -m app.seed.seed` needlessly slow to re-run).
    If the embedding model itself is unavailable (not yet downloaded, no matching device, etc.),
    seeding still completes — search then falls back to lexical-only until it is (FR-043)."""

    result = await session.execute(select(KbArticle).where(KbArticle.is_published.is_(True)))
    articles = list(result.scalars().all())
    if not articles:
        return

    already_chunked_result = await session.execute(select(KbArticleChunk.kb_article_id).distinct())
    already_chunked = {row[0] for row in already_chunked_result.all()}
    pending = [article for article in articles if article.id not in already_chunked]
    if not pending:
        print("[seed] kb_article_chunks already populated for every published article — skipping.")
        return

    try:
        model = get_embedding_model()
    except Exception as exc:  # noqa: BLE001 — seeding must still complete without embeddings
        print(f"[seed] embedding model unavailable, skipping kb_article_chunks backfill: {exc}")
        return

    rows: list[dict] = []
    for article in pending:
        for locale, body in (("ar", article.body_ar), ("en", article.body_en)):
            chunks = chunk_text(body, settings.KB_CHUNK_TOKENS, settings.KB_CHUNK_OVERLAP_TOKENS)
            if not chunks:
                continue
            try:
                vectors = model.embed(chunks)
            except Exception as exc:  # noqa: BLE001 — same rationale, scoped to one article/locale
                print(f"[seed] embedding failed for article {article.id} ({locale}): {exc}")
                continue
            for index, (content, vector) in enumerate(zip(chunks, vectors)):
                rows.append(
                    dict(
                        id=sid("kb_chunk", str(article.id), locale, str(index)),
                        kb_article_id=article.id,
                        locale=locale,
                        chunk_index=index,
                        content=content,
                        embedding=vector,
                        created_by=article.created_by,
                    )
                )
    await upsert(session, KbArticleChunk, rows)
    print(f"[seed] kb_article_chunks: {len(rows)} chunk(s) embedded for {len(pending)} article(s).")


# --------------------------------------------------------------------------------------------
# Tickets (40, spread across every status/priority/channel; some pre-breaching)
# --------------------------------------------------------------------------------------------

CHANNELS = ["web", "email", "whatsapp", "sms", "chat", "portal"]

# (subject_ar, description_ar, subject_en, description_en, category leaf key)
TICKET_TEMPLATES = [
    ("لا أستطيع تسجيل الدخول إلى حسابي",
     "حاولت تسجيل الدخول عدة مرات ولكن يظهر لي خطأ في اسم المستخدم أو كلمة المرور رغم أنني متأكد "
     "من صحتهما.",
     "Unable to log into my account",
     "I have tried logging in multiple times but keep getting an invalid username or password "
     "error even though I am sure they are correct.",
     "password"),
    ("نسيت كلمة المرور الخاصة بحسابي",
     "لم أتلقَّ رسالة إعادة تعيين كلمة المرور على بريدي الإلكتروني بعد تقديم الطلب.",
     "Forgot my account password",
     "I did not receive the password reset email after submitting the request.",
     "password"),
    ("استفسار بخصوص الفاتورة الشهرية",
     "لاحظت رسوماً إضافية على فاتورتي هذا الشهر ولا أعرف سببها.",
     "Question about my monthly invoice",
     "I noticed extra charges on this month's invoice and I am not sure what they are for.",
     "general"),
    ("طلب استرداد مبلغ مدفوع بالخطأ",
     "قمت بالدفع مرتين عن طريق الخطأ وأرغب في استرداد المبلغ الزائد.",
     "Request a refund for a duplicate payment",
     "I was charged twice by mistake and would like the extra amount refunded.",
     "refund"),
    ("الخدمة متوقفة عن العمل منذ الصباح",
     "لا يمكنني الوصول إلى لوحة التحكم منذ عدة ساعات ولا أعرف السبب.",
     "Service has been down since this morning",
     "I have not been able to access the dashboard for several hours and do not know why.",
     "general"),
    ("استفسار عام حول خطط الاشتراك",
     "أرغب في معرفة الفروقات بين خطط الاشتراك المتاحة قبل الترقية.",
     "General inquiry about subscription plans",
     "I would like to understand the differences between the available subscription plans "
     "before upgrading.",
     "general"),
    ("التطبيق يتوقف عن الاستجابة على الهاتف",
     "يتجمد تطبيق الجوال عند فتح صفحة التذاكر ولا يستجيب لأي لمسة.",
     "Mobile app freezes on my phone",
     "The mobile app freezes when I open the tickets page and does not respond to any taps.",
     "password"),
    ("تحديث بيانات الحساب",
     "أرغب في تغيير رقم الهاتف المسجل على حسابي إلى رقم جديد.",
     "Update my account information",
     "I would like to change the phone number registered on my account to a new one.",
     "general"),
    ("شكوى بخصوص بطء الرد على التذاكر السابقة",
     "لم أتلقَّ أي رد على تذكرتي السابقة منذ أكثر من ثلاثة أيام.",
     "Complaint about slow response time",
     "I have not received any reply to my previous ticket for more than three days.",
     "general"),
    ("شكر مع استفسار بسيط",
     "أشكركم على الخدمة الممتازة، ولدي سؤال بسيط حول كيفية تنزيل الفاتورة كملف PDF.",
     "Thanks, with a small question",
     "Thank you for the excellent service; I have a small question about how to download the "
     "invoice as a PDF.",
     "refund"),
]


# A ticket's event history (F02: the timeline IS the ticket's history — every mutation must
# leave a record, so a terminal status with no events behind it is inconsistent seed data) is
# derived from a fixed, legal path through `status_transitions` (data-model.md §4) from "new" to
# the ticket's current status — never an ad hoc shape independent of the workflow graph.
TRANSITION_LOOKUP = {
    (from_code, to_code): (requires_reason, required_permission)
    for from_code, to_code, requires_reason, required_permission in TRANSITION_DEFS
}
JOURNEYS: dict[str, list[tuple[str, str]]] = {
    "new": [],
    "open": [("new", "open")],
    "in_progress": [("new", "open"), ("open", "in_progress")],
    "pending_customer": [("new", "open"), ("open", "in_progress"), ("in_progress", "pending_customer")],
    "resolved": [("new", "open"), ("open", "in_progress"), ("in_progress", "resolved")],
    "closed": [
        ("new", "open"), ("open", "in_progress"), ("in_progress", "resolved"), ("resolved", "closed"),
    ],
    "reopened": [
        ("new", "open"), ("open", "in_progress"), ("in_progress", "resolved"),
        ("resolved", "closed"), ("closed", "reopened"),
    ],
}
# A ticket may only reach "pre-breaching" (no response yet, deliberately overdue) from a
# non-terminal, non-reopened status — a closed/reopened ticket's resolved_at/closed_at reflect
# real history and must not be nulled out just to simulate a breach.
BREACH_ELIGIBLE_STATUSES = {"open", "in_progress", "pending_customer"}

DEPT_AGENT_KEY = {
    DEPT_CAI_SUPPORT_ID: "agent_cai_support",
    DEPT_CAI_SALES_ID: "agent_cai_sales",
    DEPT_RUH_SUPPORT_ID: "agent_ruh_support",
}

NOTE_BODIES = [
    ("تمت مراجعة التذكرة داخلياً، بانتظار مزيد من المعلومات من العميل قبل المتابعة.",
     "Ticket reviewed internally; awaiting further information from the customer before proceeding."),
    ("تم التحقق من تفاصيل الحساب ولا توجد ملاحظات إضافية حتى الآن.",
     "Account details have been verified; no additional notes at this time."),
]
REPLY_BODIES = [
    ("شكراً لتواصلك معنا. لقد بدأنا العمل على طلبك وسنوافيك بالتحديثات أولاً بأول.",
     "Thank you for reaching out. We have started working on your request and will keep you updated."),
    ("نعتذر عن الإزعاج، تم تحويل طلبك إلى الفريق المختص لمتابعته.",
     "We apologize for the inconvenience; your request has been forwarded to the specialist team "
     "for follow-up."),
]


def _event(
    *, id: uuid.UUID, ticket_id: uuid.UUID, actor_id: uuid.UUID, event_type: str,
    visibility: str, correlation_id: uuid.UUID, created_at: datetime,
    old_value: dict | None = None, new_value: dict | None = None, body: str | None = None,
) -> dict:
    """Every `TicketEvent` row needs the identical key set — SQLAlchemy's multi-row
    `.values([...])` builds one column list from the batch, so a dict missing a key silently
    misaligns the row rather than inserting NULL for it."""

    return dict(
        id=id, ticket_id=ticket_id, actor_id=actor_id, event_type=event_type,
        field_name=None, old_value=old_value, new_value=new_value, body=body,
        visibility=visibility, reason=None, correlation_id=correlation_id, created_at=created_at,
    )


async def seed_tickets(
    session: AsyncSession,
    status_ids: dict[str, dict[str, uuid.UUID]],
    priority_ids: dict[str, dict[str, uuid.UUID]],
    category_ids: dict[str, dict[str, uuid.UUID]],
    customers: dict[str, list[dict]],
) -> None:
    now = datetime.now(UTC)
    status_cycle = [code for code, *_ in STATUS_DEFS]
    priority_cycle = [code for code, *_ in PRIORITY_DEFS]
    # Same resolution order SlaService.resolve_policy uses for a real POST /tickets (exact
    # category+priority -> priority-only -> category-only -> default) — reused directly, not
    # reimplemented, so seeded tickets are never resolved by a second, silently-divergent copy
    # of this logic. RUH (branch B) has no seeded sla_policies rows at all (PLAN.md §7: 3 total,
    # a demo-path asset against branch A only) so every RUH ticket legitimately resolves to None.
    sla_service = SlaService(session, TenantScope(branch_id=None, department_id=None, cross_branch=True))

    rows = []
    event_rows = []
    breach_eligible_seen = 0
    for i in range(40):
        subj_ar, desc_ar, subj_en, desc_en, leaf_key = TICKET_TEMPLATES[i % len(TICKET_TEMPLATES)]
        is_ar = i % 2 == 0
        status_code = status_cycle[i % len(status_cycle)]
        priority_code = priority_cycle[i % len(priority_cycle)]
        channel = CHANNELS[i % len(CHANNELS)]

        pre_breaching = False
        if status_code in BREACH_ELIGIBLE_STATUSES:
            breach_eligible_seen += 1
            pre_breaching = breach_eligible_seen % 4 == 0

        if i < 28:
            branch_key, branch_id = "CAI", BRANCH_A_ID
            customer = customers["CAI"][i % len(customers["CAI"])]
        else:
            branch_key, branch_id = "RUH", BRANCH_B_ID
            customer = customers["RUH"][(i - 28) % len(customers["RUH"])]

        ticket_id = sid("ticket", str(i))
        agent_id = USER_IDS[DEPT_AGENT_KEY[customer["department_id"]]]
        reopen_actor_id = USER_IDS["lead"] if branch_key == "CAI" else USER_IDS["admin"]

        created_at = now - (timedelta(days=6) if pre_breaching else timedelta(hours=i + 1))
        is_progressed = status_code != "new"
        # A reopened ticket was, historically, resolved and closed — reopening never clears those
        # timestamps (TicketTransitionService.change_status never touches them either).
        is_done = status_code in ("resolved", "closed", "reopened")

        first_response_at = (
            None if (pre_breaching or not is_progressed) else created_at + timedelta(minutes=45)
        )
        resolved_at = created_at + timedelta(hours=6) if is_done and not pre_breaching else None
        closed_at = (
            created_at + timedelta(hours=8)
            if status_code in ("closed", "reopened") and not pre_breaching
            else None
        )

        department_id = customer["department_id"]
        category_id = category_ids[branch_key][leaf_key]
        priority_id = priority_ids[branch_key][priority_code]
        resolved_policy = await sla_service.resolve_policy(
            branch_id, department_id, category_id, priority_id
        )
        sla_policy_id = resolved_policy.id if resolved_policy is not None else None

        rows.append(dict(
            id=ticket_id,
            branch_id=branch_id, department_id=department_id,
            reference_no=f"TKT-{now.year}-{i + 1:06d}",
            customer_id=customer["id"],
            subject=subj_ar if is_ar else subj_en,
            description=desc_ar if is_ar else desc_en,
            category_id=category_id,
            priority_id=priority_id,
            status_id=status_ids[branch_key][status_code],
            assignee_id=agent_id if is_progressed else None,
            channel=channel,
            source_locale="ar" if is_ar else "en",
            sla_policy_id=sla_policy_id,
            first_response_at=first_response_at,
            resolved_at=resolved_at,
            closed_at=closed_at,
            reopened_count=1 if status_code == "reopened" else 0,
            created_at=created_at,
        ))

        ticket_key = str(i)
        seq = 0

        def _corr(n: int, _ticket_key: str = ticket_key) -> uuid.UUID:
            return sid("event", "correlation", _ticket_key, str(n))

        event_rows.append(_event(
            id=sid("event", ticket_key, "created"), ticket_id=ticket_id, actor_id=agent_id,
            event_type="created", visibility="customer", correlation_id=_corr(seq),
            created_at=created_at,
        ))
        seq += 1

        if is_progressed:
            event_rows.append(_event(
                id=sid("event", ticket_key, "assigned"), ticket_id=ticket_id, actor_id=agent_id,
                event_type="assigned", new_value={"assignee_id": str(agent_id)},
                visibility="internal", correlation_id=_corr(seq),
                created_at=created_at + timedelta(minutes=10),
            ))
            seq += 1

        for step_idx, (from_code, to_code) in enumerate(JOURNEYS[status_code]):
            _requires_reason, required_permission = TRANSITION_LOOKUP[(from_code, to_code)]
            step_actor = reopen_actor_id if required_permission == "ticket.reopen" else agent_id
            event_rows.append(_event(
                id=sid("event", ticket_key, "status", str(step_idx)), ticket_id=ticket_id,
                actor_id=step_actor, event_type="status_changed",
                old_value={"status_id": str(status_ids[branch_key][from_code])},
                new_value={"status_id": str(status_ids[branch_key][to_code])},
                visibility="customer", correlation_id=_corr(seq),
                created_at=created_at + timedelta(hours=2 * (step_idx + 1)),
            ))
            seq += 1

        use_reply = first_response_at is not None
        body_ar, body_en = (REPLY_BODIES if use_reply else NOTE_BODIES)[i % 2]
        event_rows.append(_event(
            id=sid("event", ticket_key, "interaction"), ticket_id=ticket_id, actor_id=agent_id,
            event_type="reply_sent" if use_reply else "note_added",
            body=body_ar if is_ar else body_en,
            visibility="customer" if use_reply else "internal", correlation_id=_corr(seq),
            created_at=(first_response_at or created_at) + timedelta(minutes=5),
        ))

    await upsert(session, Ticket, rows)
    await _backfill_ticket_sla_policy(session, rows)
    await upsert(session, TicketEvent, event_rows)


async def _backfill_ticket_sla_policy(session: AsyncSession, rows: list[dict]) -> None:
    """`upsert()` above is insert-only (`ON CONFLICT (id) DO NOTHING`) — against a database
    already seeded before `sla_policy_id` resolution existed, it silently leaves every
    already-inserted ticket's `sla_policy_id` at whatever it was (`NULL`, for most of them).
    This fills in exactly those still-`NULL` rows with the value just resolved above — and only
    those: a ticket whose `sla_policy_id` was later legitimately set (an already-resolved value
    from a fresh seed run, or a real `POST /tickets/{id}/sla-override`) is never touched, so this
    stays idempotent — the first run heals the gap, every run after is a no-op."""

    # `update(Ticket.__table__)` (Core, not the mapped class) avoids SQLAlchemy 2.0's ORM-enabled
    # "bulk UPDATE by primary key" path, which demands the primary key under its real column
    # name in every params dict rather than a bound parameter — irrelevant for a plain Core
    # executemany like this one.
    stmt = (
        update(Ticket.__table__)
        .where(Ticket.id == bindparam("ticket_id"), Ticket.sla_policy_id.is_(None))
        .values(sla_policy_id=bindparam("new_sla_policy_id"))
    )
    params = [
        {"ticket_id": row["id"], "new_sla_policy_id": row["sla_policy_id"]}
        for row in rows
        if row["sla_policy_id"] is not None
    ]
    if params:
        await session.execute(stmt, params)


async def sync_ticket_reference_sequence(session: AsyncSession) -> None:
    """`seed_tickets()` above inserts explicit `reference_no` values (`TKT-{year}-{6-digit}`) as
    part of its idempotent `ON CONFLICT DO NOTHING` upsert, and never touches
    `ticket_reference_seq` (the DB sequence `TicketService._generate_reference_no` — batch 4d —
    draws from for every real `POST /tickets`). Left alone, the sequence starts at 1 while seeded
    reference numbers already occupy 1..40, so ticket creation collides
    (`UniqueViolationError`) until enough calls advance it past 40.

    `GREATEST` against the sequence's own current `last_value` makes this safe to call every seed
    run (idempotent — never moves the sequence backwards) and safe even if real tickets were
    already created via the API before/between seed runs."""

    result = await session.execute(
        text("SELECT COALESCE(MAX(split_part(reference_no, '-', 3)::bigint), 0) FROM tickets")
    )
    max_suffix = result.scalar_one()
    result = await session.execute(
        text(
            "SELECT setval('ticket_reference_seq', "
            "GREATEST(:max_suffix, (SELECT last_value FROM ticket_reference_seq)))"
        ),
        {"max_suffix": max_suffix},
    )
    new_value = result.scalar_one()
    print(f"[seed] ticket_reference_seq synced to {new_value} (highest seeded reference: {max_suffix}).")


# --------------------------------------------------------------------------------------------
# Post-seed verification — re-reads every label_ar and every Arabic ticket subject straight
# back from Postgres and confirms each one starts with a U+06xx (Arabic block) codepoint,
# catching exactly the class of corruption a Windows console codepage previously caused.
# --------------------------------------------------------------------------------------------

_LABEL_AR_TABLES = [
    "branches", "departments", "roles", "permissions", "categories",
    "priorities", "ticket_statuses", "sla_policies", "quick_replies",
]


async def verify_arabic_integrity(session: AsyncSession) -> None:
    failures: list[str] = []
    total = 0

    for table in _LABEL_AR_TABLES:
        result = await session.execute(text(f"SELECT id, label_ar FROM {table}"))
        for row_id, value in result.all():
            total += 1
            if not value or ord(value[0]) not in ARABIC_BLOCK:
                failures.append(f"{table}.label_ar id={row_id}")

    result = await session.execute(text("SELECT id, subject FROM tickets WHERE source_locale = 'ar'"))
    for row_id, subject in result.all():
        total += 1
        if not subject or ord(subject[0]) not in ARABIC_BLOCK:
            failures.append(f"tickets.subject id={row_id}")

    if failures:
        raise RuntimeError(
            f"Arabic integrity check failed for {len(failures)} of {total} row(s): {failures[:10]}"
        )
    print(f"[seed] Arabic integrity verified: {total} row(s) OK.")


# --------------------------------------------------------------------------------------------

async def run() -> None:
    async with async_session_factory() as session:
        await seed_branches(session)
        await seed_departments(session)
        await seed_roles(session)
        await seed_permissions(session)
        await seed_users(session)
        category_ids = await seed_categories(session)
        priority_ids = await seed_priorities(session)
        status_ids = await seed_statuses_and_transitions(session)
        await seed_sla_policies(session, category_ids, priority_ids)
        await seed_quick_replies(session)
        await seed_channel_configs(session, category_ids)
        customers = await seed_customers(session)
        await seed_kb_articles(session, category_ids)
        await seed_kb_article_embeddings(session)
        await seed_tickets(session, status_ids, priority_ids, category_ids, customers)
        await sync_ticket_reference_sequence(session)
        await session.commit()

        await verify_arabic_integrity(session)

    print("[seed] Done.")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
