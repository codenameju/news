#!/usr/bin/env python3
# ==========================================
# 텔레그램 봇 테스트 스크립트
# ==========================================

import os
import sys

# 경로 설정
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestBot")

try:
    from telegram_bot import send_telegram_message, fetch_latest_news, create_card_news_with_buttons, get_kst_now
    from app import DatabaseManager, Config

    def test_telegram_connection():
        """텔레그램 연결 테스트"""
        logger.info("=" * 50)
        logger.info("Test 1: Telegram Connection")
        logger.info("=" * 50)

        kst_time = get_kst_now().strftime("%Y년 %m월 %d일 %H:%M (KST)")

        message = f"""<b>🧪 텔레그램 봇 테스트</b>
<i>{kst_time}</i>

✅ 텔레그램 봇이 정상적으로 작동합니다!

이 메시지가 도착하면 설정이 완료된 것입니다.
"""
        success = send_telegram_message(message)

        if success:
            logger.info("✅ Telegram connection test PASSED")
        else:
            logger.error("❌ Telegram connection test FAILED")
        return success

    def test_news_fetch():
        """뉴스 수집 테스트"""
        logger.info("=" * 50)
        logger.info("Test 2: News Fetch")
        logger.info("=" * 50)

        try:
            count = fetch_latest_news()
            logger.info(f"✅ News fetch test PASSED - Fetched {count} news articles")
            return count
        except Exception as e:
            logger.error(f"❌ News fetch test FAILED: {e}")
            return 0

    def test_news_card():
        """카드뉴스 생성 테스트"""
        logger.info("=" * 50)
        logger.info("Test 3: Card News Generation")
        logger.info("=" * 50)

        try:
            db = DatabaseManager(Config.DB_FILE)
            from telegram_bot import get_kst_today
            today = get_kst_today()
            news_list = db.get_news(date_filter=today)

            if not news_list:
                logger.warning("⚠️ No news found for today, creating test data...")

                # 테스트용 뉴스 생성
                news_list = [
                    (1, "테스트 뉴스 제목 1", "이것은 테스트 뉴스 요약입니다.", "https://example.com/1", today, "Economy", 0),
                    (2, "테스트 뉴스 제목 2", "이것은 두 번째 테스트 뉴스 요약입니다.", "https://example.com/2", today, "Society", 0),
                ]

            message, reply_markup = create_card_news_with_buttons(news_list, max_count=3)

            logger.info(f"Generated card news with {len(news_list)} articles")
            logger.info(f"Message preview:\n{message[:200]}...")

            if reply_markup:
                logger.info(f"Button count: {len(reply_markup['inline_keyboard'])}")

            logger.info("✅ Card news generation test PASSED")

            # 텔레그램으로 테스트 전송
            success = send_telegram_message(message, reply_markup)

            if success:
                logger.info("✅ Card news telegram send test PASSED")
            else:
                logger.error("❌ Card news telegram send test FAILED")

            return success

        except Exception as e:
            logger.error(f"❌ Card news generation test FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False

    def main():
        """메인 테스트 함수"""
        logger.info("\n" + "=" * 50)
        logger.info("🧪 Telegram Bot Test Suite")
        logger.info("=" * 50 + "\n")

        # 테스트 실행
        results = []

        # 1. 텔레그램 연결 테스트
        results.append(("Telegram Connection", test_telegram_connection()))

        # 2. 뉴스 수집 테스트 (API 키 필요)
        results.append(("News Fetch", test_news_fetch() > 0))

        # 3. 카드뉴스 생성 및 전송 테스트
        results.append(("Card News Generation", test_news_card()))

        # 결과 요약
        logger.info("\n" + "=" * 50)
        logger.info("📊 Test Results Summary")
        logger.info("=" * 50)

        for test_name, result in results:
            status = "✅ PASSED" if result else "❌ FAILED"
            logger.info(f"{test_name}: {status}")

        passed = sum(1 for _, r in results if r)
        total = len(results)

        logger.info(f"\nTotal: {passed}/{total} tests passed")

        if passed == total:
            logger.info("\n🎉 All tests passed! The bot is ready to run.")
            return 0
        else:
            logger.warning(f"\n⚠️ {total - passed} test(s) failed. Please check the errors above.")
            return 1

    if __name__ == "__main__":
        sys.exit(main())

except Exception as e:
    logger.error(f"Fatal error in test script: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
