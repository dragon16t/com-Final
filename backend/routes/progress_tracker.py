"""
Celesta Glow — AI Skin Progress Tracker + Razorpay auto-pay subscription.

Customer (email-OTP authenticated) endpoints (mounted under /api):
- GET  /tracker/status                 -> full tracker state: enrolment, plan, days left,
                                           eligibility, today's AI tasks, recent logs, subscription
- POST /tracker/enroll                 -> activate tracker (FREE 1 month if a qualifying order
                                           >= TRACKER_FREE_ORDER_MIN exists, else needs subscription)
- POST /tracker/log                    -> upload daily selfie (Cloudinary) + notes; every 3rd day
                                           an AI improvement suggestion is generated
- GET  /tracker/logs                   -> all daily logs (photos + notes + suggestions)
- POST /tracker/subscribe              -> create a Razorpay recurring subscription (auto-pay ₹499/mo)
- POST /tracker/subscribe/verify       -> verify first subscription payment, mark plan 'paid'

Admin endpoints (X-Admin-Token):
- GET  /admin/trackers                 -> list every customer tracker (with log counts)
- GET  /admin/trackers/{email}         -> full detail incl. photos, notes, AI suggestions, tasks
"""
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import os
import json
import re
import base64
import logging
import hashlib

logger = logging.getLogger(__name__)

router = APIRouter()
db = None


def set_db(database):
    global db
    db = database


# ---- config ----
TRACKER_PRICE = int(os.environ.get("TRACKER_MONTHLY_PRICE", "499"))
TRACKER_FREE_ORDER_MIN = int(os.environ.get("TRACKER_FREE_ORDER_MIN", "499"))
FREE_DAYS = 30


# ---- razorpay client (lazy) ----
def _rzp():
    kid = os.environ.get("RAZORPAY_KEY_ID")
    ks = os.environ.get("RAZORPAY_KEY_SECRET")
    if not kid or not ks:
        return None
    try:
        import razorpay
        return razorpay.Client(auth=(kid, ks))
    except Exception as e:
        logger.warning(f"[tracker] razorpay init failed: {e}")
        return None


async def _user(authorization: Optional[str]):
    """Reuse the customer-auth session resolver."""
    from routes.customer_auth import _get_session_user
    return await _get_session_user(authorization)


def _now():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.isoformat()


def _parse_dt(v):
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        except Exception:
            return None
    return None


async def _qualifying_order(email: str):
    """Return the first paid/confirmed order for this user worth >= the free threshold."""
    customer = await db.customers.find_one({"email": email}, {"_id": 0}) or {}
    phone = customer.get("phone")
    ors = [{"email": email}]
    if phone:
        ors.append({"phone": phone})
    cursor = db.orders.find({"$or": ors}, {"_id": 0}).sort("created_at", -1).limit(100)
    async for o in cursor:
        amt = o.get("amount") or o.get("total_amount") or 0
        try:
            amt = float(amt)
        except Exception:
            amt = 0
        if amt >= TRACKER_FREE_ORDER_MIN:
            return o
    return None


def _access(tracker: dict):
    """Return (has_access, plan, expires_at, days_left)."""
    if not tracker:
        return False, None, None, 0
    now = _now()
    plan = tracker.get("plan")
    if plan == "free":
        exp = _parse_dt(tracker.get("free_until"))
    elif plan == "paid":
        exp = _parse_dt(tracker.get("paid_until"))
    else:
        exp = None
    if tracker.get("subscription_status") == "active" and plan == "paid":
        # active auto-pay — treat as always-on until cancelled
        return True, plan, _iso(exp) if exp else None, 30
    if exp and exp > now:
        return True, plan, _iso(exp), max(0, (exp - now).days)
    return False, plan, _iso(exp) if exp else None, 0


