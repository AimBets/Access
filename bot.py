import json
import logging
from datetime import datetime, timedelta
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatInviteLink
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, CallbackQueryHandler
)
import os
import asyncio

TOKEN = "7219790201:AAFDj6bYSMygD2CIrgcff9bQ4pVeI2dUBds"
CANAL_ID = -1002540984437
ADMIN_ID = 1454008370
PIX_CHAVE = "aimbetspro@gmail.com"

DATA_FILE = "vip_data.json"
logging.basicConfig(level=logging.INFO)

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or update.effective_user.first_name

    data = load_data()
    if user_id in data:
        await update.message.reply_text("👋 Você já é um membro VIP ativo ou em processo.")
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Quero entrar no VIP 🔐", callback_data=f"quero_vip_{user_id}")]
    ])
    await update.message.reply_text(
        "Olá! Deseja entrar no nosso grupo VIP?\n\n💰 Acesso por 30 dias: *R$500*",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

async def botao_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data()
    user_id = str(query.from_user.id)

    if query.data.startswith("quero_vip_"):
        data[user_id] = {
            "username": query.from_user.username,
            "status": "aguardando_comprovante",
            "valid_until": None,
            "notified": False
        }
        save_data(data)
        await query.message.reply_text(
            f"🔐 O valor do VIP é *R$500*\n\nChave PIX: `{PIX_CHAVE}`\nTipo: e-mail\n\n📩 Envie o comprovante aqui mesmo após o pagamento.",
            parse_mode="Markdown"
        )

    elif query.data.startswith("renovar_vip_"):
        await query.message.reply_text(
            f"🔁 Para renovar, envie o pagamento de *R$500*\n\nChave PIX: `{PIX_CHAVE}`\nTipo: e-mail\n\n📩 Depois envie o novo comprovante aqui.",
            parse_mode="Markdown"
        )
        data[user_id]["status"] = "renovando"
        save_data(data)

    elif query.data.startswith("confirmar_"):
        target_id = query.data.split("_")[1]
        data = load_data()
        username = data[target_id]["username"]
        now = datetime.now()

        if data[target_id]["valid_until"]:
            atual = datetime.strptime(data[target_id]["valid_until"], "%Y-%m-%d")
            nova_data = atual + timedelta(days=30)
        else:
            nova_data = now + timedelta(days=30)

        link: ChatInviteLink = await context.bot.create_chat_invite_link(
            chat_id=CANAL_ID,
            expire_date=nova_data,
            member_limit=1,
            name=f"VIP_{username}"
        )

        await context.bot.send_message(
            chat_id=int(target_id),
            text=f"✅ Pagamento confirmado!\n\n🎫 Aqui está seu acesso VIP de 30 dias:\n{link.invite_link}"
        )

        data[target_id]["valid_until"] = nova_data.strftime("%Y-%m-%d")
        data[target_id]["status"] = "ativo"
        data[target_id]["notified"] = False
        save_data(data)

        await query.message.edit_text(f"✅ @{username} foi ativado até {nova_data.strftime('%d/%m/%Y')}.")

    elif query.data.startswith("recusar_"):
        target_id = query.data.split("_")[1]
        await context.bot.send_message(chat_id=int(target_id), text="❌ Pagamento recusado. Envie novamente ou entre em contato com o suporte.")
        await query.message.edit_text("❌ Pagamento recusado.")
        data = load_data()
        if target_id in data:
            del data[target_id]
            save_data(data)

async def receber_comprovante(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or update.effective_user.first_name
    data = load_data()

    if user_id not in data or data[user_id]["status"] not in ["aguardando_comprovante", "renovando"]:
        return

    msg = await update.message.forward(chat_id=ADMIN_ID)
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirmar", callback_data=f"confirmar_{user_id}"),
            InlineKeyboardButton("❌ Recusar", callback_data=f"recusar_{user_id}")
        ]
    ])

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"💰 Novo comprovante de @{username}\nConfirma pagamento?",
        reply_to_message_id=msg.message_id,
        reply_markup=keyboard
    )

async def checar_vencimentos(app):
    while True:
        data = load_data()
        now = datetime.now()

        for user_id, info in list(data.items()):
            if not info.get("valid_until"):
                continue

            venc = datetime.strptime(info["valid_until"], "%Y-%m-%d")
            dias = (venc - now).days

            if dias == 3 and not info.get("notified"):
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔁 Renovar", callback_data=f"renovar_vip_{user_id}")]
                ])
                try:
                    await app.bot.send_message(
                        chat_id=int(user_id),
                        text="⚠️ Seu VIP expira em 3 dias. Deseja renovar?",
                        reply_markup=keyboard
                    )
                    data[user_id]["notified"] = True
                    save_data(data)
                except:
                    continue

            if dias < 0:
                del data[user_id]
                save_data(data)

        await asyncio.sleep(86400)

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, receber_comprovante))
    app.add_handler(CallbackQueryHandler(botao_callback))

    app.job_queue.run_once(lambda ctx: asyncio.create_task(checar_vencimentos(app)), when=1)

    print("Bot rodando...")
    app.run_polling()
