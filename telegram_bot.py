# ==========================================
# Telegram 봇 - 스케줄링된 뉴스 알림
# ==========================================

import os
import time
import logging
import json
import datetime
import sys

# 경로 설정 (app.py와 같은 디렉토리)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import schedule
except ImportError:
    print("Error: 'schedule' package not found. Please install it: pip install schedule")
    sys.exit(1)

try:
    import pytz
except ImportError:
    print("Error: 'pytz' package not found. Please install it: pip install pytz")
    sys.exit(1)

import requests

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = lambda: None
    print("Warning: 'python-dotenv' not found, using environment variables directly")

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TelegramBot")

# 환경 변수 로드
load_dotenv()

# 텔레그램 설정
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8550186803:AAGEDWmforGFn_QQyWUY8E6b6jDHN8LJZXM")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "5272469108")

# AI API 설정
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
XAI_API_KEY = os.getenv("XAI_API_KEY", "")

# ==========================================
# 앱 모듈 가져오기
# ==========================================
try:
    from app import Config, DatabaseManager, AIAgent, feedparser, clean_json_response
except ImportError as e:
    logger.error(f"Failed to import app modules: {e}")
    exit(1)


# ==========================================
# 유틸리티 함수
# ==========================================
def get_kst_now():
    """한국 시간(KST) datetime 객체 반환"""
    kst = pytz.timezone('Asia/Seoul')
    return datetime.datetime.now(kst)


def get_kst_today():
    """한국 시간(KST) 기준 오늘 날짜 문자열 반환 (YYYY-MM-DD)"""
    return get_kst_now().strftime('%Y-%m-%d')


# ==========================================
# 뉴스 수집 함수
# ==========================================
def fetch_latest_news():
    """최신 뉴스 수집 (app.py 로직 재사용)"""
    try:
        if not GOOGLE_API_KEY:
            logger.error("GOOGLE_API_KEY not found")
            return 0

        db = DatabaseManager(Config.DB_FILE)
        ai = AIAgent(GOOGLE_API_KEY, GROQ_API_KEY, XAI_API_KEY)

        total_cnt = 0
        categories = list(Config.RSS_MAP.items())

        for i, (cat_name, rss_url) in enumerate(categories):
            logger.info(f"Fetching [{cat_name}] news...")
            try:
                feed = feedparser.parse(rss_url)
                logger.info(f"[{cat_name}] RSS entries: {len(feed.entries)}")

                candidates = []
                for entry in feed.entries:
                    if not db.check_url_exists(entry.link):
                        candidates.append(entry)

                logger.info(f"[{cat_name}] New candidates: {len(candidates)}")

                if candidates:
                    news_data = ai.curate_news(candidates[:5], cat_name)
                    logger.info(f"[{cat_name}] AI curated: {len(news_data) if news_data else 0}")

                    if news_data:
                        cnt = db.save_news_bulk(news_data)
                        total_cnt += cnt
                        logger.info(f"[{cat_name}] Saved: {cnt}")

                if i < len(categories) - 1:
                    time.sleep(2)
            except Exception as e:
                logger.error(f"Error processing {cat_name}: {e}")

        logger.info(f"Total news fetched: {total_cnt}")
        return total_cnt

    except Exception as e:
        logger.error(f"Failed to fetch news: {e}")
        return 0


# ==========================================
# 텔레그램 메시지 전송 함수
# ==========================================
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


# ==========================================
# 카드뉴스 생성 함수
# ==========================================
def create_card_news(news_items, max_count=5):
    """뉴스 아이템으로 카드뉴스 형식 텍스트 생성"""
    kst_time = get_kst_now().strftime("%Y년 %m월 %d일 %H:%M (KST)")

    message = f"""<b>📰 AI 경제 브리핑</b>
 <i>{kst_time}</i>

 """

    for idx, news in enumerate(news_items[:max_count], 1):
        news_id, title, summary, url, date, category, _ = news

        # 요약에서 줄 바꿈 정리 (최대 3줄)
        summary_lines = summary.split('\n')
        clean_summary = '\n'.join(summary_lines[:3]) if len(summary_lines) > 3 else summary

        message += f"""<b>{idx}. {title}</b>
 📂 {category}

 {clean_summary}

 <a href="{url}">📎 원문 보기</a>

 """

    return message