# =============================================================
# AI helpers
# =============================================================
async def _generate_daily_tasks(tracker: dict, day_number: int) -> list:
    """AI-generate the day's routine + do/don't tasks. Robust static fallback."""
    concerns = ", ".join(tracker.get("concerns") or []) or "healthy glowing skin"
    skin_type = tracker.get("skin_type") or "all skin types"
    age = tracker.get("age") or "adult"
    products = ", ".join(tracker.get("product_names") or []) or "your Celesta Glow products"
    api_key = os.environ.get("EMERGENT_LLM_KEY", "")
    if api_key:
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            prompt = f"""You are a dermatology coach for the Celesta Glow skin tracker.
Create Day {day_number} tasks for a {age} person with {skin_type} skin working on: {concerns}.
They use: {products}.
Return ONLY JSON:
{{
  "focus": "<one-line focus for today, max 10 words>",
  "tasks": [
     {{"type":"use","title":"<what to apply / step>","detail":"<short how, max 16 words>"}},
     {{"type":"care","title":"<a care habit>","detail":"<short why, max 16 words>"}},
     {{"type":"do","title":"<a do>","detail":"<short, max 14 words>"}},
     {{"type":"dont","title":"<a don't>","detail":"<short, max 14 words>"}}
  ]
}}
Give 4-6 tasks. Warm, practical, India-aware. No medical claims."""
            chat = LlmChat(api_key=api_key, session_id=f"tracker-{tracker.get('email','x')[:6]}-{day_number}",
                           system_message="You are a precise JSON-only skincare coaching API.").with_model("gemini", "gemini-2.5-flash")
            resp = await chat.send_message(UserMessage(text=prompt))
            raw = re.sub(r"^```(?:json)?\s*", "", (resp or "").strip())
            raw = re.sub(r"\s*```$", "", raw)
            m = re.search(r"\{[\s\S]*\}", raw)
            data = json.loads(m.group(0) if m else raw)
            tasks = data.get("tasks") or []
            if tasks:
                return [{"focus": data.get("focus", "")}] + tasks
        except Exception as e:
            logger.warning(f"[tracker] AI task gen failed (day {day_number}): {e}")
    # -------- static fallback --------
    return [
        {"focus": "Consistency builds visible results"},
        {"type": "use", "title": "Cleanse AM & PM", "detail": "Use a gentle cleanser on damp skin, pat dry."},
        {"type": "use", "title": "Apply your serum", "detail": "2-3 drops on clean skin before moisturiser."},
        {"type": "care", "title": "Sunscreen every morning", "detail": "SPF 50, reapply if outdoors."},
        {"type": "do", "title": "Drink 2-3L water", "detail": "Hydration supports the skin barrier."},
        {"type": "dont", "title": "Don't over-exfoliate", "detail": "Max 2x a week to avoid irritation."},
    ]


async def _ai_suggestion(tracker: dict, photo_b64: str, day_number: int) -> dict:
    """Run the skin analyzer on the latest photo and compare with the baseline."""
    try:
        from services.ai_skin_analyzer import AISkinAnalyzer
        analyzer = AISkinAnalyzer()
        raw = photo_b64.split(",", 1)[1] if photo_b64.startswith("data:") and "," in photo_b64 else photo_b64
        analysis = await analyzer.analyze_face_image(raw, "front")

        def _s(k):
            try:
                return float(analysis.get(k, 6))
            except Exception:
                return 6.0
        keys = ["beauty_score", "aging_score", "acne_score", "dullness_score", "pigmentation_score", "texture_score"]
        score = round(sum(_s(k) for k in keys) / len(keys) * 10)
        baseline = tracker.get("baseline_score")
        delta = (score - baseline) if isinstance(baseline, (int, float)) else 0
        tip = analysis.get("personalized_tip") or "Keep going — consistency is the key to visible change."
        trend = "improving" if delta > 0 else ("steady" if delta == 0 else "needs attention")
        return {
            "score": score,
            "baseline_score": baseline,
            "delta": delta,
            "trend": trend,
            "suggestion": f"Day {day_number}: your skin looks {trend}. {tip}",
            "analysis": analysis,
        }
    except Exception as e:
        logger.warning(f"[tracker] AI suggestion failed: {e}")
        return {
            "score": None, "delta": 0, "trend": "steady",
            "suggestion": f"Day {day_number}: great job logging your progress! Stay consistent with your routine.",
        }


# =============================================================
# Customer endpoints
# =============================================================
class EnrollRequest(BaseModel):
    order_id: Optional[str] = None
    skin_type: Optional[str] = None
    age: Optional[str] = None
    concerns: List[str] = []


class LogRequest(BaseModel):
    photo_base64: Optional[str] = None
    notes: Optional[str] = None
    mood: Optional[str] = None


