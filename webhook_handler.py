#!/usr/bin/env python3
# ==========================================
# 텔레그램 Webhook 핸들러 - 단어 "다시 받기" 버튼 처리
# ==========================================

import os
import sys
import json
import logging

# 경로 설정
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram_bot import send_vocab_quiz, get_kst_now
from app import DatabaseManager, Config

try:
    from flask import Flask, request
except ImportError:
    print("Error: 'flask' package not found. Please install it: pip install flask")
    sys.exit(1)

import requests

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("WebhookHandler")

# 텔레그램 설정
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8550186803:AAGEDWmforGFn_QQyWUY8E6b6jDHN8LJZXM")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "5272469108")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
PORT = int(os.getenv("PORT", "5000"))

app = Flask(__name__)


def send_telegram_message(text, reply_markup=None):
    """텔레그램 메시지 전송"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }

        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup)

        response = requests.post(url, data=data, timeout=30)

        if response.status_code == 200:
            logger.info("Telegram message sent successfully")
            return True
        else:
            logger.error(f"Telegram API error: {response.text}")
            return False

    except Exception as e:
        logger.error(f"Failed to send telegram message: {e}")
        return False


def answer_callback_query(callback_query_id):
    """콜백 쿼리 응답 (텔레그램 API)"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery"
        data = {
            "callback_query_id": callback_query_id,
            "text": "단어를 준비 중입니다...",
            "show_alert": True
        }
        response = requests.post(url, data=data, timeout=30)

        if response.status_code == 200:
            logger.info(f"Callback query answered: {callback_query_id}")
            return True
        else:
            logger.error(f"Failed to answer callback query: {response.text}")
            return False

    except Exception as e:
        logger.error(f"Error answering callback query: {e}")
        return False


@app.route(f'/webhook/{TELEGRAM_TOKEN}', methods=['POST'])
def webhook():
    """텔레그램 Webhook 엔드포인트"""
    try:
        update = request.json
        logger.info(f"Received update: {update}")

        # 콜백 쿼리 처리 (다시 받기 버튼)
        if 'callback_query' in update:
            callback_query = update['callback_query']
            callback_data = callback_query.get('data', '')

            logger.info(f"Callback query received: {callback_data}")

            if callback_data == 'vocab_refresh':
                # 콜백 응답
                answer_callback_query(callback_query['id'])

                # DB에서 랜덤 단어 가져오기
                db = DatabaseManager(Config.DB_FILE)
                words = db.get_random_unlearned_words(count=5)

                if not words:
                    message = f"""<b>📚 AI 단어 학습</b>
<i>{get_kst_now().strftime("%Y년 %m월 %d일 %H:%M (KST)")}</i>

🎉 모든 단어를 학습 완료했습니다!

새로운 단어를 추가하고 다시 도전하세요! ✨
"""
                    send_telegram_message(message)
                    return

                # 단어 카드 형식 생성
                from telegram_bot import create_vocab_card
                message = create_vocab_card(words)

                # 버튼 생성
                reply_markup = {
                    "inline_keyboard": [
                        [
                            {"text": "🔄 다시 받기", "callback_data": "vocab_refresh"}
                        ]
                    ]
                }

                # 메시지 전송
                send_telegram_message(message, reply_markup)

        return json.dumps({"status": "ok"}), 200

    except Exception as e:
        logger.error(f"Error in webhook: {e}")
        import traceback
        traceback.print_exc()
        return json.dumps({"status": "error", "message": str(e)}), 500


@app.route('/', methods=['GET'])
def health_check():
    """헬스 체크"""
    return json.dumps({"status": "ok", "service": "telegram-webhook"}), 200


def set_webhook():
    """Webhook 설정"""
    if not WEBHOOK_URL:
        logger.error("WEBHOOK_URL not set in environment variables")
        return False

    webhook_url = f"{WEBHOOK_URL}/webhook/{TELEGRAM_TOKEN}"

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
    data = {
        "url": webhook_url
    }

    response = requests.post(url, data=data, timeout=30)

    if response.status_code == 200:
        result = response.json()
        if result.get('ok'):
            logger.info(f"Webhook set successfully: {webhook_url}")
            return True
        else:
            logger.error(f"Failed to set webhook: {result}")
            return False
    else:
        logger.error(f"Failed to set webhook: {response.text}")
        return False


def delete_webhook():
    """Webhook 삭제"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook"

    response = requests.get(url, timeout=30)

    if response.status_code == 200:
        logger.info("Webhook deleted")
        return True
    else:
        logger.error(f"Failed to delete webhook: {response.text}")
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Telegram Webhook Handler')
    parser.add_argument('--set-webhook', action='store_true', help='Set webhook')
    parser.add_argument('--delete-webhook', action='store_true', help='Delete webhook')
    args = parser.parse_args()

    if args.set_webhook:
        set_webhook()
    elif args.delete_webhook:
        delete_webhook()
    else:
        # 웹 서버 실행
        logger.info("=" * 50)
        logger.info("Telegram Webhook Handler Started")
        logger.info(f"Port: {PORT}")
        logger.info("=" * 50)

        app.run(host='0.0.0.0', port=PORT, debug=False)
