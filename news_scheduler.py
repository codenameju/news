#!/usr/bin/env python3
# ==========================================
# 뉴스 스케줄러 - 1시간마다 뉴스 수집
# ==========================================

import os
import sys
import time
import logging

# 경로 설정 (app.py와 같은 디렉토리)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("NewsScheduler")


def fetch_news():
    """뉴스 수집 함수"""
    try:
        from app import DatabaseManager, AIAgent, Config, feedparser, clean_json_response
        from telegram_bot import get_kst_now

        logger.info(f"Starting news fetch at {get_kst_now()}")

        # API 키 확인
        GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
        GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
        XAI_API_KEY = os.getenv("XAI_API_KEY", "")

        if not GOOGLE_API_KEY:
            logger.error("GOOGLE_API_KEY not found in environment variables")
            return 0

        # 뉴스 수집
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

        # 마지막 업데이트 시간 저장
        db.set_setting("last_news_update", get_kst_now().strftime("%Y-%m-%d %H:%M:%S"))

        logger.info(f"Total news fetched: {total_cnt}")
        return total_cnt

    except Exception as e:
        logger.error(f"Error in fetch_news: {e}")
        import traceback
        traceback.print_exc()
        return 0


def main():
    """메인 함수 - 스케줄러 실행"""
    logger.info("=" * 50)
    logger.info("News Scheduler Started")
    logger.info("=" * 50)
    logger.info("Schedule: Every 1 hour")
    logger.info("=" * 50)

    # 바로 한 번 실행
    logger.info("Running immediate fetch...")
    fetch_news()

    # 무한 루프 - 매 시간 체크
    while True:
        try:
            # 1시간마다 뉴스 수집
            time.sleep(3600)  # 1시간 = 3600초

            logger.info("Fetching news (scheduled)...")
            fetch_news()

        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(60)  # 에러 시 1분 후 재시도


if __name__ == "__main__":
    main()