async def _today_tasks(tracker: dict):
    """Fetch (or generate + cache) today's tasks for the tracker."""
    started = _parse_dt(tracker.get("started_at")) or _now()
    day_number = max(1, (_now() - started).days + 1)
    date_key = _now().strftime("%Y-%m-%d")
    existing = await db.tracker_tasks.find_one({"email": tracker["email"], "date": date_key}, {"_id": 0})
    if existing:
        return day_number, existing.get("tasks", [])
    tasks = await _generate_daily_tasks(tracker, day_number)
    await db.tracker_tasks.update_one(
        {"email": tracker["email"], "date": date_key},
        {"$set": {"email": tracker["email"], "date": date_key, "day_number": day_number,
                  "tasks": tasks, "created_at": _iso(_now())}},
        upsert=True,
    )
    return day_number, tasks


@router.get("/tracker/status")
async def tracker_status(authorization: Optional[str] = Header(None)):
    session = await _user(authorization)
    email = session["email"]
    tracker = await db.trackers.find_one({"email": email}, {"_id": 0})
    qualifying = await _qualifying_order(email)

    if not tracker:
        return {
            "enrolled": False,
            "eligible_free": bool(qualifying),
            "qualifying_order_id": qualifying.get("order_id") if qualifying else None,
            "price": TRACKER_PRICE,
            "free_order_min": TRACKER_FREE_ORDER_MIN,
        }

    has_access, plan, expires_at, days_left = _access(tracker)
    day_number, tasks = (0, [])
    if has_access:
        day_number, tasks = await _today_tasks(tracker)
    logs = await db.tracker_logs.find({"email": email}, {"_id": 0}).sort("created_at", -1).limit(60).to_list(60)
    return {
        "enrolled": True,
        "has_access": has_access,
        "plan": plan,
        "status": tracker.get("status"),
        "expires_at": expires_at,
        "days_left": days_left,
        "started_at": tracker.get("started_at"),
        "day_number": day_number,
        "today_focus": (tasks[0].get("focus") if tasks and isinstance(tasks[0], dict) and "focus" in tasks[0] else ""),
        "today_tasks": [t for t in tasks if "title" in t],
        "logs": logs,
        "logs_count": len(logs),
        "subscription_status": tracker.get("subscription_status"),
        "eligible_free": bool(qualifying),
        "price": TRACKER_PRICE,
        "free_order_min": TRACKER_FREE_ORDER_MIN,
    }


@router.post("/tracker/enroll")
async def tracker_enroll(req: EnrollRequest, authorization: Optional[str] = Header(None)):
    session = await _user(authorization)
    email = session["email"]
    existing = await db.trackers.find_one({"email": email}, {"_id": 0})
    if existing:
        has_access, *_ = _access(existing)
        if has_access:
            return {"success": True, "already": True, "message": "Tracker already active."}

    qualifying = await _qualifying_order(email)
    now = _now()

    # product names from the qualifying order (used to personalise AI tasks)
    product_names = []
    if qualifying:
        for it in (qualifying.get("items") or []):
            nm = it.get("name") or it.get("short_name")
            if nm:
                product_names.append(nm)

    base = {
        "email": email,
        "customer_id": session.get("customer_id"),
        "skin_type": req.skin_type,
        "age": req.age,
        "concerns": req.concerns,
        "product_names": product_names[:8],
        "updated_at": _iso(now),
    }

    if qualifying:
        base.update({
            "plan": "free",
            "status": "active",
            "started_at": _iso(now),
            "free_until": _iso(now + timedelta(days=FREE_DAYS)),
            "qualifying_order_id": qualifying.get("order_id"),
            "created_at": _iso(now),
        })
        await db.trackers.update_one({"email": email}, {"$set": base}, upsert=True)
        return {"success": True, "plan": "free", "needs_subscription": False,
                "free_until": base["free_until"],
                "message": f"Your free 1-month AI progress tracker is active! (Order {qualifying.get('order_id')})"}

    # No qualifying order -> must subscribe to activate
    base.update({"plan": "pending", "status": "pending_subscription", "created_at": _iso(now)})
    await db.trackers.update_one({"email": email}, {"$set": base}, upsert=True)
    return {"success": True, "plan": "pending", "needs_subscription": True, "price": TRACKER_PRICE,
            "message": f"Subscribe at ₹{TRACKER_PRICE}/month to activate your AI progress tracker."}


