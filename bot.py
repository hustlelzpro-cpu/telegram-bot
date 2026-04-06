import os
import sqlite3
import logging
from datetime import datetime
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# =========================
# LOGGING
# =========================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# =========================
# ENV
# =========================
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
CALENDLY_LINK = os.getenv("CALENDLY_LINK", "https://calendly.com/hustlelzpro")

if not TOKEN:
    raise ValueError("BOT_TOKEN missing")

# =========================
# DB
# =========================
conn = sqlite3.connect("leads.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    capital TEXT,
    objectif TEXT,
    experience TEXT,
    attempts TEXT,
    urgency TEXT,
    score INTEGER,
    created_at TEXT
)
""")
conn.commit()

# =========================
# STATE
# =========================
user_step = {}
user_score = {}
user_answers = {}

# =========================
# QUESTIONS (PRO FUNNEL)
# =========================
QUESTIONS = [
    ("Quel capital peux-tu réellement mobiliser immédiatement ?", [
        "< 300",
        "300 - 500",
        "500 - 1000",
        "1000+"
    ]),

    ("Quelle situation décrit le mieux ton objectif ?", [
        "dépendance financière actuelle",
        "complément de revenu sérieux",
        "liberté financière long terme",
        "curiosité / test"
    ]),

    ("Quel est ton niveau d'expérience réel ?", [
        "aucune expérience",
        "quelques tests",
        "déjà actif / investi régulièrement"
    ]),

    ("As-tu déjà essayé de générer de l'argent en ligne ?", [
        "jamais",
        "oui mais échec",
        "oui avec petits résultats",
        "oui résultats stables"
    ]),

    ("Quelle est ta situation d'urgence actuelle ?", [
        "besoin de résultats rapides",
        "objectif dans 1-3 mois",
        "objectif long terme",
        "aucune urgence"
    ])
]

# =========================
# KEYBOARD
# =========================
def keyboard(options):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(opt, callback_data=opt)]
        for opt in options
    ])

# =========================
# SCORING (PRO LOGIC)
# =========================
def score(step, choice):
    s = 0

    if step == 0:
        if choice == "1000+":
            s += 4
        elif choice == "500 - 1000":
            s += 3
        elif choice == "300 - 500":
            s += 1

    elif step == 1:
        if choice == "dépendance financière actuelle":
            s += 4
        elif choice == "complément de revenu sérieux":
            s += 3
        elif choice == "liberté financière long terme":
            s += 2

    elif step == 2:
        if choice == "déjà actif / investi régulièrement":
            s += 3
        elif choice == "quelques tests":
            s += 1

    elif step == 3:
        if choice == "oui résultats stables":
            s += 4
        elif choice == "oui avec petits résultats":
            s += 2
        elif choice == "oui mais échec":
            s += 1

    elif step == 4:
        if choice == "besoin de résultats rapides":
            s += 5
        elif choice == "objectif dans 1-3 mois":
            s += 3
        elif choice == "aucune urgence":
            s -= 2

    return s

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    user_step[user_id] = 0
    user_score[user_id] = 0
    user_answers[user_id] = []

    q, options = QUESTIONS[0]

    await update.message.reply_text(q, reply_markup=keyboard(options))
    logger.info(f"START user {user_id}")

# =========================
# HANDLE
# =========================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id

        if user_id not in user_step:
            user_step[user_id] = 0
            user_score[user_id] = 0
            user_answers[user_id] = []

        step = user_step[user_id]
        choice = query.data

        user_answers[user_id].append(choice)
        user_score[user_id] += score(step, choice)

        step += 1
        user_step[user_id] = step

        logger.info(f"USER {user_id} STEP {step} CHOICE {choice}")

        # FIN
        if step >= len(QUESTIONS):
            final_score = user_score[user_id]

            cursor.execute("""
            INSERT INTO leads (user_id, capital, objectif, experience, attempts, urgency, score, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                user_answers[user_id][0],
                user_answers[user_id][1],
                user_answers[user_id][2],
                user_answers[user_id][3],
                user_answers[user_id][4],
                final_score,
                datetime.now().isoformat()
            ))
            conn.commit()

            if final_score >= 12:
                await query.message.reply_text(
                    "Profil qualifié. Réserve ici :\n" + CALENDLY_LINK
                )
            else:
                await query.message.reply_text(
                    "Profil non qualifié pour le moment."
                )

            logger.info(f"LEAD SAVED user {user_id} score {final_score}")
            return

        q, options = QUESTIONS[step]
        await query.message.reply_text(q, reply_markup=keyboard(options))

    except Exception as e:
        logger.error(f"HANDLE ERROR: {e}", exc_info=True)

# =========================
# ERROR HANDLER
# =========================
async def error_handler(update, context):
    logger.error("UNHANDLED ERROR", exc_info=context.error)

# =========================
# MAIN
# =========================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("go", start))
    app.add_handler(CallbackQueryHandler(handle))

    app.add_error_handler(error_handler)

    logger.info("BOT STARTED")
    app.run_polling()

if __name__ == "__main__":
    main()