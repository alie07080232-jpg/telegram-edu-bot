import json
import os
import logging
import time
import html

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from telegram.error import BadRequest
from telegram.request import HTTPXRequest

# =========================
# 1. إعدادات السجل والبيانات
# =========================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = "8923167631:AAEL_Kj0CajjWR744VpwvJ9AC8hdQStSExg"
OWNER_ID = 1400528157
YOUTUBE_URL = "https://youtube.com/@moqtdaamer?si=qTDuPNCBSckl2qmu"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "test_data.json")

default_structure = {
    "admins": [OWNER_ID],
    "sub_admins": {}, 
    "users": [],
    "user_stages": {}, 
    "usernames": {},
    "banned_users": [],
    "stages": {},
    "favorites": {},
    "schedule_info": "📅 لا يوجد جدول مضاف حالياً.",
    "faq_info": {
        "سعي": "📊 **احتساب السعي:** يتم احتساب السعي بناءً على درجات امتحانات الفاينل والميد والنشاط اليومي.",
        "عبور": "⚖️ **شروط العبور (التحميل):** يحق للطالب العبور بمادتين كحد أقصى من المرحلة الحالية.",
        "قاعات": "📍 **القاعات والمختبرات:** يرجى مراجعة لوحة الإعلانات في قسمك لمعرفة جدول القاعات."
    },
    "student_contributions": {}
}

admin_states = {}

# =========================
# 2. وظائف حفظ واسترجاع البيانات
# =========================
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    loaded = json.loads(content)
                    if "admins" not in loaded: loaded["admins"] = [OWNER_ID]
                    if OWNER_ID not in loaded["admins"]: loaded["admins"].append(OWNER_ID)
                    if "sub_admins" not in loaded: loaded["sub_admins"] = {}
                    if "users" not in loaded: loaded["users"] = []
                    if "user_stages" not in loaded: loaded["user_stages"] = {}
                    if "usernames" not in loaded: loaded["usernames"] = {}
                    if "banned_users" not in loaded: loaded["banned_users"] = []
                    if "stages" not in loaded: loaded["stages"] = {}
                    if "favorites" not in loaded: loaded["favorites"] = {}
                    if "schedule_info" not in loaded: loaded["schedule_info"] = default_structure["schedule_info"]
                    if "faq_info" not in loaded: loaded["faq_info"] = default_structure["faq_info"]
                    if "student_contributions" not in loaded: loaded["student_contributions"] = {}
                    return loaded
        except Exception as e:
            logger.error(f"Error loading JSON: {e}")
    return default_structure.copy()

def save_data(data_to_save):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"Error saving JSON: {e}")

db = load_data()

def is_full_admin(user_id: int) -> bool:
    if user_id == OWNER_ID:
        return True
    admins = db.get("admins", [])
    return user_id in admins or str(user_id) in [str(a) for a in admins]

def is_sub_admin(user_id: int) -> bool:
    return str(user_id) in db.get("sub_admins", {})

def is_any_admin(user_id: int) -> bool:
    return is_full_admin(user_id) or is_sub_admin(user_id)

def is_banned(user_id: int) -> bool:
    return user_id in db.get("banned_users", [])

def update_user_data(user):
    user_id = user.id
    username = user.username.lower() if user.username else None
    
    changed = False
    if user_id not in db["users"]:
        db["users"].append(user_id)
        changed = True
        
    if username:
        if db["usernames"].get(username) != user_id:
            db["usernames"][username] = user_id
            db["usernames"][f"@{username}"] = user_id
            changed = True
        
    if changed:
        save_data(db)

def get_user_stage_id(user_id: int):
    str_uid = str(user_id)
    stages_list = db.get("user_stages", {}).get(str_uid, [])
    return stages_list[0] if stages_list else None

# =========================
# 3. الأوامر الرئيسية
# =========================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    if is_banned(user_id):
        if update.message:
            await update.message.reply_text("❌ أنت محظور من استخدام البوت.")
        return

    update_user_data(user)

    user_stage = get_user_stage_id(user_id)
    stages = db.get("stages", {})
    if not user_stage and not is_any_admin(user_id):
        if stages:
            keyboard = [[InlineKeyboardButton(f"🎓 {v['name']}", callback_data=f"set_primary_stage:{k}")] for k, v in stages.items()]
            safe_name = html.escape(user.first_name)
            ask_text = f"👋 <b>أهلاً بك يا {safe_name}!</b>\n\nيرجى اختيار <b>مرحلتك الدراسية الأساسية</b> (لإرسال الإشعارات والإذاعات الخاصة بمرحلتك):"
            if update.callback_query:
                try:
                    await update.callback_query.edit_message_text(ask_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
                except BadRequest:
                    pass
            else:
                await update.message.reply_text(ask_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            return

    keyboard = [
        [InlineKeyboardButton("📚 المراحل والمناهج", callback_data="u_st_main")],
        [InlineKeyboardButton("💡 ملخصات وشروحات الطلبة", callback_data="student_contrib_main")],
        [InlineKeyboardButton("📅 جدول الامتحانات والدروس", callback_data="show_schedule"), InlineKeyboardButton("🤖 الأسئلة الشائعة", callback_data="show_faq")],
        [InlineKeyboardButton("🔍 بحث سريع", callback_data="start_search"), InlineKeyboardButton("⭐ مفضلتي", callback_data="show_favs")],
        [InlineKeyboardButton("🔄 تغيير المرحلة الأساسية", callback_data="change_my_stage")],
        [InlineKeyboardButton("🎥 قناة اليوتيوب", url=YOUTUBE_URL), InlineKeyboardButton("💬 تواصل مع الإدارة", callback_data="start_support")],
        [InlineKeyboardButton("🗑 مسح الرسالة", callback_data="close")]
    ]

    safe_name = html.escape(user.first_name)
    welcome_text = (
        f"✨ <b>البوت التعليمي الرسمي</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👑 **المطور والمهندس:** <code>مقتدى عامر</code>\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"👋 أهلاً بك يا <b>{safe_name}</b> في بوتك التعليمي.\n"
        f"اختر من القائمة أدناه للبدء:"
    )
    
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        except BadRequest:
            pass
    else:
        await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

def get_admin_panel_keyboard(user_id):
    if is_full_admin(user_id):
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ إضافة مرحلة", callback_data="add_st"), InlineKeyboardButton("➕ إضافة مادة", callback_data="add_sb")],
            [InlineKeyboardButton("📥 رفع محتوى", callback_data="up_st"), InlineKeyboardButton("🗑 حذف مرحلة/مادة", callback_data="del_menu")],
            [InlineKeyboardButton("📢 إذاعة للكل", callback_data="broadcast_all"), InlineKeyboardButton("🎯 إذاعة مخصصة (لمرحلة)", callback_data="broadcast_target")],
            [InlineKeyboardButton("📅 تحديث الجدول", callback_data="set_schedule"), InlineKeyboardButton("👥 رابط مناقشة لمادة", callback_data="set_group_link")],
            [InlineKeyboardButton("👑 إضافة مشرف جزئي", callback_data="add_subadmin")],
            [InlineKeyboardButton("📊 الإحصائيات", callback_data="stats"), InlineKeyboardButton("💾 Backup", callback_data="backup_db")],
            [InlineKeyboardButton("🚫 حظر", callback_data="ban_usr"), InlineKeyboardButton("✅ فك الحظر", callback_data="unban_usr")],
            [InlineKeyboardButton("🗑 إغلاق اللوحة", callback_data="close")]
        ])
    elif is_sub_admin(user_id):
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📥 رفع محتوى للمواد المخصصة لك", callback_data="up_st")],
            [InlineKeyboardButton("🗑 إغلاق اللوحة", callback_data="close")]
        ])
    return None