def create_card_news_with_buttons(news_items, max_count=5):
    """버튼 포함 카드뉴스 생성"""
    if not news_items:
        return "<b>📰 오늘의 뉴스</b>\n\n새로운 뉴스가 없습니다.", None

    message = create_card_news(news_items, max_count)

    # 버튼 생성 (각 뉴스의 원문 링크)
    buttons = []
    for idx, news in enumerate(news_items[:max_count], 1):
        news_id, title, summary, url, date, category, _ = news
        buttons.append([{"text": f"🔗 {idx}번 기사", "url": url}])

    reply_markup = {"inline_keyboard": buttons}

    return message, reply_markup


# ==========================================
# 스케줄링된 뉴스 알림 함수
# ==========================================
def send_scheduled_news():
    """스케줄링된 뉴스 알림 전송 (DB에서 미전송 뉴스만)"""
    try:
        logger.info(f"Starting scheduled news notification at {get_kst_now()}")

        # 1. DB에서 아직 텔레그램으로 보내지 않은 뉴스만 가져오기
        db = DatabaseManager(Config.DB_FILE)
        today = get_kst_today()
        news_list = db.get_unsent_news(date_filter=today)

        logger.info(f"Unsent news count for today: {len(news_list)}")

        if not news_list:
            logger.info("No unsent news found. Skipping.")
            return

        # 2. 카드뉴스 형식으로 전송
        message, reply_markup = create_card_news_with_buttons(news_list, max_count=5)

        # 3. 텔레그램으로 전송
        success = send_telegram_message(message, reply_markup)

        if success:
            # 4. 보낸 뉴스의 telegram_sent = 1로 업데이트
            news_ids = [news[0] for news in news_list]
            db.mark_news_as_sent(news_ids)
            logger.info(f"News notification sent successfully. {len(news_list)} articles marked as sent.")
        else:
            logger.error("Failed to send news notification")

    except Exception as e:
        logger.error(f"Error in send_scheduled_news: {e}")


# ==========================================
# 단어봇 관련 함수
# ==========================================
def create_vocab_card(words):
    """단어 카드뉴스 형식 생성"""
    kst_time = get_kst_now().strftime("%Y년 %m월 %d일 %H:%M (KST)")

    message = f"""<b>📚 AI 단어 학습</b>
<i>{kst_time}</i>

오늘 학습할 단어입니다! ✨

"""

    for idx, word in enumerate(words, 1):
        word_id, word_text, meaning, sentence, example, grammar = word

        message += f"""<b>{idx}. {word_text}</b>
📖 뜻: {meaning}

📜 예문: {sentence}

💡 {grammar}

"""

    return message


def create_vocab_card_with_refresh_button(words):
    """새로고침 버튼 포함 단어 카드 생성"""
    if not words:
        return "<b>📚 AI 단어 학습</b>\n\n학습할 단어가 없습니다.", None

    message = create_vocab_card(words)

    # "다시 받기" 버튼 (callback data는 웹훅에서 처리해야 함)
    # 간단하게는 URL이나 별도 명령으로 처리
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "🔄 다시 받기", "callback_data": "vocab_refresh"}
            ]
        ]
    }

    return message, reply_markup


def send_vocab_quiz():
    """랜덤 단어 퀴즈 전송 (3시간마다)"""
    try:
        logger.info(f"Starting vocab quiz at {get_kst_now()}")

        db = DatabaseManager(Config.DB_FILE)

        # 랜덤 미학습 단어 5개 가져오기
        words = db.get_random_unlearned_words(count=5)

        logger.info(f"Random unlearned words: {len(words)}")

        if not words:
            logger.warning("No unlearned words found")
            message = f"""<b>📚 AI 단어 학습</b>
<i>{get_kst_now().strftime("%Y년 %m월 %d일 %H:%M (KST)")}</i>

🎉 모든 단어를 학습 완료했습니다!

새로운 단어를 추가하고 다시 도전하세요! 💪
"""
            send_telegram_message(message)
            return

        # 단어 카드 형식으로 전송
        message, reply_markup = create_vocab_card_with_refresh_button(words)

        # 텔레그램으로 전송
        success = send_telegram_message(message, reply_markup)

        if success:
            logger.info(f"Vocab quiz sent successfully. {len(words)} words.")
        else:
            logger.error("Failed to send vocab quiz")

    except Exception as e:
        logger.error(f"Error in send_vocab_quiz: {e}")


