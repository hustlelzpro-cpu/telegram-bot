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
# QUESTIONS (ULTRA CLAIRES)
# =========================
QUESTIONS = [
    ("Combien peux-tu investir immédiatement ?", [
        "Moins de 300€",
        "300 à 500€",
        "500 à 1000€",
        "Plus de 1000€"
    ]),

    ("Quel est ton objectif principal ?", [
        "Gagner un complément de revenu",
        "Remplacer mon salaire",
        "Faire fructifier mon argent",
        "Je teste juste par curiosité"
    ]),

    ("As-tu de l’expérience en trading / investissement en ligne ?", [
        "Aucune expérience",
        "J’ai déjà essayé sans résultats",
        "J’ai obtenu quelques résultats",
        "Je suis déjà actif régulièrement"
    ]),

    ("As-tu déjà essayé de gagner de l’argent en ligne ?", [
        "Jamais",
        "Oui mais sans succès",
        "Oui avec petits résultats",
        "Oui avec résultats stables"
    ]),

    ("Quand veux-tu réellement commencer ?", [
        "Maintenant",
        "Dans les 30 jours",
        "Plus tard",
        "Je ne sais pas encore"
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
# SCORING
# =========================
def score(step, choice):
    s = 0

    if step == 0:
        if choice == "Plus de 1000€":
            s += 4
        elif choice == "500 à 1000€":
            s += 3
        elif choice == "300 à 500€":
            s += 1

    elif step == 1:
        if choice == "Remplacer mon salaire":
            s += 4
        elif choice == "Gagner un complément de revenu":
            s += 3
        elif choice == "Faire fructifier mon argent":
            s += 2

    elif step == 2:
        if choice == "Je suis déjà actif régulièrement":
            s += 3
        elif choice == "J’ai obtenu quelques résultats":
            s += 2
        elif choice == "J’ai déjà essayé sans résultats":
            s += 1

    elif step == 3:
        if choice == "Oui avec résultats stables":
            s += 4
        elif choice == "Oui avec petits résultats":
            s += 2
        elif choice == "Oui mais sans succès":
            s += 1

    elif step == 4:
        if choice == "Maintenant":
            s += 5
        elif choice == "Dans les 30 jours":
            s += 3
        elif choice == "Plus tard":
            s -= 1

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