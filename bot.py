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
    "schedule_info": {"type": "text", "value": "📅 لا يوجد جدول مضاف حالياً."},
    "faq_info": {
        "سعي": {"type": "text", "value": "📊 **احتساب السعي:** يتم احتساب السعي بناءً على درجات امتحانات الفاينل والميد والنشاط اليومي."},
        "عبور": {"type": "text", "value": "⚖️ **شروط العبور (التحميل):** يحق للطالب العبور بمادتين كحد أقصى من المرحلة الحالية."},
        "قاعات": {"type": "text", "value": "📍 **القاعات والمختبرات:** يرجى مراجعة لوحة الإعلانات في قسمك لمعرفة جدول القاعات."}
    },
    "student_contributions": {},
    "pending_contribs": {}
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
                    if "pending_contribs" not in loaded: loaded["pending_contribs"] = {}
                    
                    if isinstance(loaded["schedule_info"], str):
                        loaded["schedule_info"] = {"type": "text", "value": loaded["schedule_info"]}
                    
                    for k, v in list(loaded["faq_info"].items()):
                        if isinstance(v, str):
                            loaded["faq_info"][k] = {"type": "text", "value": v}

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
        [InlineKeyboardButton("📚 المراحل والمناهج", callback_data="u_st_main"), InlineKeyboardButton("💡 ملخصات الطلبة", callback_data="student_contrib_main")],
        [InlineKeyboardButton("📅 جدول الامتحانات", callback_data="show_schedule"), InlineKeyboardButton("🤖 الأسئلة الشائعة", callback_data="show_faq")],
        [InlineKeyboardButton("🔍 بحث سريع", callback_data="start_search"), InlineKeyboardButton("⭐ مفضلتي", callback_data="show_favs")],
        [InlineKeyboardButton("🔄 تغيير المرحلة الأساسية", callback_data="change_my_stage")],
        [InlineKeyboardButton("🎥 قناة اليوتيوب", url=YOUTUBE_URL), InlineKeyboardButton("💬 تواصل مع الإدارة", callback_data="start_support")],
        [InlineKeyboardButton("🗑 مسح الرسالة", callback_data="close")]
    ]

    safe_name = html.escape(user.first_name)
    welcome_text = (
        f"✨ <b>البوت التعليمي الرسمي</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👑 <b>المطور والمهندس:</b> <code>مقتدى عامر</code>\n"
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
            [InlineKeyboardButton("📥 رفع محتوى للمواد", callback_data="up_st"), InlineKeyboardButton("🗑 حذف مراحل/مواد", callback_data="del_menu")],
            [InlineKeyboardButton("📅 إدارة الجدول", callback_data="set_schedule"), InlineKeyboardButton("🤖 إدارة الأسئلة الشائعة", callback_data="manage_faq")],
            [InlineKeyboardButton("📢 إذاعة للكل", callback_data="broadcast_all"), InlineKeyboardButton("🎯 إذاعة لمرحلة", callback_data="broadcast_target")],
            [InlineKeyboardButton("👥 رابط مناقشة لمادة", callback_data="set_group_link"), InlineKeyboardButton("👑 إضافة مشرف", callback_data="add_subadmin")],
            [InlineKeyboardButton("📊 الإحصائيات", callback_data="stats"), InlineKeyboardButton("💾 نسخة احتياطية", callback_data="backup_db")],
            [InlineKeyboardButton("🚫 حظر مستخدم", callback_data="ban_usr"), InlineKeyboardButton("✅ فك الحظر", callback_data="unban_usr")],
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
        sched_data = db.get("schedule_info", {"type": "text", "value": "📅 لا يوجد جدول مضاف حالياً."})
        back_kb = [[InlineKeyboardButton("⬅️ الرجوع للرئيسية", callback_data="go_home")], [InlineKeyboardButton("🗑 مسح", callback_data="close")]]
        
        stype = sched_data.get("type", "text")
        val = sched_data.get("value", "")
        caption = sched_data.get("caption", "📅 <b>جدول الامتحانات والدروس:</b>")

        try:
            if stype == "photo":
                await query.message.reply_photo(photo=val, caption=caption, reply_markup=InlineKeyboardMarkup(back_kb), parse_mode="HTML")
            elif stype == "pdf":
                await query.message.reply_document(document=val, caption=caption, reply_markup=InlineKeyboardMarkup(back_kb), parse_mode="HTML")
            else:
                await query.edit_message_text(f"📅 <b>جدول الامتحانات والدروس:</b>\n\n{val}", reply_markup=InlineKeyboardMarkup(back_kb), parse_mode="HTML")
        except Exception as e:
            logger.error(f"Error showing schedule: {e}")
            await query.message.reply_text(f"📅 <b>جدول الامتحانات والدروس:</b>\n\n{val}", reply_markup=InlineKeyboardMarkup(back_kb), parse_mode="HTML")
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
        faq_data = db.get("faq_info", {}).get(faq_key)
        back_kb = [[InlineKeyboardButton("⬅️ الرجوع للأسئلة الشائعة", callback_data="show_faq")]]
        
        if not faq_data:
            await query.answer("❌ السؤال غير موجود.", show_alert=True)
            return

        ftype = faq_data.get("type", "text")
        val = faq_data.get("value", "")
        caption = faq_data.get("caption", f"💡 <b>سؤال: {faq_key}</b>")

        try:
            if ftype == "photo":
                await query.message.reply_photo(photo=val, caption=f"💡 <b>{faq_key}</b>\n\n{caption}", reply_markup=InlineKeyboardMarkup(back_kb), parse_mode="HTML")
            elif ftype == "pdf":
                await query.message.reply_document(document=val, caption=f"💡 <b>{faq_key}</b>\n\n{caption}", reply_markup=InlineKeyboardMarkup(back_kb), parse_mode="HTML")
            else:
                await query.edit_message_text(f"💡 <b>{faq_key}:</b>\n\n{val}", reply_markup=InlineKeyboardMarkup(back_kb), parse_mode="HTML")
        except Exception as e:
            logger.error(f"Error fetching FAQ: {e}")
        return

    # معالجة الموافقة والرفض لملخصات الطلبة
    if data.startswith("approve_contrib:") or data.startswith("reject_contrib:"):
        parts = data.split(":")
        action, st_id, u_id_str = parts[0], parts[1], parts[2]
        pending = db.get("pending_contribs", {}).get(u_id_str)
        
        if pending:
            p_item = pending["item"]
            if action == "approve_contrib":
                if st_id not in db["student_contributions"]:
                    db["student_contributions"][st_id] = []
                db["student_contributions"][st_id].append(p_item)
                save_data(db)
                try:
                    await context.bot.send_message(chat_id=int(u_id_str), text="🎉 <b>مبارك! تمت الموافقة على ملخصك ونشره في قسم شروحات وملخصات الطلبة.</b>", parse_mode="HTML")
                except Exception:
                    pass
                await query.answer("✅ تمت الموافقة ونشر الملخص بنجاح!", show_alert=True)
            else:
                try:
                    await context.bot.send_message(chat_id=int(u_id_str), text="❌ نعتذر، تم رفض الملخص المرسل من قبل الإدارة.", parse_mode="HTML")
                except Exception:
                    pass
                await query.answer("❌ تم رفض الملخص.", show_alert=True)
            
            if u_id_str in db["pending_contribs"]:
                del db["pending_contribs"][u_id_str]
                save_data(db)

            try:
                action_text = "✅ تم قبول ونشر الملخص" if action == "approve_contrib" else "❌ تم رفض الملخص"
                await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(action_text, callback_data="close")]]))
            except BadRequest:
                pass
        else:
            await query.answer("⚠️ هذا الطلب غير موجود أو تم التعامل معه مسبقاً.", show_alert=True)
        return

    if not is_any_admin(user_id):
        return

    cancel_btn = [InlineKeyboardButton("❌ إلغاء / مسح", callback_data="cancel_state")]
    back_to_panel = [InlineKeyboardButton("⬅️ رجوع للوحة", callback_data="adm_pnl")]

    if data == "set_schedule":
        keyboard = [
            [InlineKeyboardButton("✍️ تعديل/رفع جدول جديد", callback_data="upload_sched_now")],
            [InlineKeyboardButton("🗑 حذف الجدول الحالي", callback_data="delete_sched_now")],
            back_to_panel
        ]
        try:
            await query.edit_message_text("📅 <b>إدارة جدول الامتحانات والدروس:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        except BadRequest:
            pass
        return

    if data == "upload_sched_now":
        admin_states[user_id] = {"mode": "setting_schedule"}
        await query.message.reply_text("✍️ <b>أرسل الآن جدول الامتحانات (نص، صورة، أو ملف PDF):</b>", reply_markup=InlineKeyboardMarkup([cancel_btn]), parse_mode="HTML")
        return

    if data == "delete_sched_now":
        db["schedule_info"] = {"type": "text", "value": "📅 لا يوجد جدول مضاف حالياً."}
        save_data(db)
        await query.answer("✅ تم حذف الجدول الحالي بنجاح!", show_alert=True)
        await panel_command(update, context)
        return

    if data == "manage_faq":
        keyboard = [
            [InlineKeyboardButton("➕ إضافة سؤال شائع جديد", callback_data="add_faq_title")],
            [InlineKeyboardButton("🗑 حذف سؤال شائع", callback_data="del_faq_list")],
            back_to_panel
        ]
        try:
            await query.edit_message_text("⚙️ <b>لوحة إعدادات وتحديث الأسئلة الشائعة:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        except BadRequest:
            pass
        return

    if data == "add_faq_title":
        admin_states[user_id] = {"mode": "add_faq_title"}
        await query.message.reply_text("✍️ <b>اكتب اسم/عنوان السؤال الشائع الجديد:</b>\nمثال: <code>سعي المادة</code> أو <code>موعد الفاينل</code>", reply_markup=InlineKeyboardMarkup([cancel_btn]), parse_mode="HTML")
        return

    if data == "del_faq_list":
        faqs = db.get("faq_info", {})
        if not faqs:
            await query.answer("❌ لا توجد أسئلة شائعة حالياً للحذف.", show_alert=True)
            return
        keyboard = [[InlineKeyboardButton(f"🗑 {k}", callback_data=f"do_del_faq:{k}")] for k, v in faqs.items()]
        keyboard.append([InlineKeyboardButton("⬅️ رجوع", callback_data="manage_faq")])
        try:
            await query.edit_message_text("⚠️ <b>اختر السؤال المراد حذفه نهائياً:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        except BadRequest:
            pass
        return

    if data.startswith("do_del_faq:"):
        faq_key = data.split(":")[1]
        if faq_key in db.get("faq_info", {}):
            del db["faq_info"][faq_key]
            save_data(db)
            await query.answer(f"✅ تم حذف السؤال ({faq_key}) بنجاح.", show_alert=True)
        
        faqs = db.get("faq_info", {})
        keyboard = [[InlineKeyboardButton(f"🗑 {k}", callback_data=f"do_del_faq:{k}")] for k, v in faqs.items()]
        keyboard.append([InlineKeyboardButton("⬅️ رجوع", callback_data="manage_faq")])
        try:
            await query.edit_message_text("⚠️ <b>اختر السؤال المراد حذفه نهائياً:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        except BadRequest:
            pass
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
        if not stages:
            await query.answer("❌ لا توجد مراحل للحذف.", show_alert=True)
            return
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
        keyboard = [[InlineKeyboardButton(f"🗑 {v['name']}", callback_data=f"do_del_st:{k}")] for k, v in stages.items()] if stages else []
        keyboard.append([InlineKeyboardButton("⬅️ رجوع", callback_data="del_menu")])
        try:
            await query.edit_message_text("⚠️ <b>اختر المرحلة التي تريد حذفها نهائياً:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        except BadRequest:
            pass
        return

    if data == "del_sb_st_list":
        stages = db.get("stages", {})
        if not stages:
            await query.answer("❌ لا توجد مراحل.", show_alert=True)
            return
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
        if not subjects:
            await query.answer("❌ لا توجد مواد في هذه المرحلة.", show_alert=True)
            return
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
        keyboard = [[InlineKeyboardButton(f"🗑 {v['name']}", callback_data=f"do_del_sb:{st_id}:{k}")] for k, v in subjects.items()] if subjects else []
        keyboard.append([InlineKeyboardButton("⬅️ رجوع", callback_data="del_sb_st_list")])
        try:
            await query.edit_message_text("⚠️ <b>اختر المادة المراد حذفها نهائياً:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        except BadRequest:
            pass
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
        await query.message.reply_text("✍️ <b>أرسل الآن اسم المرحلة الجديدة:</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="cancel_state")]]), parse_mode="HTML")
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
        await query.message.reply_text("✍️ <b>أرسل الآن اسم المادة الجديدة:</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="cancel_state")]]), parse_mode="HTML")
        return

    if data == "broadcast_all":
        admin_states[user_id] = {"mode": "broadcasting_all"}
        await query.message.reply_text("✍️ <b>أرسل رسالة الإذاعة (ستصل لجميع المشتركين):</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="cancel_state")]]), parse_mode="HTML")
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
        await query.message.reply_text(f"✍️ <b>أرسل رسالة أو ملف الإذاعة (نص، صورة، ملف، شرح) لطلاب مرحلة {st_name}:</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="cancel_state")]]), parse_mode="HTML")
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
        await query.message.reply_text("✍️ <b>أرسل الآيدي (ID) الخاص بالمستخدم المراد حظره:</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="cancel_state")]]), parse_mode="HTML")
        return

    if data == "unban_usr":
        admin_states[user_id] = {"mode": "unban_user_id"}
        await query.message.reply_text("✍️ <b>أرسل الآيدي (ID) الخاص بالمستخدم المراد فك حظره:</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="cancel_state")]]), parse_mode="HTML")
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
        await query.message.reply_text("✍️ <b>أرسل رابط جروب التليجرام الخاص بهذه المادة:</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="cancel_state")]]), parse_mode="HTML")
        return

    if data == "add_subadmin":
        admin_states[user_id] = {"mode": "add_subadmin_id"}
        await query.message.reply_text("✍️ <b>أرسل الآيدي (ID) الخاص بالمشرف الجديد:</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="cancel_state")]]), parse_mode="HTML")
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
        keyboard.append([InlineKeyboardButton("🗑 إغلاق", callback_data="close")])
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
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="cancel_state")]]), parse_mode="HTML")
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

        if mode == "setting_schedule" and is_full_admin(user_id):
            sched_item = {}
            if update.message.document:
                sched_item = {"type": "pdf", "value": update.message.document.file_id, "caption": update.message.caption or "📅 جدول الامتحانات والدروس"}
            elif update.message.photo:
                sched_item = {"type": "photo", "value": update.message.photo[-1].file_id, "caption": update.message.caption or "📅 جدول الامتحانات والدروس"}
            elif update.message.text:
                sched_item = {"type": "text", "value": update.message.text.strip()}
            else:
                await update.message.reply_text("⚠️ يرجى إرسال نص، صورة، أو ملف PDF فقط.")
                return

            db["schedule_info"] = sched_item
            save_data(db)
            del admin_states[user_id]
            await update.message.reply_text("✅ <b>تم تحديث جدول الامتحانات والدروس بنجاح!</b>", parse_mode="HTML")
            return

        if mode == "add_faq_title" and is_full_admin(user_id):
            title = update.message.text.strip() if update.message.text else ""
            if not title:
                await update.message.reply_text("❌ يرجى إدخال عنوان نصي صريح للسؤال.")
                return
            
            admin_states[user_id] = {"mode": "add_faq_content", "faq_title": title}
            cancel_kb = [[InlineKeyboardButton("❌ إلغاء", callback_data="cancel_state")]]
            await update.message.reply_text(f"✍️ <b>الآن أرسل إجابة سؤال ({html.escape(title)}):</b>\n(يمكنك إرسال نص، صورة، أو ملف PDF):", reply_markup=InlineKeyboardMarkup(cancel_kb), parse_mode="HTML")
            return

        if mode == "add_faq_content" and is_full_admin(user_id):
            faq_title = state.get("faq_title")
            faq_item = {}
            if update.message.document:
                faq_item = {"type": "pdf", "value": update.message.document.file_id, "caption": update.message.caption or ""}
            elif update.message.photo:
                faq_item = {"type": "photo", "value": update.message.photo[-1].file_id, "caption": update.message.caption or ""}
            elif update.message.text:
                faq_item = {"type": "text", "value": update.message.text.strip()}
            else:
                await update.message.reply_text("⚠️ يرجى إرسال نص، صورة، أو ملف PDF كإجابة للسؤال.")
                return

            db["faq_info"][faq_title] = faq_item
            save_data(db)
            del admin_states[user_id]
            safe_title = html.escape(faq_title)
            await update.message.reply_text(f"✅ <b>تم حفظ السؤال الشائع ({safe_title}) وإجابته بنجاح!</b>", parse_mode="HTML")
            return

        if mode == "add_st" and is_full_admin(user_id):
            name = update.message.text.strip() if update.message.text else "مرحلة جديدة"
            st_id = f"s{int(time.time())}"
            db["stages"][st_id] = {"name": name, "subjects": {}}
            save_data(db)
            del admin_states[user_id]
            safe_st_name = html.escape(name)
            await update.message.reply_text(f"✅ تمت إضافة المرحلة: <b>{safe_st_name}</b>", parse_mode="HTML")
            return

        if mode == "add_sb" and is_full_admin(user_id):
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

        if mode == "setting_grp_link" and is_full_admin(user_id):
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

        if mode == "ban_user_id" and is_full_admin(user_id):
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

        if mode == "unban_user_id" and is_full_admin(user_id):
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

        if mode == "broadcasting_all" and is_full_admin(user_id):
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

    while True:
        try:
            app.run_polling(
                drop_pending_updates=True, 
                allowed_updates=Update.ALL_TYPES,
                close_loop=False
            )
        except Exception as e:
            print(f"⚠️ واجهنا انقطاع مؤقت في الشبكة (Bad Gateway): {e}")
            import time
            time.sleep(10)

if __name__ == "__main__":
    main()