def send_vocab_quiz_manual():
    """수동으로 단어 퀴즈 전송 (다시 받기 버튼용)"""
    return send_vocab_quiz()


# ==========================================
# 메인 함수
# ==========================================
def main():
    """메인 함수 - 스케줄러 실행 (KST 기준)"""
    logger.info("=" * 50)
    logger.info("Telegram News & Vocab Bot Started")
    logger.info("=" * 50)

    # 스케줄 설정 (한국 시간 기준: 뉴스 6시, 12시, 18시)
    news_schedule_times = ["06:00", "12:00", "18:00"]
    vocab_interval_hours = 3

    # 마지막 실행 시간 추적 (KST)
    last_news_execution = {}  # {time_str: last_executed_datetime}
    last_vocab_execution = None

    logger.info("Scheduled jobs (KST):")
    for time_str in news_schedule_times:
        logger.info(f"  - {time_str} KST: News notification")
    logger.info(f"  - Every {vocab_interval_hours} hours: Vocab quiz")

    # 바로 한 번 실행 테스트 (필요시 주석 처리)
    # logger.info("Running immediate test...")
    # send_scheduled_news()
    # send_vocab_quiz()

    # 무한 루프 - 스케줄러 실행
    while True:
        try:
            # 현재 KST 시간 가져오기
            current_kst = get_kst_now()
            current_time_str = current_kst.strftime("%H:%M")
            current_hour = current_kst.hour

            logger.debug(f"Current KST time: {current_time_str}")

            # 뉴스 스케줄 체크
            for schedule_time in news_schedule_times:
                # 이 시간대에 대해 아직 오늘 실행하지 않았는지 확인
                if schedule_time not in last_news_execution:
                    # 첫 실행이므로 무시하고 기록
                    pass
                else:
                    # 마지막 실행이 오늘인지 확인
                    last_exec = last_news_execution[schedule_time]
                    if last_exec.date() != current_kst.date():
                        # 새로운 날이므로 시간 비교
                        if current_time_str == schedule_time:
                            logger.info(f"Executing scheduled news notification at {schedule_time} KST")
                            send_scheduled_news()
                            last_news_execution[schedule_time] = current_kst
                    else:
                        # 같은 날이면 이미 실행했는지 확인
                        continue

            # 마지막 실행 기록이 없으면 초기화
            for schedule_time in news_schedule_times:
                if schedule_time not in last_news_execution:
                    last_news_execution[schedule_time] = current_kst

            # 현재 시간이 정확히 스케줄 시간이면 실행
            if current_time_str in news_schedule_times:
                if last_news_execution.get(current_time_str):
                    last_exec = last_news_execution[current_time_str]
                    if last_exec.date() != current_kst.date() or last_exec.hour != current_kst.hour:
                        logger.info(f"Executing scheduled news notification at {current_time_str} KST")
                        send_scheduled_news()
                        last_news_execution[current_time_str] = current_kst

            # 단어 퀴즈 - 3시간마다 체크
            if last_vocab_execution is None:
                last_vocab_execution = current_kst
            else:
                hours_since_last = (current_kst - last_vocab_execution).total_seconds() / 3600
                if hours_since_last >= vocab_interval_hours:
                    logger.info(f"Executing vocab quiz (every {vocab_interval_hours} hours)")
                    send_vocab_quiz()
                    last_vocab_execution = current_kst

            time.sleep(60)  # 1분마다 체크

        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(60)

if __name__ == "__main__":
    main()