@router.post("/tracker/log")
async def tracker_log(req: LogRequest, authorization: Optional[str] = Header(None)):
    session = await _user(authorization)
    email = session["email"]
    tracker = await db.trackers.find_one({"email": email}, {"_id": 0})
    if not tracker:
        raise HTTPException(status_code=400, detail="Enroll in the tracker first.")
    has_access, *_ = _access(tracker)
    if not has_access:
        raise HTTPException(status_code=402, detail="Your tracker has expired. Subscribe to continue.")

    started = _parse_dt(tracker.get("started_at")) or _now()
    now = _now()
    day_number = max(1, (now - started).days + 1)

    photo_url = None
    if req.photo_base64:
        try:
            from services import cloudinary_service
            await cloudinary_service.ensure_configured(db)
            raw = req.photo_base64
            if raw.startswith("data:") and "," in raw:
                raw = raw.split(",", 1)[1]
            file_bytes = base64.b64decode(raw)
            pid = f"tracker/{hashlib.md5(email.encode()).hexdigest()[:8]}/day{day_number}-{int(now.timestamp())}"
            up = await cloudinary_service.upload_image(db, file_bytes, folder="celesta-tracker", public_id=pid)
            photo_url = up.get("url")
        except Exception as e:
            logger.warning(f"[tracker] photo upload failed: {e}")
            raise HTTPException(status_code=502, detail="Photo upload failed. Please try again.")

    # set baseline score on first photo
    ai = None
    is_third = (day_number % 3 == 0)
    log_count = await db.tracker_logs.count_documents({"email": email})
    if req.photo_base64 and log_count == 0:
        # baseline analysis (store score, no comparison yet)
        b = await _ai_suggestion({**tracker, "baseline_score": None}, req.photo_base64, day_number)
        if b.get("score") is not None:
            await db.trackers.update_one({"email": email}, {"$set": {"baseline_score": b["score"]}})
            tracker["baseline_score"] = b["score"]
    # every 3rd day -> AI improvement suggestion
    if req.photo_base64 and (is_third or log_count == 0):
        ai = await _ai_suggestion(tracker, req.photo_base64, day_number)

    doc = {
        "id": hashlib.md5(f"{email}{now.timestamp()}".encode()).hexdigest(),
        "email": email,
        "day_number": day_number,
        "date": now.strftime("%Y-%m-%d"),
        "photo_url": photo_url,
        "notes": req.notes,
        "mood": req.mood,
        "ai_suggestion": ai.get("suggestion") if ai else None,
        "ai_score": ai.get("score") if ai else None,
        "ai_delta": ai.get("delta") if ai else None,
        "ai_trend": ai.get("trend") if ai else None,
        "created_at": _iso(now),
    }
    await db.tracker_logs.insert_one(dict(doc))
    doc.pop("_id", None)
    await db.trackers.update_one({"email": email}, {"$set": {"last_log_at": _iso(now)}})
    return {"success": True, "log": doc, "ai_suggestion": doc["ai_suggestion"]}


@router.get("/tracker/logs")
async def tracker_logs(authorization: Optional[str] = Header(None)):
    session = await _user(authorization)
    logs = await db.tracker_logs.find({"email": session["email"]}, {"_id": 0}).sort("created_at", -1).to_list(365)
    return {"success": True, "logs": logs, "count": len(logs)}


# =============================================================
# Razorpay recurring subscription (auto-pay)
# =============================================================
async def _ensure_plan():
    """Return a Razorpay monthly ₹TRACKER_PRICE plan id, creating + caching it once."""
    cfg = await db.admin_settings.find_one({"type": "tracker_plan"}, {"_id": 0}) or {}
    if cfg.get("plan_id") and cfg.get("amount") == TRACKER_PRICE:
        return cfg["plan_id"]
    client = _rzp()
    if not client:
        raise HTTPException(status_code=503, detail="Payments not configured.")
    plan = client.plan.create({
        "period": "monthly",
        "interval": 1,
        "item": {
            "name": "Celesta Glow AI Skin Tracker",
            "amount": TRACKER_PRICE * 100,
            "currency": "INR",
            "description": "Monthly AI skin progress tracking subscription",
        },
    })
    await db.admin_settings.update_one(
        {"type": "tracker_plan"},
        {"$set": {"type": "tracker_plan", "plan_id": plan["id"], "amount": TRACKER_PRICE,
                  "created_at": _iso(_now())}},
        upsert=True,
    )
    return plan["id"]