async def panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    update_user_data(update.effective_user)
    
    kb = get_admin_panel_keyboard(user_id)
    if kb:
        text = "🎓 <b>لوحة الإدارة الشاملة (المطور: مقتدى عامر):</b>" if is_full_admin(user_id) else "🎓 <b>لوحة المشرف الجزئي:</b>"
        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb.inline_keyboard), parse_mode="HTML")
            except BadRequest:
                pass
        else:
            await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        if not update.callback_query:
            await update.message.reply_text("❌ هذا الأمر للإدارة فقط.")

async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in admin_states and admin_states[user_id].get("mode") in ["uploading", "ask_protect", "broadcasting_st_protect"]:
        del admin_states[user_id]
        await update.message.reply_text(f"✅ <b>تمت العملية بنجاح!</b>", parse_mode="HTML")
    else:
        await update.message.reply_text("ℹ️ لا توجد عملية نشطة حالياً.")

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in admin_states:
        del admin_states[user_id]
        await update.message.reply_text("✅ تم إلغاء العملية الحالية بنجاح.")

# =========================
# 4. المعالج التفاعلي (Callback Queries)
# =========================
async def render_subject_menu(query, st_id: str, sb_id: str, user_id: int):
    subject = db.get("stages", {}).get(st_id, {}).get("subjects", {}).get(sb_id, {})
    disc_link = subject.get("discussion_link")

    str_user_id = str(user_id)
    user_favs = db.get("favorites", {}).get(str_user_id, [])
    is_fav = any(f.get("st_id") == st_id and f.get("sb_id") == sb_id for f in user_favs)
    fav_btn_text = "⭐ مضافة للمفضلة" if is_fav else "☆ إضافة للمفضلة"

    keyboard = [
        [InlineKeyboardButton("📚 المحاضرات (PDF)", callback_data=f"u_sec:{st_id}:{sb_id}:pdf")],
        [InlineKeyboardButton("📝 الأسئلة والامتحانات", callback_data=f"u_sec:{st_id}:{sb_id}:questions")],
        [InlineKeyboardButton("🎥 الشروحات (YouTube)", callback_data=f"u_sec:{st_id}:{sb_id}:youtube")]
    ]
    
    if disc_link:
        keyboard.append([InlineKeyboardButton("💬 جروب المناقشة الخاص بالمادة", url=disc_link)])
        
    keyboard.append([InlineKeyboardButton(fav_btn_text, callback_data=f"toggle_fav:{st_id}:{sb_id}")])
    keyboard.append([InlineKeyboardButton("⬅️ الرجوع للمرحلة", callback_data=f"u_st:{st_id}")])
    keyboard.append([InlineKeyboardButton("🗑 مسح الرسالة", callback_data="close")])
    
    safe_sub_name = html.escape(subject.get('name', ''))
    try:
        await query.edit_message_text(f"📂 <b>أقسام مادة ({safe_sub_name}):</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    except BadRequest:
        pass

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    user_id = user.id
    data = query.data

    if is_banned(user_id):
        await query.answer("أنت محظور من البوت.", show_alert=True)
        return
        
    await query.answer()

    if data == "close" or data == "cancel_state":
        if user_id in admin_states:
            del admin_states[user_id]
        try:
            await query.message.delete()
        except Exception:
            pass
        return

    if data.startswith("set_primary_stage:"):
        st_id = data.split(":")[1]
        str_uid = str(user_id)
        db["user_stages"][str_uid] = [st_id]
        save_data(db)
        st_name = db.get("stages", {}).get(st_id, {}).get("name", "المحددة")
        await query.answer(f"✅ تم حفظ مرحلتك: {st_name}", show_alert=True)
        await start_command(update, context)
        return

    if data == "change_my_stage":
        stages = db.get("stages", {})
        if not stages:
            await query.answer("❌ لا توجد مراحل مضافة حالياً.", show_alert=True)
            return
        keyboard = [[InlineKeyboardButton(f"🎓 {v['name']}", callback_data=f"set_primary_stage:{k}")] for k, v in stages.items()]
        keyboard.append([InlineKeyboardButton("⬅️ إلغاء ورجوع", callback_data="go_home")])
        try:
            await query.edit_message_text("🔄 <b>اختر مرحلتك الدراسية الجديدة:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        except BadRequest:
            pass
        return

    if data == "student_contrib_main":
        stages = db.get("stages", {})
        keyboard = [
            [InlineKeyboardButton("📤 رفع ملخص أو شرح جديد", callback_data="student_upload_start")]
        ]
        for k, v in stages.items():
            keyboard.append([InlineKeyboardButton(f"💡 ملخصات {v['name']}", callback_data=f"view_contrib_st:{k}")])
        keyboard.append([InlineKeyboardButton("⬅️ الرجوع للرئيسية", callback_data="go_home")])
        keyboard.append([InlineKeyboardButton("🗑 مسح", callback_data="close")])
        try:
            await query.edit_message_text("💡 <b>قسم شروحات وملخصات الطلبة المتميزين:</b>\nاختر المرحلة لعرض الملخصات أو اضغط لرفع ملخصك الخاص:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        except BadRequest:
            pass
        return

    if data == "student_upload_start":
        stages = db.get("stages", {})
        if not stages:
            await query.answer("❌ لا توجد مراحل متاحة حالياً.", show_alert=True)
            return
        keyboard = [[InlineKeyboardButton(f"📚 {v['name']}", callback_data=f"contrib_sel_st:{k}")] for k, v in stages.items()]
        keyboard.append([InlineKeyboardButton("⬅️ رجوع", callback_data="student_contrib_main")])
        try:
            await query.edit_message_text("📤 <b>اختر المرحلة الدراسية الخاصة بالملخص أو الشرح الذي تريد رفعه:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        except BadRequest:
            pass
        return

    if data.startswith("contrib_sel_st:"):
        st_id = data.split(":")[1]
        admin_states[user_id] = {"mode": "student_contrib_upload", "st_id": st_id}
        cancel_kb = [[InlineKeyboardButton("❌ إلغاء", callback_data="cancel_state")]]
        try:
            await query.message.reply_text("✍️ <b>أرسل الآن الملخص (ملف PDF، أو صورة، أو شرح نصي) مع ذكر اسمك ورتّب التفاصيل:</b>", reply_markup=InlineKeyboardMarkup(cancel_kb), parse_mode="HTML")
        except BadRequest:
            pass
        return

    if data.startswith("view_contrib_st:"):
        st_id = data.split(":")[1]
        contributions = db.get("student_contributions", {}).get(st_id, [])
        back_kb = [
            [InlineKeyboardButton("⬅️ رجوع لقائمة الملخصات", callback_data="student_contrib_main")],
            [InlineKeyboardButton("🗑 مسح", callback_data="close")]
        ]
        if not contributions:
            try:
                await query.edit_message_text("❌ لا توجد ملخصات معتمدة لهذه المرحلة حالياً.", reply_markup=InlineKeyboardMarkup(back_kb))
            except BadRequest:
                pass
            return

        for item in contributions:
            itype, val, u_name, caption = item.get("type"), item.get("value"), item.get("uploader_name"), item.get("caption", "")
            full_cap = f"💡 <b>ملخص طالب متميز:</b> {html.escape(u_name)}\n📝 {html.escape(caption)}"
            try:
                if itype == "pdf":
                    await query.message.reply_document(document=val, caption=full_cap, parse_mode="HTML")
                elif itype == "image":
                    await query.message.reply_photo(photo=val, caption=full_cap, parse_mode="HTML")
                elif itype == "text":
                    await query.message.reply_text(f"{full_cap}\n\n{html.escape(val)}", parse_mode="HTML")
            except Exception as e:
                logger.error(f"Error sending contribution: {e}")

        try:
            await query.message.reply_text("✨ <b>تم عرض جميع ملخصات هذه المرحلة.</b>", reply_markup=InlineKeyboardMarkup(back_kb), parse_mode="HTML")
        except BadRequest:
            pass
        return

    if data == "show_schedule":
        sched = db.get("schedule_info", "📅 لا يوجد جدول مضاف حالياً.")
        back_kb = [[InlineKeyboardButton("⬅️ الرجوع للرئيسية", callback_data="go_home")], [InlineKeyboardButton("🗑 مسح", callback_data="close")]]
        try:
            await query.edit_message_text(f"📅 <b>جدول الامتحانات والدروس:</b>\n\n{sched}", reply_markup=InlineKeyboardMarkup(back_kb), parse_mode="HTML")
        except BadRequest:
            pass
        return

    if data == "show_faq":
        faqs = db.get("faq_info", {})
        keyboard = []
        for k in faqs.keys():
            keyboard.append([InlineKeyboardButton(f"❓ {k}", callback_data=f"get_faq:{k}")])
        keyboard.append([InlineKeyboardButton("⬅️ الرجوع للرئيسية", callback_data="go_home")])
        keyboard.append([InlineKeyboardButton("🗑 مسح", callback_data="close")])
        try:
            await query.edit_message_text("🤖 <b>الأسئلة الشائعة والإجابات الآلية:</b>\nاختر السؤال من القائمة للمعاينة:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        except BadRequest:
            pass
        return

    if data.startswith("get_faq:"):
        faq_key = data.split(":")[1]
        answer = db.get("faq_info", {}).get(faq_key, "لا توجد إجابة متاحة.")
        back_kb = [[InlineKeyboardButton("⬅️ الرجوع للأسئلة الشائعة", callback_data="show_faq")]]
        try:
            await query.edit_message_text(f"💡 <b>{faq_key}:</b>\n\n{answer}", reply_markup=InlineKeyboardMarkup(back_kb), parse_mode="HTML")
        except BadRequest:
            pass
        return

    if data.startswith("set_protect:"):
        protect_val = data.split(":")[1] == "true"
        state = admin_states.get(user_id)
        
        if state and state.get("mode") == "ask_protect" and "temp_item" in state:
            st_id, sb_id, sec_type = state["st_id"], state["sb_id"], state["sec_type"]
            item_data = state["temp_item"]
            item_data["protect_content"] = protect_val

            stage = db.get("stages", {}).get(st_id)
            if stage and sb_id in stage.get("subjects", {}):
                subject = stage["subjects"][sb_id]
                if "sections" not in subject:
                    subject["sections"] = {"pdf": [], "questions": [], "youtube": []}
                if sec_type not in subject["sections"]:
                    subject["sections"][sec_type] = []

                subject["sections"][sec_type].append(item_data)
                state["count"] += 1
                state["mode"] = "uploading"
                del state["temp_item"]
                save_data(db)

                status_txt = "🔒 ممنوع التوجيه" if protect_val else "🔓 مسموح التوجيه"
                cancel_done = [[InlineKeyboardButton("✅ إنهاء الرفع (/done)", callback_data="cancel_state")]]
                await query.message.reply_text(
                    f"✅ تم حفظ الملف بنجاح! ({status_txt})\n📊 إجمالي الملفات المرفوعة: <b>{state['count']}</b>\n\nأرسل الملف التالي أو اضغط إنهاء عند الاكتمال.",
                    reply_markup=InlineKeyboardMarkup(cancel_done),
                    parse_mode="HTML"
                )
        return

    if data.startswith("broadcast_protect:"):
        protect_val = data.split(":")[1] == "true"
        state = admin_states.get(user_id)
        if state and state.get("mode") == "broadcasting_st_protect":
            st_id = state.get("st_id")
            msg_data = state.get("msg_data")
            
            del admin_states[user_id]
            
            count = 0
            for u in db.get("users", []):
                str_u = str(u)
                if str_u in db.get("user_stages", {}) and st_id in db["user_stages"][str_u]:
                    try:
                        m_type = msg_data.get("type")
                        val = msg_data.get("value")
                        cap = msg_data.get("caption", "")
                        formatted_cap = f"📢 <b>إشعار لمرحلتك:</b>\n{cap}" if cap else "📢 <b>إشعار لمرحلتك:</b>"

                        if m_type == "text":
                            await context.bot.send_message(chat_id=u, text=f"📢 <b>إشعار لمرحلتك:</b>\n\n{val}", parse_mode="HTML", protect_content=protect_val)
                        elif m_type == "document":
                            await context.bot.send_document(chat_id=u, document=val, caption=formatted_cap, parse_mode="HTML", protect_content=protect_val)
                        elif m_type == "photo":
                            await context.bot.send_photo(chat_id=u, photo=val, caption=formatted_cap, parse_mode="HTML", protect_content=protect_val)
                        elif m_type == "video":
                            await context.bot.send_video(chat_id=u, video=val, caption=formatted_cap, parse_mode="HTML", protect_content=protect_val)
                        count += 1
                    except Exception as e:
                        logger.error(f"Failed broadcasting to {u}: {e}")
            
            status_str = "🔒 (ممنوع التوجيه)" if protect_val else "🔓 (مسموح التوجيه)"
            await query.message.edit_text(f"✅ تم إرسال الإذاعة بنجاح إلى <b>{count}</b> طالب في المرحلة المحددة {status_str}.", parse_mode="HTML")
        return

    if data == "adm_pnl":
        await panel_command(update, context)
        return

    if data == "u_st_main":
        stages = db.get("stages", {})
        keyboard = [[InlineKeyboardButton(f"📚 {v['name']}", callback_data=f"u_st:{k}")] for k, v in stages.items()]
        keyboard.append([InlineKeyboardButton("⬅️ الرجوع للرئيسية", callback_data="go_home")])
        keyboard.append([InlineKeyboardButton("🗑 مسح الرسالة", callback_data="close")])
        try:
            await query.edit_message_text("📚 <b>اختر المرحلة الدراسية للتصفح:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        except BadRequest:
            pass
        return

    if data == "go_home":
        await start_command(update, context)
        return

    if data.startswith("u_st:"):
        st_id = data.split(":")[1]
        stage = db.get("stages", {}).get(st_id)
        if not stage:
            try:
                await query.edit_message_text("❌ المرحلة غير موجودة.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data="u_st_main")]]))
            except BadRequest:
                pass
            return

        keyboard = []
        for k, v in stage.get("subjects", {}).items():
            keyboard.append([InlineKeyboardButton(f"📖 {v['name']}", callback_data=f"u_sb:{st_id}:{k}")])

        keyboard.append([InlineKeyboardButton("⬅️ الرجوع للمراحل", callback_data="u_st_main")])
        keyboard.append([InlineKeyboardButton("🗑 مسح الرسالة", callback_data="close")])
        safe_st_name = html.escape(stage['name'])
        try:
            await query.edit_message_text(f"📖 <b>مواد ({safe_st_name}):</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        except BadRequest:
            pass
        return

    if data.startswith("u_sb:"):
        _, st_id, sb_id = data.split(":")
        await render_subject_menu(query, st_id, sb_id, user_id)
        return

    if data.startswith("u_sec:"):
        _, st_id, sb_id, sec_type = data.split(":")
        subject = db.get("stages", {}).get(st_id, {}).get("subjects", {}).get(sb_id, {})
        content_list = subject.get("sections", {}).get(sec_type, [])

        back_kb = [
            [InlineKeyboardButton("⬅️ الرجوع للمادة", callback_data=f"u_sb:{st_id}:{sb_id}")],
            [InlineKeyboardButton("🗑 مسح الرسالة", callback_data="close")]
        ]
        
        if not content_list:
            await query.message.reply_text("❌ هذا القسم فارغ حالياً.", reply_markup=InlineKeyboardMarkup(back_kb))
            return

        for item in content_list:
            itype, val, tag = item.get("type"), item.get("value"), item.get("tag", "")
            is_protected = item.get("protect_content", False)
            caption_text = f"🏷 السنة/الدور: {html.escape(tag)}" if tag else ""
            
            try:
                if itype == "pdf":
                    await query.message.reply_document(document=val, caption=caption_text, parse_mode="HTML", protect_content=is_protected)
                elif itype == "image":
                    await query.message.reply_photo(photo=val, caption=caption_text, parse_mode="HTML", protect_content=is_protected)
                elif itype == "text":
                    safe_val = html.escape(val)
                    text_msg = f"{caption_text}\n\n{safe_val}" if caption_text else safe_val
                    await query.message.reply_text(text_msg, parse_mode="HTML", protect_content=is_protected)
            except Exception as e:
                logger.error(f"Error sending item: {e}")
                await query.message.reply_text("⚠️ متعذر إرسال هذا الملف حالياً.")

        await query.message.reply_text("✨ <b>تم عرض كافة الملفات.</b>", reply_markup=InlineKeyboardMarkup(back_kb), parse_mode="HTML")
        return

    if data.startswith("toggle_fav:"):
        _, st_id, sb_id = data.split(":")
        str_user_id = str(user_id)
        if str_user_id not in db["favorites"]:
            db["favorites"][str_user_id] = []

        user_favs = db["favorites"][str_user_id]
        existing = next((f for f in user_favs if f.get("st_id") == st_id and f.get("sb_id") == sb_id), None)

        if existing:
            user_favs.remove(existing)
            await query.answer("🗑 تم مسح المادة من المفضلة", show_alert=True)
        else:
            sb_name = db.get("stages", {}).get(st_id, {}).get("subjects", {}).get(sb_id, {}).get("name", "مادة")
            user_favs.append({"st_id": st_id, "sb_id": sb_id, "name": sb_name})
            await query.answer("⭐ تم إضافة المادة لمفضلتك", show_alert=True)

        save_data(db)
        await render_subject_menu(query, st_id, sb_id, user_id)
        return

    if data == "show_favs":
        str_user_id = str(user_id)
        user_favs = db.get("favorites", {}).get(str_user_id, [])

        back_kb = [
            [InlineKeyboardButton("⬅️ الرجوع للرئيسية", callback_data="go_home")],
            [InlineKeyboardButton("🗑 مسح الرسالة", callback_data="close")]
        ]

        if not user_favs:
            try:
                await query.edit_message_text("⭐ قائمة مفضلتك فارغة حالياً.", reply_markup=InlineKeyboardMarkup(back_kb))
            except BadRequest:
                pass
            return

        keyboard = [[InlineKeyboardButton(f"📖 {f['name']}", callback_data=f"u_sb:{f['st_id']}:{f['sb_id']}")] for f in user_favs]
        keyboard.extend(back_kb)
        try:
            await query.edit_message_text("⭐ <b>المواد المحفوظة في المفضلة:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        except BadRequest:
            pass
        return

    if data == "start_search":
        admin_states[user_id] = {"mode": "searching"}
        cancel_kb = [[InlineKeyboardButton("❌ إلغاء / مسح", callback_data="cancel_state")]]
        await query.message.reply_text("🔍 <b>أرسل اسم المادة أو المرحلة التي تبحث عنها:</b>", reply_markup=InlineKeyboardMarkup(cancel_kb), parse_mode="HTML")
        return

    if data == "start_support":
        admin_states[user_id] = {"mode": "user_support"}
        cancel_kb = [[InlineKeyboardButton("❌ إلغاء / مسح", callback_data="cancel_state")]]
        await query.message.reply_text("💬 <b>اكتب رسالتك أو استفسارك وسوف يصل مباشرة لإدارة البوت:</b>", reply_markup=InlineKeyboardMarkup(cancel_kb), parse_mode="HTML")
        return

    if not is_any_admin(user_id):
        return

    cancel_btn = [InlineKeyboardButton("❌ إلغاء / مسح", callback_data="cancel_state")]
    back_to_panel = [InlineKeyboardButton("⬅️ رجوع للوحة", callback_data="adm_pnl")]

    if data == "set_schedule":
        admin_states[user_id] = {"mode": "setting_schedule"}
        await query.message.reply_text("✍️ <b>أرسل نص جدول الامتحانات أو الدروس الجديد ليتم حفظه:</b>", reply_markup=InlineKeyboardMarkup([cancel_btn]), parse_mode="HTML")
        return

    if data == "up_st":
        stages = db.get("stages", {})
        keyboard = []
        user_sub_access = db.get("sub_admins", {}).get(str(user_id), [])

        for k, v in stages.items():
            if is_full_admin(user_id):
                keyboard.append([InlineKeyboardButton(f"📚 {v['name']}", callback_data=f"up_st_sel:{k}")])
            else:
                has_access = any(isinstance(acc, dict) and acc.get("st_id") == k for acc in user_sub_access)
                if has_access:
                    keyboard.append([InlineKeyboardButton(f"📚 {v['name']}", callback_data=f"up_st_sel:{k}")])

        if not keyboard:
            try:
                await query.edit_message_text("❌ لا تملك صلاحية لأي مرحلة حالياً.", reply_markup=InlineKeyboardMarkup([back_to_panel]))
            except BadRequest:
                pass
            return
            
        keyboard.append(back_to_panel)
        keyboard.append([InlineKeyboardButton("🗑 مسح / إغلاق", callback_data="close")])
        try:
            await query.edit_message_text("اختر المرحلة للرفع فيها:", reply_markup=InlineKeyboardMarkup(keyboard))
        except BadRequest:
            pass
        return

    if data.startswith("up_st_sel:"):
        st_id = data.split(":")[1]
        subjects = db.get("stages", {}).get(st_id, {}).get("subjects", {})
        keyboard = []
        user_sub_access = db.get("sub_admins", {}).get(str(user_id), [])

        for k, v in subjects.items():
            if is_full_admin(user_id):
                keyboard.append([InlineKeyboardButton(f"📖 {v['name']}", callback_data=f"up_sb_sel:{st_id}:{k}")])
            else:
                has_access = any(isinstance(acc, dict) and acc.get("st_id") == st_id and acc.get("sb_id") == k for acc in user_sub_access)
                if has_access:
                    keyboard.append([InlineKeyboardButton(f"📖 {v['name']}", callback_data=f"up_sb_sel:{st_id}:{k}")])

        keyboard.append([InlineKeyboardButton("⬅️ رجوع للمراحل", callback_data="up_st")])
        keyboard.append(back_to_panel)
        try:
            await query.edit_message_text("اختر المادة المطلوبة:", reply_markup=InlineKeyboardMarkup(keyboard))
        except BadRequest:
            pass
        return

    if data.startswith("up_sb_sel:"):
        _, st_id, sb_id = data.split(":")
        keyboard = [
            [InlineKeyboardButton("📚 المحاضرات (PDF)", callback_data=f"start_up:{st_id}:{sb_id}:pdf")],
            [InlineKeyboardButton("📝 الأسئلة (صور)", callback_data=f"start_up:{st_id}:{sb_id}:questions")],
            [InlineKeyboardButton("🎥 الشروحات (Youtube)", callback_data=f"start_up:{st_id}:{sb_id}:youtube")],
            [InlineKeyboardButton("⬅️ رجوع للمواد", callback_data=f"up_st_sel:{st_id}")],
            back_to_panel
        ]
        try:
            await query.edit_message_text("اختر القسم المخصص للرفع:", reply_markup=InlineKeyboardMarkup(keyboard))
        except BadRequest:
            pass
        return

    if data.startswith("start_up:"):
        _, st_id, sb_id, sec_type = data.split(":")
        admin_states[user_id] = {
            "mode": "ask_tag",
            "st_id": st_id,
            "sb_id": sb_id,
            "sec_type": sec_type,
            "count": 0,
            "tag": ""
        }
        await query.message.reply_text("✍️ <b>أرسل تصنيف الملفات (السنة والدور) لتنظيمها.</b>\nمثال: <code>2024 - الدور الأول</code>\n(أو أرسل كلمة <code>تخطي</code>):", 
            reply_markup=InlineKeyboardMarkup([cancel_btn]), parse_mode="HTML")
        return

    if not is_full_admin(user_id):
        return

    if data == "stats":
        total_users = len(db.get("users", []))
        total_banned = len(db.get("banned_users", []))
        total_stages = len(db.get("stages", {}))
        total_subjects = sum(len(st.get("subjects", {})) for st in db.get("stages", {}).values())

        stats_msg = (
            "📊 <b>الإحصائيات المتقدمة:</b>\n\n"
            f"👤 <b>المستخدمين الكلي:</b> <code>{total_users}</code>\n"
            f"🚫 <b>المحظورين:</b> <code>{total_banned}</code>\n"
            f"📚 <b>المراحل:</b> <code>{total_stages}</code>\n"
            f"📖 <b>المواد:</b> <code>{total_subjects}</code>"
        )
        keyboard = [back_to_panel, [InlineKeyboardButton("🗑 مسح", callback_data="close")]]
        try:
            await query.edit_message_text(stats_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        except BadRequest:
            pass
        return

    if data == "backup_db":
        try:
            await query.message.reply_document(document=DATA_FILE, filename="backup_data.json", caption="💾 <b>نسخة احتياطية لقاعدة البيانات.</b>", parse_mode="HTML")
        except Exception as e:
            await query.message.reply_text(f"❌ خطأ عند إرسال النسخة الاحتياطية: {e}")
        return

    if data == "add_st":
        admin_states[user_id] = {"mode": "add_st"}
        await query.message.reply_text("✍️ <b>أرسل الآن اسم المرحلة الجديدة:</b>", reply_markup=InlineKeyboardMarkup([cancel_btn]), parse_mode="HTML")
        return

    if data == "add_sb":
        stages = db.get("stages", {})
        if not stages:
            try:
                await query.edit_message_text("❌ أضف مرحلة واحدة على الأقل أولاً!", reply_markup=InlineKeyboardMarkup([back_to_panel]))
            except BadRequest:
                pass
            return
        keyboard = [[InlineKeyboardButton(f"📚 {v['name']}", callback_data=f"sel_st_sb:{k}")] for k, v in stages.items()]
        keyboard.append(back_to_panel)
        try:
            await query.edit_message_text("اختر المرحلة التي تريد إضافة المادة إليها:", reply_markup=InlineKeyboardMarkup(keyboard))
        except BadRequest:
            pass
        return

    if data.startswith("sel_st_sb:"):
        st_id = data.split(":")[1]
        admin_states[user_id] = {"mode": "add_sb", "st_id": st_id}
        await query.message.reply_text("✍️ <b>أرسل الآن اسم المادة الجديدة:</b>", reply_markup=InlineKeyboardMarkup([cancel_btn]), parse_mode="HTML")
        return

    if data == "del_menu":
        keyboard = [
            [InlineKeyboardButton("🗑 حذف مرحلة بالكامل", callback_data="del_st_list")],
            [InlineKeyboardButton("🗑 حذف مادة فقط", callback_data="del_sb_st_list")],
            back_to_panel
        ]
        try:
            await query.edit_message_text("⚠️ <b>اختر ماذا تريد أن تحذف:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        except BadRequest:
            pass
        return

    if data == "del_st_list":
        stages = db.get("stages", {})
        keyboard = [[InlineKeyboardButton(f"🗑 {v['name']}", callback_data=f"do_del_st:{k}")] for k, v in stages.items()]
        keyboard.append([InlineKeyboardButton("⬅️ رجوع", callback_data="del_menu")])
        try:
            await query.edit_message_text("⚠️ <b>اختر المرحلة التي تريد حذفها نهائياً:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        except BadRequest:
            pass
        return

    if data.startswith("do_del_st:"):
        st_id = data.split(":")[1]
        if st_id in db["stages"]:
            del db["stages"][st_id]
            save_data(db)
            await query.answer("✅ تم حذف المرحلة بالكامل.", show_alert=True)
        
        stages = db.get("stages", {})
        keyboard = [[InlineKeyboardButton(f"🗑 {v['name']}", callback_data=f"do_del_st:{k}")] for k, v in stages.items()]
        keyboard.append([InlineKeyboardButton("⬅️ رجوع", callback_data="del_menu")])
        try:
            await query.edit_message_text("⚠️ <b>اختر المرحلة التي تريد حذفها نهائياً:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        except BadRequest:
            pass
        return

    if data == "del_sb_st_list":
        stages = db.get("stages", {})
        keyboard = [[InlineKeyboardButton(f"📚 {v['name']}", callback_data=f"del_sb_list:{k}")] for k, v in stages.items()]
        keyboard.append([InlineKeyboardButton("⬅️ رجوع", callback_data="del_menu")])
        try:
            await query.edit_message_text("اختر المرحلة التي بداخلها المادة المراد حذفها:", reply_markup=InlineKeyboardMarkup(keyboard))
        except BadRequest:
            pass
        return

    if data.startswith("del_sb_list:"):
        st_id = data.split(":")[1]
        subjects = db.get("stages", {}).get(st_id, {}).get("subjects", {})
        keyboard = [[InlineKeyboardButton(f"🗑 {v['name']}", callback_data=f"do_del_sb:{st_id}:{k}")] for k, v in subjects.items()]
        keyboard.append([InlineKeyboardButton("⬅️ رجوع", callback_data="del_sb_st_list")])
        try:
            await query.edit_message_text("⚠️ <b>اختر المادة المراد حذفها نهائياً:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        except BadRequest:
            pass
        return

    if data.startswith("do_del_sb:"):
        _, st_id, sb_id = data.split(":")
        if st_id in db["stages"] and sb_id in db["stages"][st_id]["subjects"]:
            del db["stages"][st_id]["subjects"][sb_id]
            save_data(db)
            await query.answer("✅ تم حذف المادة بنجاح.", show_alert=True)
            
        subjects = db.get("stages", {}).get(st_id, {}).get("subjects", {})
        keyboard = [[InlineKeyboardButton(f"🗑 {v['name']}", callback_data=f"do_del_sb:{st_id}:{k}")] for k, v in subjects.items()]
        keyboard.append([InlineKeyboardButton("⬅️ رجوع", callback_data="del_sb_st_list")])
        try:
            await query.edit_message_text("⚠️ <b>اختر المادة المراد حذفها نهائياً:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        except BadRequest:
            pass
        return

    if data == "broadcast_all":
        admin_states[user_id] = {"mode": "broadcasting_all"}
        await query.message.reply_text("✍️ <b>أرسل رسالة الإذاعة (ستصل لجميع المشتركين):</b>", reply_markup=InlineKeyboardMarkup([cancel_btn]), parse_mode="HTML")
        return

    if data == "broadcast_target":
        stages = db.get("stages", {})
        keyboard = [[InlineKeyboardButton(f"🎯 إذاعة لـ {v['name']}", callback_data=f"do_broad_st:{k}")] for k, v in stages.items()]
        keyboard.append(back_to_panel)
        try:
            await query.edit_message_text("اختر المرحلة التي تريد إرسال الإشعار لطلابها فقط:", reply_markup=InlineKeyboardMarkup(keyboard))
        except BadRequest:
            pass
        return

    if data.startswith("do_broad_st:"):
        st_id = data.split(":")[1]
        st_name = html.escape(db["stages"][st_id]["name"])
        admin_states[user_id] = {"mode": "broadcasting_st", "st_id": st_id}
        await query.message.reply_text(f"✍️ <b>أرسل رسالة أو ملف الإذاعة (نص، صورة، ملف، شرح) لطلاب مرحلة {st_name}:</b>", reply_markup=InlineKeyboardMarkup([cancel_btn]), parse_mode="HTML")
        return
        
    if data == "set_group_link":
        stages = db.get("stages", {})
        keyboard = [[InlineKeyboardButton(f"📚 {v['name']}", callback_data=f"grp_st:{k}")] for k, v in stages.items()]
        keyboard.append(back_to_panel)
        try:
            await query.edit_message_text("اختر المرحلة لإضافة رابط جروب لمادتها:", reply_markup=InlineKeyboardMarkup(keyboard))
        except BadRequest:
            pass
        return

    if data == "ban_usr":
        admin_states[user_id] = {"mode": "ban_user_id"}
        await query.message.reply_text("✍️ <b>أرسل الآيدي (ID) الخاص بالمستخدم المراد حظره:</b>", reply_markup=InlineKeyboardMarkup([cancel_btn]), parse_mode="HTML")
        return

    if data == "unban_usr":
        admin_states[user_id] = {"mode": "unban_user_id"}
        await query.message.reply_text("✍️ <b>أرسل الآيدي (ID) الخاص بالمستخدم المراد فك حظره:</b>", reply_markup=InlineKeyboardMarkup([cancel_btn]), parse_mode="HTML")
        return
        
    if data.startswith("grp_st:"):
        st_id = data.split(":")[1]
        subjects = db.get("stages", {}).get(st_id, {}).get("subjects", {})
        keyboard = [[InlineKeyboardButton(f"📖 {v['name']}", callback_data=f"grp_sb:{st_id}:{k}")] for k, v in subjects.items()]
        keyboard.append([InlineKeyboardButton("⬅️ رجوع", callback_data="set_group_link")])
        try:
            await query.edit_message_text("اختر المادة:", reply_markup=InlineKeyboardMarkup(keyboard))
        except BadRequest:
            pass
        return
        
    if data.startswith("grp_sb:"):
        _, st_id, sb_id = data.split(":")
        admin_states[user_id] = {"mode": "setting_grp_link", "st_id": st_id, "sb_id": sb_id}
        await query.message.reply_text("✍️ <b>أرسل رابط جروب التليجرام الخاص بهذه المادة:</b>", reply_markup=InlineKeyboardMarkup([cancel_btn]), parse_mode="HTML")
        return

    if data == "add_subadmin":
        admin_states[user_id] = {"mode": "add_subadmin_id"}
        await query.message.reply_text("✍️ <b>أرسل الآيدي (ID) الخاص بالمشرف الجديد:</b>", reply_markup=InlineKeyboardMarkup([cancel_btn]), parse_mode="HTML")
        return

    if data.startswith("subadm_st:"):
        parts = data.split(":")
        target_id, st_id = parts[1], parts[2]
        subjects = db.get("stages", {}).get(st_id, {}).get("subjects", {})
        keyboard = [[InlineKeyboardButton(f"📖 {v['name']}", callback_data=f"subadm_sb:{target_id}:{st_id}:{k}")] for k, v in subjects.items()]
        keyboard.append([InlineKeyboardButton("🗑 إغلاق", callback_data="close")])
        try:
            await query.edit_message_text("اختر المرحلة التي يُسمح له بالرفع فيها:", reply_markup=InlineKeyboardMarkup(keyboard))
        except BadRequest:
            pass
        return

    if data.startswith("subadm_sb:"):
        _, target_id, st_id, sb_id = data.split(":")
        if target_id not in db["sub_admins"]: db["sub_admins"][target_id] = []
        db["sub_admins"][target_id].append({"st_id": st_id, "sb_id": sb_id})
        save_data(db)
        try:
            await query.edit_message_text(f"✅ تم إضافة الصلاحية بنجاح للمشرف (ID: {target_id}).", reply_markup=InlineKeyboardMarkup([back_to_panel]))
        except BadRequest:
            pass
        return

    if data.startswith("reply_to:"):
        target_id = int(data.split(":")[1])
        admin_states[user_id] = {"mode": "replying_support", "target_id": target_id}
        await query.message.reply_text(f"✍️ <b>اكتب ردك للطالب (ID: {target_id}):</b>", reply_markup=InlineKeyboardMarkup([cancel_btn]), parse_mode="HTML")
        return

# =========================
# 5. معالج المدخلات المباشرة
# =========================
async def input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    if is_banned(user_id): return
    update_user_data(user)

    user_stage = get_user_stage_id(user_id)
    stages = db.get("stages", {})
    if not user_stage and not is_any_admin(user_id):
        if stages:
            keyboard = [[InlineKeyboardButton(f"🎓 {v['name']}", callback_data=f"set_primary_stage:{k}")] for k, v in stages.items()]
            await update.message.reply_text("⚠️ يرجى اختيار **مرحلتك الدراسية الأساسية** لمرة واحدة أولاً للمتابعة:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            return

    if user_id in admin_states:
        state = admin_states[user_id]
        mode = state.get("mode")

        if mode == "student_contrib_upload":
            st_id = state.get("st_id")
            del admin_states[user_id]

            contrib_item = {"uploader_name": user.full_name, "uploader_id": user_id}
            if update.message.document:
                contrib_item.update({"type": "pdf", "value": update.message.document.file_id, "caption": update.message.caption or ""})
            elif update.message.photo:
                contrib_item.update({"type": "image", "value": update.message.photo[-1].file_id, "caption": update.message.caption or ""})
            elif update.message.text:
                contrib_item.update({"type": "text", "value": update.message.text.strip(), "caption": ""})
            else:
                await update.message.reply_text("⚠️ نوع الملف غير مدعوم.")
                return

            st_name = db.get("stages", {}).get(st_id, {}).get("name", "المرحلة")
            
            for adm in db.get("admins", []):
                try:
                    kb = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("✅ موافقة ونشر", callback_data=f"approve_contrib:{st_id}:{user_id}"),
                            InlineKeyboardButton("❌ رفض", callback_data=f"reject_contrib:{st_id}:{user_id}")
                        ]
                    ])
                    db.setdefault("pending_contribs", {})[str(user_id)] = {"st_id": st_id, "item": contrib_item}
                    save_data(db)

                    await context.bot.send_message(
                        chat_id=adm,
                        text=f"💡 <b>طلب ملخص جديد من طالب:</b>\n👤 الطالب: {html.escape(user.full_name)}\n📚 المرحلة: {html.escape(st_name)}\n\nيرجى المعاينة:",
                        reply_markup=kb,
                        parse_mode="HTML"
                    )
                    if contrib_item["type"] == "pdf":
                        await context.bot.send_document(chat_id=adm, document=contrib_item["value"], caption=contrib_item.get("caption",""))
                    elif contrib_item["type"] == "image":
                        await context.bot.send_photo(chat_id=adm, photo=contrib_item["value"], caption=contrib_item.get("caption",""))
                    elif contrib_item["type"] == "text":
                        await context.bot.send_message(chat_id=adm, text=contrib_item["value"])
                except Exception as e:
                    logger.error(f"Failed sending contrib to admin {adm}: {e}")

            await update.message.reply_text("✅ <b>تم إرسال ملخصك بنجاح إلى الإدارة للمراجعة، وسيتم نشره فور الموافقة عليه!</b>", parse_mode="HTML")
            return

        if mode == "setting_schedule" and is_full_admin(user_id):
            sched_text = update.message.text.strip() if update.message.text else ""
            db["schedule_info"] = sched_text
            save_data(db)
            del admin_states[user_id]
            await update.message.reply_text("✅ تم تحديث جدول الامتحانات والدروس بنجاح!")
            return

        if mode == "searching":
            del admin_states[user_id]
            q = update.message.text.strip().lower() if update.message.text else ""
            results = []
            for st_id, st_val in db.get("stages", {}).items():
                for sb_id, sb_val in st_val.get("subjects", {}).items():
                    if q in sb_val["name"].lower() or q in st_val["name"].lower():
                        results.append((st_val["name"], sb_val["name"], st_id, sb_id))

            if not results:
                await update.message.reply_text("❌ لم يتم العثور على نتائج.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🗑 مسح", callback_data="close")]]))
                return

            keyboard = [[InlineKeyboardButton(f"📚 {r[0]} - 📖 {r[1]}", callback_data=f"u_sb:{r[2]}:{r[3]}")] for r in results]
            keyboard.append([InlineKeyboardButton("🗑 مسح", callback_data="close")])
            await update.message.reply_text("🔍 <b>نتائج البحث:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            return

        if mode == "user_support":
            del admin_states[user_id]
            msg = update.message.text or "محتوى غير نصي"
            safe_name = html.escape(user.full_name)
            safe_msg = html.escape(msg)
            kb = [[InlineKeyboardButton("💬 رد على هذا الطالب", callback_data=f"reply_to:{user_id}")]]
            
            for adm in db.get("admins", []):
                try:
                    await context.bot.send_message(
                        chat_id=adm,
                        text=f"📩 <b>رسالة جديدة من طالب:</b>\n👤 <b>الاسم:</b> {safe_name}\n🆔 <b>الآيدي:</b> <code>{user_id}</code>\n\n💬 <b>الرسالة:</b>\n{safe_msg}",
                        reply_markup=InlineKeyboardMarkup(kb),
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Failed to deliver support msg to admin {adm}: {e}")
            await update.message.reply_text("✅ تم إرسال رسالتك للإدارة بنجاح.")
            return

        if mode == "replying_support" and is_full_admin(user_id):
            target_id = state.get("target_id")
            del admin_states[user_id]
            reply_text = html.escape(update.message.text or "")
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=f"💬 <b>رد من إدارة البوت:</b>\n\n{reply_text}",
                    parse_mode="HTML"
                )
                await update.message.reply_text("✅ تم إرسال الرد للطالب.")
            except Exception as e:
                await update.message.reply_text(f"❌ فشل الإرسال: {e}")
            return

        if mode == "ask_tag" and is_any_admin(user_id):
            tag_text = update.message.text.strip() if update.message.text else "تخطي"
            if tag_text.lower() == "تخطي":
                state["tag"] = ""
            else:
                state["tag"] = tag_text
                
            state["mode"] = "uploading"
            cancel_done = [
                [InlineKeyboardButton("✅ إنهاء الرفع (/done)", callback_data="cancel_state")]
            ]
            await update.message.reply_text("📥 <b>ممتاز! أرسل الملفات الآن، واضغط إنهاء عند اكتمال الرفع.</b>", reply_markup=InlineKeyboardMarkup(cancel_done), parse_mode="HTML")
            return

        if mode == "uploading" and is_any_admin(user_id):
            tag = state.get("tag", "")

            item_data = {"tag": tag}
            if update.message.document:
                item_data.update({"type": "pdf", "value": update.message.document.file_id})
            elif update.message.photo:
                item_data.update({"type": "image", "value": update.message.photo[-1].file_id})
            elif update.message.text:
                item_data.update({"type": "text", "value": update.message.text.strip()})
            else:
                await update.message.reply_text("⚠️ نوع الملف غير مدعوم حالياً. يرجى إرسال ملف PDF، صورة، أو نص فقط.")
                return

            state["mode"] = "ask_protect"
            state["temp_item"] = item_data

            protect_kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🔒 ممنوع التوجيه", callback_data="set_protect:true"),
                    InlineKeyboardButton("🔓 مسموح التوجيه", callback_data="set_protect:false")
                ]
            ])
            await update.message.reply_text("⚙️ <b>هل تريد السماح بإعادة توجيه وحفظ هذا الملف؟</b>", reply_markup=protect_kb, parse_mode="HTML")
            return

        if not is_full_admin(user_id): return
        
        if mode == "add_st":
            name = update.message.text.strip() if update.message.text else "مرحلة جديدة"
            st_id = f"s{int(time.time())}"
            db["stages"][st_id] = {"name": name, "subjects": {}}
            save_data(db)
            del admin_states[user_id]
            safe_st_name = html.escape(name)
            await update.message.reply_text(f"✅ تمت إضافة المرحلة: <b>{safe_st_name}</b>", parse_mode="HTML")
            return

        if mode == "add_sb":
            name = update.message.text.strip() if update.message.text else "مادة جديدة"
            st_id = state.get("st_id")
            sb_id = f"sub{int(time.time())}"
            if st_id in db.get("stages", {}):
                db["stages"][st_id]["subjects"][sb_id] = {
                    "name": name,
                    "sections": {"pdf": [], "questions": [], "youtube": []}
                }
                save_data(db)
                del admin_states[user_id]
                safe_sb_name = html.escape(name)
                await update.message.reply_text(f"✅ تمت إضافة المادة: <b>{safe_sb_name}</b>", parse_mode="HTML")
            else:
                del admin_states[user_id]
                await update.message.reply_text("❌ حدث خطأ، المرحلة غير موجودة.")
            return

        if mode == "setting_grp_link":
            st_id, sb_id = state.get("st_id"), state.get("sb_id")
            link = update.message.text.strip() if update.message.text else ""
            if st_id in db.get("stages", {}) and sb_id in db["stages"][st_id].get("subjects", {}):
                db["stages"][st_id]["subjects"][sb_id]["discussion_link"] = link
                save_data(db)
                await update.message.reply_text("✅ تم ربط جروب المناقشة بالمادة بنجاح!")
            else:
                await update.message.reply_text("❌ حدث خطأ، المادة غير موجودة.")
            del admin_states[user_id]
            return

        if mode == "ban_user_id":
            target_str = update.message.text.strip() if update.message.text else ""
            if target_str.isdigit():
                target_id = int(target_str)
                if target_id not in db["banned_users"]:
                    db["banned_users"].append(target_id)
                    save_data(db)
                del admin_states[user_id]
                await update.message.reply_text(f"✅ تم حظر المستخدم <code>{target_id}</code> بنجاح.", parse_mode="HTML")
            else:
                await update.message.reply_text("❌ يرجى إدخال ID صالح (أرقام فقط).")
            return

        if mode == "unban_user_id":
            target_str = update.message.text.strip() if update.message.text else ""
            if target_str.isdigit():
                target_id = int(target_str)
                if target_id in db["banned_users"]:
                    db["banned_users"].remove(target_id)
                    save_data(db)
                del admin_states[user_id]
                await update.message.reply_text(f"✅ تم فك الحظر عن المستخدم <code>{target_id}</code> بنجاح.", parse_mode="HTML")
            else:
                await update.message.reply_text("❌ يرجى إدخال ID صالح (أرقام فقط).")
            return
            
        if mode == "add_subadmin_id":
            target_id = update.message.text.strip() if update.message.text else ""
            if not target_id.isdigit():
                await update.message.reply_text("❌ الآيدي يجب أن يكون أرقاماً فقط.")
                return
            stages = db.get("stages", {})
            keyboard = [[InlineKeyboardButton(f"📚 {v['name']}", callback_data=f"subadm_st:{target_id}:{k}")] for k, v in stages.items()]
            keyboard.append([InlineKeyboardButton("🗑 إلغاء", callback_data="close")])
            await update.message.reply_text("اختر المرحلة الدراسية للصلاحية:", reply_markup=InlineKeyboardMarkup(keyboard))
            del admin_states[user_id]
            return

        if mode == "broadcasting_all":
            del admin_states[user_id]
            msg = html.escape(update.message.text or "")
            count = 0
            for u in db.get("users", []):
                try:
                    await context.bot.send_message(chat_id=u, text=f"📢 <b>إشعار عام:</b>\n\n{msg}", parse_mode="HTML")
                    count += 1
                except Exception:
                    pass
            await update.message.reply_text(f"✅ تم الإرسال إلى {count} مستخدم.")
            return

        if mode == "broadcasting_st":
            st_id = state.get("st_id")
            
            msg_data = {}
            if update.message.document:
                msg_data = {"type": "document", "value": update.message.document.file_id, "caption": update.message.caption or ""}
            elif update.message.photo:
                msg_data = {"type": "photo", "value": update.message.photo[-1].file_id, "caption": update.message.caption or ""}
            elif update.message.video:
                msg_data = {"type": "video", "value": update.message.video.file_id, "caption": update.message.caption or ""}
            elif update.message.text:
                msg_data = {"type": "text", "value": update.message.text.strip()}
            else:
                await update.message.reply_text("⚠️ نوع المحتوى غير مدعوم للاذاعة.")
                return

            state["mode"] = "broadcasting_st_protect"
            state["msg_data"] = msg_data

            protect_kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🔒 ممنوع التوجيه", callback_data="broadcast_protect:true"),
                    InlineKeyboardButton("🔓 مسموح التوجيه", callback_data="broadcast_protect:false")
                ]
            ])
            await update.message.reply_text("⚙️ <b>هل تريد السماح بإعادة توجيه محتوى الإذاعة للمرحلة؟</b>", reply_markup=protect_kb, parse_mode="HTML")
            return

async def handle_contrib_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    if data.startswith("approve_contrib:"):
        _, st_id, u_id_str = data.split(":")
        pending = db.get("pending_contribs", {}).get(u_id_str)
        if pending:
            p_st_id = pending["st_id"]
            p_item = pending["item"]
            if p_st_id not in db["student_contributions"]:
                db["student_contributions"][p_st_id] = []
            db["student_contributions"][p_st_id].append(p_item)
            save_data(db)
            
            try:
                await context.bot.send_message(chat_id=int(u_id_str), text="🎉 <b>مبارك! تمت الموافقة على ملخصك ونشره في قسم شروحات وملخصات الطلبة.</b>", parse_mode="HTML")
            except Exception:
                pass
        await query.answer("✅ تمت الموافقة ونشر الملخص في البوت بنجاح!", show_alert=True)
        try:
            await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ تم النشر رسمياً", callback_data="close")]]))
        except BadRequest:
            pass

# =========================
# 6. التشغيل الرئيسي
# =========================
def main():
    request = HTTPXRequest(
        connect_timeout=60.0,
        read_timeout=60.0,
        write_timeout=60.0,
        pool_timeout=60.0
    )
    
    # بناء التطبيق بالطريقة العادية
    app = Application.builder().token(TOKEN).request(request).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("panel", panel_command))
    app.add_handler(CommandHandler("done", done_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    
    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, input_handler))

    print("==========================================")
    print("🚀 تم تشغيل البوت بنجاح تام!")
    print("==========================================")

    # تشغيل مباشر مع التقاط أي خطأ شبكي وإعادة المحاولة بذكاء
    while True:
        try:
            # استخدام التشغيل اليدوي للآبديت لتجنب انهيار التهيئة التلقائية
            import asyncio
            async def run_bot():
                await app.initialize()
                await app.start()
                await app.updater.start_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
                
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # إذا كانت حلقة العمل تعمل مسبقاً
                pass
            else:
                asyncio.run(run_bot())
                
        except Exception as e:
            print(f"⚠️ خطأ في الاتصال (Bad Gateway / Network): {e}. إعادة المحاولة خلال 10 ثوانٍ...")
            import time
            time.sleep(10)

if __name__ == "__main__":
    main()
