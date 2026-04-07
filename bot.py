import os
import sqlite3
from datetime import datetime
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ENV
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

CAL_LINK = "https://cal.com/hustlelzpro/appel-selection"

# DB
conn = sqlite3.connect("leads.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    capital TEXT,
    objectif TEXT,
    experience TEXT,
    timing TEXT,
    score INTEGER,
    created_at TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    event TEXT,
    data TEXT,
    created_at TEXT
)
""")

conn.commit()

# STATE
user_step = {}
user_score = {}
user_answers = {}

# TRACKING
def track(user_id, event, data=None):
    cursor.execute("""
        INSERT INTO events (user_id, event, data, created_at)
        VALUES (?, ?, ?, ?)
    """, (
        user_id,
        event,
        str(data),
        datetime.now().isoformat()
    ))
    conn.commit()

# QUESTIONS
QUESTIONS = [
    ("Quel capital peux-tu réellement mobiliser pour investir ?", [
        "< 300",
        "300 - 500",
        "500 - 1000",
        "1000+"
    ]),
    ("Quel est ton objectif principal aujourd’hui ?", [
        "Complément de revenu",
        "Remplacer mon revenu",
        "Faire fructifier mon capital",
        "Curiosité / apprentissage"
    ]),
    ("As-tu déjà investi ou tradé de l’argent réel ?", [
        "Jamais",
        "Oui, test (petites sommes)",
        "Oui, régulièrement"
    ]),
    ("Dans quel délai veux-tu vraiment passer à l’action ?", [
        "Immédiatement",
        "Dans les 30 jours",
        "Plus tard",
        "Je regarde juste"
    ])
]

# KEYBOARD
def keyboard(options):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(opt, callback_data=opt)]
        for opt in options
    ])

# SCORE
def score(step, choice):
    s = 0

    if step == 0:
        if choice == "1000+": s += 4
        elif choice == "500 - 1000": s += 3
        elif choice == "300 - 500": s += 1

    elif step == 1:
        if choice == "Remplacer mon revenu": s += 3
        elif choice == "Complément de revenu": s += 2
        elif choice == "Faire fructifier mon capital": s += 1

    elif step == 2:
        if choice == "Oui, régulièrement": s += 2
        elif choice == "Oui, test (petites sommes)": s += 1

    elif step == 3:
        if choice == "Immédiatement": s += 4
        elif choice == "Dans les 30 jours": s += 2
        elif choice == "Plus tard": s -= 1
        elif choice == "Je regarde juste": s -= 3

    return s

# START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    user_step[user_id] = 0
    user_score[user_id] = 0
    user_answers[user_id] = []

    track(user_id, "start_quiz")

    q, options = QUESTIONS[0]
    await update.message.reply_text(q, reply_markup=keyboard(options))

# HANDLE
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    step = user_step[user_id]
    choice = query.data

    user_answers[user_id].append(choice)
    user_score[user_id] += score(step, choice)

    track(user_id, "step_answer", {
        "step": step,
        "choice": choice
    })

    step += 1
    user_step[user_id] = step

    if step >= len(QUESTIONS):
        final_score = user_score[user_id]

        track(user_id, "quiz_completed", {"score": final_score})

        segment = "cold"
        if final_score >= 8:
            segment = "hot"
        elif final_score >= 5:
            segment = "warm"

        track(user_id, "lead_segment", segment)

        cursor.execute("""
        INSERT INTO leads (user_id, capital, objectif, experience, timing, score, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            user_answers[user_id][0],
            user_answers[user_id][1],
            user_answers[user_id][2],
            user_answers[user_id][3],
            final_score,
            datetime.now().isoformat()
        ))
        conn.commit()

        track(user_id, "cal_link_sent")

        if segment == "hot":
            await query.message.reply_text(
                "Profil validé. Réserve ton appel ici :\n" + CAL_LINK
            )
        elif segment == "warm":
            await query.message.reply_text(
                "Ton profil est intéressant. Voici un accès prioritaire :\n" + CAL_LINK
            )
        else:
            await query.message.reply_text(
                "Tu n’es pas encore au bon moment. Continue à te former et reviens plus tard."
            )

        return

    q, options = QUESTIONS[step]
    await query.message.reply_text(q, reply_markup=keyboard(options))

# MAIN
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("go", start))
    app.add_handler(CallbackQueryHandler(handle))

    app.run_polling()

if __name__ == "__main__":
    main()