@router.post("/tracker/subscribe")
async def tracker_subscribe(authorization: Optional[str] = Header(None)):
    session = await _user(authorization)
    email = session["email"]
    client = _rzp()
    if not client:
        raise HTTPException(status_code=503, detail="Payments not configured.")
    plan_id = await _ensure_plan()
    sub = client.subscription.create({
        "plan_id": plan_id,
        "customer_notify": 1,
        "quantity": 1,
        "total_count": 12,  # auto-charge monthly for up to 12 months
        "notes": {"email": email, "product": "ai_skin_tracker"},
    })
    await db.trackers.update_one(
        {"email": email},
        {"$set": {"email": email, "customer_id": session.get("customer_id"),
                  "razorpay_subscription_id": sub["id"], "subscription_status": "created",
                  "updated_at": _iso(_now())}},
        upsert=True,
    )
    return {
        "success": True,
        "subscription_id": sub["id"],
        "key_id": os.environ.get("RAZORPAY_KEY_ID"),
        "short_url": sub.get("short_url"),
        "amount": TRACKER_PRICE,
        "customer_email": email,
    }


class SubVerifyRequest(BaseModel):
    razorpay_payment_id: str
    razorpay_subscription_id: str
    razorpay_signature: str


@router.post("/tracker/subscribe/verify")
async def tracker_subscribe_verify(req: SubVerifyRequest, authorization: Optional[str] = Header(None)):
    session = await _user(authorization)
    email = session["email"]
    client = _rzp()
    if not client:
        raise HTTPException(status_code=503, detail="Payments not configured.")
    try:
        client.utility.verify_payment_signature({
            "razorpay_payment_id": req.razorpay_payment_id,
            "razorpay_subscription_id": req.razorpay_subscription_id,
            "razorpay_signature": req.razorpay_signature,
        })
    except Exception as e:
        logger.warning(f"[tracker] subscription signature verify failed: {e}")
        raise HTTPException(status_code=400, detail="Payment verification failed.")

    now = _now()
    tracker = await db.trackers.find_one({"email": email}, {"_id": 0}) or {}
    upd = {
        "email": email,
        "plan": "paid",
        "status": "active",
        "subscription_status": "active",
        "razorpay_subscription_id": req.razorpay_subscription_id,
        "last_payment_id": req.razorpay_payment_id,
        "paid_until": _iso(now + timedelta(days=31)),
        "updated_at": _iso(now),
    }
    if not tracker.get("started_at"):
        upd["started_at"] = _iso(now)
        upd["created_at"] = _iso(now)
    await db.trackers.update_one({"email": email}, {"$set": upd}, upsert=True)
    return {"success": True, "plan": "paid", "message": "Subscription active — your AI tracker is unlocked!"}


# =============================================================
# Admin endpoints
# =============================================================
def _verify_admin(token: Optional[str]):
    from routes import products
    products.verify_auth(x_admin_token=token)


@router.get("/admin/trackers")
async def admin_list_trackers(x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")):
    _verify_admin(x_admin_token)
    trackers = await db.trackers.find({}, {"_id": 0}).sort("updated_at", -1).to_list(1000)
    out = []
    for t in trackers:
        has_access, plan, expires_at, days_left = _access(t)
        count = await db.tracker_logs.count_documents({"email": t["email"]})
        out.append({
            **t,
            "has_access": has_access,
            "days_left": days_left,
            "logs_count": count,
        })
    return {"trackers": out, "count": len(out)}


@router.get("/admin/trackers/{email}")
async def admin_tracker_detail(email: str, x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")):
    _verify_admin(x_admin_token)
    email = email.lower().strip()
    tracker = await db.trackers.find_one({"email": email}, {"_id": 0})
    if not tracker:
        raise HTTPException(status_code=404, detail="Tracker not found")
    logs = await db.tracker_logs.find({"email": email}, {"_id": 0}).sort("created_at", 1).to_list(365)
    tasks = await db.tracker_tasks.find({"email": email}, {"_id": 0}).sort("date", -1).to_list(120)
    has_access, plan, expires_at, days_left = _access(tracker)
    return {
        "tracker": {**tracker, "has_access": has_access, "days_left": days_left, "expires_at": expires_at},
        "logs": logs,
        "tasks": tasks,
    }
