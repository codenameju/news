import streamlit as st
from google import genai
from groq import Groq
from openai import OpenAI
import feedparser
import sqlite3
import datetime
import os
import requests
import time
import logging
import json
import re
import pandas as pd
import urllib.parse
from PIL import Image
from fpdf import FPDF
import base64
import pytz
import threading
import subprocess

# ==========================================
# ⚙️ 0. 설정 및 로깅
# ==========================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("StudyApp")

class Config:
    PAGE_TITLE = "Insight & Voca Pro v22.1 (Text Input Added)"
    PAGE_ICON = "⚡"
    
    # DB 파일명 (데이터 유지)
    DB_FILE = 'my_english_study_final.db' 
    
    FONT_DIR = "./fonts"
    FONT_REG = os.path.join(FONT_DIR, "NanumGothic.ttf")
    FONT_BOLD = os.path.join(FONT_DIR, "NanumGothicBold.ttf")
    FONT_URL_REG = "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Regular.ttf"
    FONT_URL_BOLD = "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Bold.ttf"

    RSS_MAP = {
        "Economy": "https://feeds.bbci.co.uk/news/business/rss.xml",
        "Society": "https://feeds.bbci.co.uk/news/uk/rss.xml",
        "World": "https://feeds.bbci.co.uk/news/world/rss.xml"
    }

st.set_page_config(page_title=Config.PAGE_TITLE, page_icon=Config.PAGE_ICON, layout="wide")

# ==========================================
# 🛠️ 1. 유틸리티
# ==========================================
def get_kst_now():
    """한국 시간(KST) datetime 객체 반환"""
    kst = pytz.timezone('Asia/Seoul')
    return datetime.datetime.now(kst)

def get_kst_today():
    """한국 시간(KST) 기준 오늘 날짜 문자열 반환 (YYYY-MM-DD)"""
    return get_kst_now().strftime('%Y-%m-%d')

def ensure_fonts():
    if not os.path.exists(Config.FONT_DIR):
        os.makedirs(Config.FONT_DIR)
    
    def download_if_needed(path, url):
        if not os.path.exists(path) or os.path.getsize(path) < 1000:
            try:
                r = requests.get(url, timeout=10)
                with open(path, "wb") as f: f.write(r.content)
            except Exception as e:
                logger.error(f"Font download failed: {e}")
                return False
        return True

    r1 = download_if_needed(Config.FONT_REG, Config.FONT_URL_REG)
    r2 = download_if_needed(Config.FONT_BOLD, Config.FONT_URL_BOLD)
    return r1 and r2

def clean_json_response(text):
    logger.info(f"AI Raw Response (first 500 chars): {text[:500]}")
    try:
        result = json.loads(text)
        logger.info(f"JSON parsed successfully: {len(result) if isinstance(result, list) else 'not list'}")
        return result
    except json.JSONDecodeError:
        # JSON 코드 블록에서 추출 시도
        match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
        if match:
            try:
                result = json.loads(match.group(1))
                logger.info(f"JSON from code block parsed: {len(result) if isinstance(result, list) else 'not list'}")
                return result
            except json.JSONDecodeError as e:
                logger.warning(f"JSON code block parsing failed: {e}")
        # 배열 패턴으로 추출 시도
        match = re.search(r'\[[\s\S]*\]', text)
        if match:
            try:
                result = json.loads(match.group(0))
                logger.info(f"JSON from array pattern parsed: {len(result) if isinstance(result, list) else 'not list'}")
                return result
            except json.JSONDecodeError as e:
                logger.warning(f"Array pattern parsing failed: {e}")
        logger.error(f"JSON parsing failed completely. Response: {text}")
        return []

def resize_image_for_api(image_file, max_size=1024):
    img = Image.open(image_file)
    if img.width > max_size or img.height > max_size:
        img.thumbnail((max_size, max_size))
    return img

def get_audio_html(text):
    """
    Youdao TTS 사용 (영어 단어 발음, 복합어/구 지원)
    """
    if not text: return ""

    # 텍스트 정제
    clean_text = str(text).replace('\n', ' ').replace('"', '').replace("'", "").strip()
    if not clean_text: return ""

    # 복합어/구인 경우 간단어 분리 (예: "callused hand" -> "callused hand")
    # 스페이스로 구분하거나 케이스로 분리
    words = []
    current_word = ""
    for char in clean_text:
        if char.isupper() or char.islower():
            current_word += char
        else:
            if current_word:
                words.append(current_word)
            current_word = ""
    if current_word:
        words.append(current_word)

    # 단어가 너무 많으면 처음 2개만 사용
    if len(words) > 2:
        words = words[:2]

    # 각 단어에 대해 TTS URL 생성 (Youdao TTS - 영어 발음 최적화)
    audio_htmls = []
    for word in words:
        encoded_text = urllib.parse.quote(word)
        # Youdao TTS API (영어 사전, 발음 자연스럽고 정확함)
        tts_url = f"https://dict.youdao.com/dictvoice?audio={encoded_text}&type=1"

        audio_htmls.append(f"""
        <audio controls style="height: 25px; width: 180px; margin-top: 2px; margin-bottom: 2px; display:inline-block;">
            <source src="{tts_url}" type="audio/mpeg">
        </audio>
        """)

    return "".join(audio_htmls)



# ==========================================
# 🗄️ 2. 데이터베이스 매니저
# ==========================================
class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = os.path.abspath(db_path)
        self._init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path, check_same_thread=False, timeout=15)

    def _init_db(self):
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS news (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT, title TEXT, summary TEXT, url TEXT UNIQUE, category TEXT
                    )''')
            c.execute('''CREATE TABLE IF NOT EXISTS vocab (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        book TEXT, word TEXT, meaning TEXT, grammar TEXT,
                        sentence TEXT, example TEXT, added_date TEXT, status TEXT DEFAULT 'active',
                        usage_count INTEGER DEFAULT 0,
                        UNIQUE(book, word)
                    )''')
            c.execute('''CREATE TABLE IF NOT EXISTS quiz_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        word_id INTEGER, is_correct BOOLEAN, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )''')
            c.execute('''CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )''')
            # 컬럼 추가 시도 (이미 존재하는 경우 무시)
            try:
                c.execute("ALTER TABLE news ADD COLUMN is_saved INTEGER DEFAULT 0")
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e):
                    logger.warning(f"ALTER TABLE is_saved failed: {e}")
            try:
                c.execute("ALTER TABLE news ADD COLUMN user_note TEXT DEFAULT ''")
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e):
                    logger.warning(f"ALTER TABLE user_note failed: {e}")
            try:
                c.execute("ALTER TABLE news ADD COLUMN telegram_sent INTEGER DEFAULT 0")
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e):
                    logger.warning(f"ALTER TABLE telegram_sent failed: {e}")
            try:
                c.execute("ALTER TABLE news ADD COLUMN telegram_sent INTEGER DEFAULT 0")
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e):
                    logger.warning(f"ALTER TABLE telegram_sent failed: {e}")
            conn.commit()


    def check_url_exists(self, url):
        with self.get_connection() as conn:
            res = conn.execute("SELECT 1 FROM news WHERE url=?", (url,)).fetchone()
            return res is not None

    def save_news_bulk(self, news_list):
        if not news_list: return 0
        today = get_kst_today()
        count = 0
        with self.get_connection() as conn:
            c = conn.cursor()
            for item in news_list:
                try:
                    summary_raw = item.get('summary')
                    if isinstance(summary_raw, list):
                        summary_txt = "\n".join([str(x) for x in summary_raw])
                    else:
                        summary_txt = str(summary_raw) if summary_raw else ""

                    c.execute("""INSERT OR IGNORE INTO news
                              (date, title, summary, url, category, is_saved, user_note)
                              VALUES (?, ?, ?, ?, ?, 0, '')""",
                              (today, item.get('title'), summary_txt,
                               item.get('link'), item.get('category')))
                    if c.rowcount > 0: count += 1
                except Exception as e:
                    logger.error(f"DB Save Error: {e}")
            conn.commit()
        return count

    def get_news(self, category_filter=None, date_filter=None):
        """뉴스 조회 (카테고리/날짜 필터 지원)"""
        query = "SELECT id, title, summary, url, date, category, is_saved FROM news WHERE 1=1"
        params = []

        if category_filter and category_filter != "All":
            query += " AND category = ?"
            params.append(category_filter)

        if date_filter and date_filter != "All":
            query += " AND date = ?"
            params.append(date_filter)

        query += " ORDER BY date DESC, id DESC LIMIT 50"

        with self.get_connection() as conn:
            return conn.execute(query, params).fetchall()

    def get_unsent_news(self, category_filter=None, date_filter=None):
        """아직 텔레그램으로 보내지 않은 뉴스만 조회"""
        query = "SELECT id, title, summary, url, date, category, is_saved FROM news WHERE telegram_sent = 0"
        params = []

        if category_filter and category_filter != "All":
            query += " AND category = ?"
            params.append(category_filter)

        if date_filter and date_filter != "All":
            query += " AND date = ?"
            params.append(date_filter)

        query += " ORDER BY date ASC, id ASC LIMIT 10"

        with self.get_connection() as conn:
            return conn.execute(query, params).fetchall()

    def mark_news_as_sent(self, news_ids):
        """뉴스를 텔레그램으로 보낸 것으로 표시"""
        if not news_ids: return

        with self.get_connection() as conn:
            for news_id in news_ids:
                conn.execute("UPDATE news SET telegram_sent = 1 WHERE id = ?", (news_id,))
            conn.commit()

    def get_saved_news(self):
        with self.get_connection() as conn:
            query = "SELECT id, title, summary, url, date, category, user_note FROM news WHERE is_saved = 1 ORDER BY id DESC"
            return conn.execute(query).fetchall()

    def toggle_news_save(self, news_id, is_saved):
        with self.get_connection() as conn:
            conn.execute("UPDATE news SET is_saved = ? WHERE id = ?", (is_saved, news_id))
            conn.commit()

    def update_news_note(self, news_id, note):
        with self.get_connection() as conn:
            conn.execute("UPDATE news SET user_note = ? WHERE id = ?", (note, news_id))
            conn.commit()

    def add_vocab_from_df(self, book, df):
        if df.empty: return 0
        today = get_kst_today()
        count = 0
        with self.get_connection() as conn:
            c = conn.cursor()
            for _, row in df.iterrows():
                try:
                    def clean_field(val):
                        if isinstance(val, list): return " ".join([str(x) for x in val])
                        val_str = str(val) if pd.notna(val) else ""
                        return val_str.strip()

                    c.execute("""INSERT OR IGNORE INTO vocab
                                 (book, word, meaning, grammar, sentence, example, added_date, status)
                                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                              (
                                  book,
                                  clean_field(row.get('target_word')),
                                  clean_field(row.get('meaning')),
                                  clean_field(row.get('grammar_point')),
                                  clean_field(row.get('original_sentence')),
                                  clean_field(row.get('examples')),
                                  today,
                                  'active'
                              ))
                    if c.rowcount > 0: count += 1
                except Exception as e:
                    logger.error(f"Vocab Insert Error: {e}")
            conn.commit()
        return count

    def get_words(self, book, status, search_query=None):
        """단어장 조회 (검색 지원)"""
        query = "SELECT id, word, meaning, sentence, example, grammar, usage_count FROM vocab WHERE book=? AND status=?"
        params = [book, status]

        if search_query and search_query.strip():
            search_term = f"%{search_query.strip()}%"
            query += " AND (word LIKE ? OR meaning LIKE ? OR sentence LIKE ?)"
            params.extend([search_term, search_term, search_term])

        query += " ORDER BY id DESC"

        with self.get_connection() as conn:
            return conn.execute(query, params).fetchall()

    def get_word_usage(self, word_id):
        """단어 사용 횟수 가져오기"""
        with self.get_connection() as conn:
            result = conn.execute("SELECT usage_count FROM vocab WHERE id=?", (word_id,)).fetchone()
            return result[0] if result else 0

    def update_word_usage(self, word_id):
        """단어 사용 횟수 1 증가"""
        with self.get_connection() as conn:
            conn.execute("UPDATE vocab SET usage_count = COALESCE(usage_count, 0) + 1 WHERE id = ?", (word_id,))
            conn.commit()

    def update_status_bulk(self, word_ids, status):
        if not word_ids: return
        with self.get_connection() as conn:
            # 안전한 방식: 개별 실행 (SQLite IN clause 제한 회피)
            for word_id in word_ids:
                conn.execute("UPDATE vocab SET status=? WHERE id=?", (status, word_id))
            conn.commit()

    def delete_word_bulk(self, word_ids):
        if not word_ids: return
        with self.get_connection() as conn:
            # 안전한 방식: 개별 실행
            for word_id in word_ids:
                conn.execute("DELETE FROM vocab WHERE id=?", (word_id,))
            conn.commit()
            
    def get_books(self):
        with self.get_connection() as conn:
            return [r[0] for r in conn.execute("SELECT DISTINCT book FROM vocab").fetchall()]

    def rename_book(self, old_name, new_name):
        with self.get_connection() as conn:
            conn.execute("UPDATE vocab SET book=? WHERE book=?", (new_name, old_name))
            conn.commit()

    def delete_book(self, book_name):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM vocab WHERE book=?", (book_name,))
            conn.commit()

    def get_quiz_word(self):
        with self.get_connection() as conn:
            return conn.execute("SELECT id, word, meaning, sentence FROM vocab WHERE status='active' ORDER BY RANDOM() LIMIT 1").fetchone()

    def save_quiz_result(self, word_id, is_correct):
        with self.get_connection() as conn:
            conn.execute("INSERT INTO quiz_log (word_id, is_correct) VALUES (?, ?)", (word_id, is_correct))
            conn.commit()

    # ==========================
    # Settings 관련 메서드
    # ==========================
    def get_setting(self, key, default=None):
        """설정 값 가져오기"""
        with self.get_connection() as conn:
            result = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            if result:
                return result[0]
            return default

    def set_setting(self, key, value):
        """설정 값 저장하기"""
        with self.get_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
            conn.commit()

    def get_news_schedule_times(self):
        """뉴스 스케줄링 시간 목록 가져오기 (comma separated string -> list)"""
        schedule_str = self.get_setting("news_schedule_times", "06:00,12:00,18:00")
        return [t.strip() for t in schedule_str.split(",") if t.strip()]

    def set_news_schedule_times(self, times):
        """뉴스 스케줄링 시간 저장 (list -> comma separated string)"""
        schedule_str = ",".join(times)
        self.set_setting("news_schedule_times", schedule_str)

    def get_random_unlearned_words(self, count=5):
        """랜덤 미학습 단어 가져오기 (status='active'인 단어들 중에서)"""
        with self.get_connection() as conn:
            return conn.execute(
                "SELECT id, word, meaning, sentence, example, grammar FROM vocab WHERE status='active' ORDER BY RANDOM() LIMIT ?",
                (count,)
            ).fetchall()

    def get_stats(self):
        """학습 통계 (전체, 일일, 주간)"""
        with self.get_connection() as conn:
            # 전체 통계
            res = conn.execute("SELECT COUNT(*), SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) FROM quiz_log").fetchone()
            total = res[0] if res[0] else 0
            correct = res[1] if res[1] else 0

            # 오늘 통계
            today = get_kst_today()
            res_today = conn.execute(
                "SELECT COUNT(*), SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) FROM quiz_log WHERE DATE(created_at) = ?",
                (today,)
            ).fetchone()
            today_total = res_today[0] if res_today[0] else 0
            today_correct = res_today[1] if res_today[1] else 0

            # 이번 주 통계 (최근 7일)
            week_ago = (get_kst_now() - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
            res_week = conn.execute(
                "SELECT COUNT(*), SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) FROM quiz_log WHERE DATE(created_at) >= ?",
                (week_ago,)
            ).fetchone()
            week_total = res_week[0] if res_week[0] else 0
            week_correct = res_week[1] if res_week[1] else 0

            return {
                "total": {"attempts": total, "correct": correct, "accuracy": round(correct/total*100, 1) if total > 0 else 0},
                "today": {"attempts": today_total, "correct": today_correct, "accuracy": round(today_correct/today_total*100, 1) if today_total > 0 else 0},
                "week": {"attempts": week_total, "correct": week_correct, "accuracy": round(week_correct/week_total*100, 1) if week_total > 0 else 0}
            }

# ==========================================
# 🧠 3. AI 에이전트
# ==========================================
class AIAgent:
    def __init__(self, api_key, groq_api_key=None, xai_api_key=None):
        self.api_key = api_key
        self.groq_api_key = groq_api_key
        self.xai_api_key = xai_api_key
        self.client = None
        self.groq_client = None
        self.xai_client = None

        if self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.error(f"Gemini Client Init Error: {e}")

        if self.groq_api_key:
            try:
                self.groq_client = Groq(api_key=self.groq_api_key)
            except Exception as e:
                logger.error(f"Groq Client Init Error: {e}")

        if self.xai_api_key:
            try:
                self.xai_client = OpenAI(api_key=self.xai_api_key, base_url="https://api.x.ai/v1")
            except Exception as e:
                logger.error(f"xAI Client Init Error: {e}")

    def _call_gemini_with_retry(self, model, contents, max_retries=3):
        import random

        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=contents
                )
                return response
            except Exception as e:
                error_str = str(e)
                if '429' in error_str or 'RESOURCE_EXHAUSTED' in error_str:
                    if attempt < max_retries - 1:
                        wait_time = (2 ** (attempt + 1)) + random.uniform(0, 1)
                        logger.warning(f"Gemini rate limited. Waiting {wait_time:.1f}s before retry {attempt + 1}/{max_retries}")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Max retries ({max_retries}) reached. Giving up.")
                        raise e
                else:
                    raise e
        return None

    def _call_groq_with_retry(self, model, messages, max_retries=3):
        import random

        for attempt in range(max_retries):
            try:
                response = self.groq_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.5,
                    response_format={"type": "json_object"}
                )
                return response
            except Exception as e:
                error_str = str(e)
                if '429' in error_str or 'rate_limit' in error_str.lower():
                    if attempt < max_retries - 1:
                        wait_time = (2 ** (attempt + 1)) + random.uniform(0, 1)
                        logger.warning(f"Groq rate limited. Waiting {wait_time:.1f}s before retry {attempt + 1}/{max_retries}")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Max retries ({max_retries}) reached. Giving up.")
                        raise e
                else:
                    raise e
        return None

    def _call_xai_with_retry(self, model, messages, max_retries=3):
        import random

        for attempt in range(max_retries):
            try:
                response = self.xai_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.5,
                    response_format={"type": "json_object"}
                )
                return response
            except Exception as e:
                error_str = str(e)
                if '429' in error_str or 'rate_limit' in error_str.lower():
                    if attempt < max_retries - 1:
                        wait_time = (2 ** (attempt + 1)) + random.uniform(0, 1)
                        logger.warning(f"xAI rate limited. Waiting {wait_time:.1f}s before retry {attempt + 1}/{max_retries}")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Max retries ({max_retries}) reached. Giving up.")
                        raise e
                else:
                    raise e
        return None

    def curate_news(self, feed_entries, target_category):
        if not self.xai_client and not self.groq_client and not self.client:
            return []

        input_data = [{"title": e.title, "link": e.link} for e in feed_entries]

        prompt = f"""
        You are a top-tier Economic Analyst. Analyze the news (Category: {target_category}) and select top 5 most critical articles.

        For each article, provide a STRUCTURAL ANALYSIS (Korean):

        IMPORTANT: Check if the title already describes the situation/event (e.g., "Trump owns Greenland", "Arson on New Year's Eve", "Coup in Niger").

        IF the title already describes the situation:
        - SKIP "📊 현상 (The Fact)" section to avoid redundancy
        - ONLY provide: 2. **🔍 원인 분석 (Why)** and 3. **🔮 전망 및 경고 (Outlook)**
        - CRITICAL: Summary must be exactly 3 lines maximum, combining only these 2 points
        - Format: Line 1 = 원인 분석, Line 2 = 전망 및 경고 (split if needed), Line 3 = blank or very brief

        IF the title does NOT describe the situation:
        - Provide ALL 3 sections: 1. **📊 현상 (The Fact)**, 2. **🔍 원인 분석 (Why)**, 3. **🔮 전망 및 경고 (Outlook)**
        - CRITICAL: Summary must be exactly 3 lines maximum
        - Format: Line 1 = 현상, Line 2 = 원인 분석, Line 3 = 전망 및 경고

        For each article, provide:
        1. **📊 현상 (The Fact)**: What happened? (Include exact numbers).
        2. **🔍 원인 분석 (Why)**: WHY did this happen? (Root cause). Use proper sentence structure (e.g., "소유해야 한다고" → "소유해야 한다고 주장", "주장하고 있다고" → "주장하며 있다고").
        3. **🔮 전망 및 경고 (Outlook)**: Risk or implication.

        Output JSON keys:
        - "title": Korean title (keep original meaning, don't change)
        - "summary": "EXACTLY 3 LINES MAXIMUM. No more, no less. Use newlines to separate lines."
        - "link": Original link
        - "category": '{target_category}'
        """
        try:
            if self.xai_client:
                messages = [
                    {"role": "system", "content": "You are a top-tier Economic Analyst who provides structured news analysis in Korean. Output ONLY a JSON array, no wrapping object."},
                    {"role": "user", "content": f"{prompt}\nDATA: {json.dumps(input_data, ensure_ascii=False)}"}
                ]
                response = self._call_xai_with_retry('grok-beta', messages)
                if response:
                    result = clean_json_response(response.choices[0].message.content)
                    if isinstance(result, dict) and 'articles' in result:
                        return result['articles']
                    return result
                return []
            elif self.groq_client:
                messages = [
                    {"role": "system", "content": "You are a top-tier Economic Analyst who provides structured news analysis in Korean. Output ONLY a JSON array, no wrapping object."},
                    {"role": "user", "content": f"{prompt}\nDATA: {json.dumps(input_data, ensure_ascii=False)}"}
                ]
                response = self._call_groq_with_retry('llama-3.3-70b-versatile', messages)
                if response:
                    result = clean_json_response(response.choices[0].message.content)
                    if isinstance(result, dict) and 'articles' in result:
                        return result['articles']
                    return result
                return []
            else:
                response = self._call_gemini_with_retry('gemini-2.5-flash-lite', f"{prompt}\nDATA: {json.dumps(input_data, ensure_ascii=False)}")
                if response:
                    return clean_json_response(response.text)
                return []
        except Exception as e:
            logger.error(f"News AI Error: {e}")
            return []

    def extract_vocab(self, image):
        if not self.client: return []

        prompt = """
        Extract 5-8 English words. Output JSON:
        - "target_word": English word
        - "meaning": **Definition in ENGLISH ONLY**. (Simple & Clear).
        - "original_sentence": The EXACT sentence found in the image. Include full context.
        - "grammar_point": Short grammar tip (Korean)
        - "examples": Provide exactly 2 examples (ENGLISH ONLY. DO NOT include Korean translation).
        """
        try:
            response = self._call_gemini_with_retry('gemini-2.5-flash-lite', [prompt, image])
            if response:
                return clean_json_response(response.text)
            return []
        except Exception as e:
            logger.error(f"Vision AI Error: {e}")
            return []

    def generate_vocab_from_text(self, text_input):
        if not self.xai_client and not self.groq_client and not self.client:
            return []

        prompt = f"""
        Analyze the following English words or text: "{text_input}"

        For each distinct word (or key phrase) found in the input, generate a JSON object.
        Output ONLY a JSON array with these keys:
        - "target_word": The English word provided.
        - "meaning": **Definition in ENGLISH ONLY**. (Simple & Clear).
        - "original_sentence": Create a natural, high-quality sentence using this word (acting as context).
        - "grammar_point": Short grammar tip or nuance (in Korean).
        - "examples": Provide exactly 2 examples (ENGLISH ONLY).
        """
        try:
            if self.xai_client:
                messages = [
                    {"role": "system", "content": "You are a vocabulary expert who provides English definitions and example sentences. Output ONLY a JSON array, no wrapping object."},
                    {"role": "user", "content": prompt}
                ]
                response = self._call_xai_with_retry('grok-beta', messages)
                if response:
                    result = clean_json_response(response.choices[0].message.content)
                    if isinstance(result, dict) and 'words' in result:
                        return result['words']
                    return result
                return []
            elif self.groq_client:
                messages = [
                    {"role": "system", "content": "You are a vocabulary expert who provides English definitions and example sentences. Output ONLY a JSON array, no wrapping object."},
                    {"role": "user", "content": prompt}
                ]
                response = self._call_groq_with_retry('llama-3.3-70b-versatile', messages)
                if response:
                    result = clean_json_response(response.choices[0].message.content)
                    if isinstance(result, dict) and 'words' in result:
                        return result['words']
                    return result
                return []
            else:
                response = self._call_gemini_with_retry('gemini-2.5-flash-lite', prompt)
                if response:
                    return clean_json_response(response.text)
                return []
        except Exception as e:
            logger.error(f"Text Gen Error: {e}")
            return []

    def evaluate_sentence(self, target_word, user_sentence):
        if not self.xai_client and not self.groq_client and not self.client:
            return {"is_correct": False, "feedback": "API Key Error"}

        prompt = f"""
        Target Word: "{target_word}"
        User Sentence: "{user_sentence}"
        Task: Check accuracy.
        Output ONLY a JSON object: "is_correct" (bool), "feedback" (Korean).
        """
        try:
            if self.xai_client:
                messages = [
                    {"role": "system", "content": "You are an English language expert who evaluates sentence accuracy. Output ONLY a JSON object, no wrapping object."},
                    {"role": "user", "content": prompt}
                ]
                response = self._call_xai_with_retry('grok-beta', messages)
                if response:
                    result = clean_json_response(response.choices[0].message.content)
                    if isinstance(result, dict):
                        return result
                    elif isinstance(result, list) and len(result) > 0:
                        return result[0]
                    return {"is_correct": False, "feedback": "Invalid response"}
                return {"is_correct": False, "feedback": "AI Error: No response"}
            elif self.groq_client:
                messages = [
                    {"role": "system", "content": "You are an English language expert who evaluates sentence accuracy. Output ONLY a JSON object, no wrapping object."},
                    {"role": "user", "content": prompt}
                ]
                response = self._call_groq_with_retry('llama-3.3-70b-versatile', messages)
                if response:
                    result = clean_json_response(response.choices[0].message.content)
                    if isinstance(result, dict):
                        return result
                    elif isinstance(result, list) and len(result) > 0:
                        return result[0]
                    return {"is_correct": False, "feedback": "Invalid response"}
                return {"is_correct": False, "feedback": "AI Error: No response"}
            else:
                response = self._call_gemini_with_retry('gemini-2.5-flash-lite', prompt)
                if response:
                    return clean_json_response(response.text)
                return {"is_correct": False, "feedback": "AI Error: No response"}
        except Exception as e:
            return {"is_correct": False, "feedback": f"AI Error: {e}"}

# ==========================================
# 🖥️ 4. 메인 UI
# ==========================================
def main():
    st.markdown("""
    <style>
        .news-card { 
            padding:15px; border-radius:10px; background:white; margin-bottom:15px; 
            border:1px solid #ddd; box-shadow:0 2px 5px rgba(0,0,0,0.05); 
            border-left: 5px solid #2e86de;
        }
        .news-title { font-size: 1.2em; font-weight: bold; margin-bottom: 8px; color: #2d3436; }
        .news-meta { font-size: 0.8em; color: #636e72; margin-bottom: 12px; }
        .news-summary { font-size: 0.95em; color: #2d3436; line-height: 1.7; white-space: pre-wrap; font-family: 'Nanum Gothic', sans-serif; }
        .scrap-btn { color: #e55039; font-weight: bold; }
        .stCheckbox { display: flex; align-items: center; }
    </style>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.header(Config.PAGE_TITLE)

        # API Key: Secrets (.streamlit/secrets.toml)에서만 읽기
        api_key = st.secrets.get("GOOGLE_API_KEY", "")
        groq_api_key = st.secrets.get("GROQ_API_KEY", "")
        xai_api_key = st.secrets.get("XAI_API_KEY", "")

        st.divider()
        menu = st.radio("MENU", ["📰 Smart News", "📸 단어 추가", "🧠 Sentence Quiz", "⚙️ 설정/백업"])

    db = DatabaseManager(Config.DB_FILE)
    ai = AIAgent(api_key, groq_api_key, xai_api_key)

    # ==========================
    # 1. 뉴스 섹션
    # ==========================
    if menu == "📰 Smart News":
        st.subheader("📰 AI 경제 브리핑")
        
        tab_feed, tab_scrap = st.tabs(["📡 전체 뉴스 피드", "⭐ 내 스크랩북"])

        with tab_feed:
            if st.button("🔄 최신 뉴스 업데이트 (20건)", type="primary"):
                if not api_key:
                    st.error("API Key가 필요합니다.")
                else:
                    total_cnt = 0
                    progress_bar = st.progress(0)
                    status_box = st.empty()

                    categories = list(Config.RSS_MAP.items())
                    for i, (cat_name, rss_url) in enumerate(categories):
                        status_box.info(f"📡 [{cat_name}] 수집 중... ({i+1}/4)")
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
                            logger.error(f"Error {cat_name}: {e}")
                        progress_bar.progress((i + 1) / 4)
                    
                    status_box.success(f"완료! 총 {total_cnt}건의 뉴스가 추가되었습니다.")
                    time.sleep(1.5)
                    st.rerun()

            st.divider()

            # 뉴스 필터링 UI
            col_filter1, col_filter2 = st.columns([1, 1])
            with col_filter1:
                category_filter = st.selectbox("📂 카테고리 필터", ["All"] + list(Config.RSS_MAP.keys()), key="news_category_filter")
            with col_filter2:
                # 고유한 날짜 목록 가져오기
                with db.get_connection() as conn:
                    dates = [d[0] for d in conn.execute("SELECT DISTINCT date FROM news ORDER BY date DESC").fetchall()]
                date_filter = st.selectbox("📅 날짜 필터", ["All"] + dates, key="news_date_filter")

            news_list = db.get_news(category_filter, date_filter)

            if not news_list:
                st.info("표시할 뉴스가 없습니다. 업데이트를 진행해주세요.")
            else:
                for n in news_list:
                    news_id = n[0]
                    is_saved = n[6]

                    st.markdown(f"""
                    <div class="news-card">
                        <div class="news-title">{n[1]}</div>
                        <div class="news-meta">Category: {n[5]} | Date: {n[4]}</div>
                        <div class="news-summary">{n[2]}</div>
                        <div style="text-align:right; margin-top:8px;">
                            <a href="{n[3]}" target="_blank" style="text-decoration:none; color:#2e86de; font-weight:bold;">원문 보기 🔗</a>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if is_saved:
                        st.button("✅ 저장됨", disabled=True, key=f"saved_{news_id}")
                    else:
                        if st.button("📌 스크랩하기", key=f"save_{news_id}"):
                            db.toggle_news_save(news_id, 1)
                            st.rerun()
                    st.divider()

        with tab_scrap:
            saved_news = db.get_saved_news()
            if not saved_news:
                st.info("스크랩한 뉴스가 없습니다.")
            else:
                for sn in saved_news:
                    nid = sn[0]
                    note = sn[6]
                    st.markdown(f"""
                    <div class="news-card" style="border-left: 5px solid #ffa502;">
                        <span style="color:#ffa502; font-weight:bold;">⭐ Saved</span>
                        <div class="news-title">{sn[1]}</div>
                        <div class="news-meta">Category: {sn[5]} | Date: {sn[4]}</div>
                        <div class="news-summary">{sn[2]}</div>
                        <div style="text-align:right;">
                            <a href="{sn[3]}" target="_blank" style="text-decoration:none; color:#ffa502;">원문 🔗</a>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    c1, c2 = st.columns([4, 1])
                    with c1:
                        new_note = st.text_area("💬 메모", value=note, key=f"note_{nid}", height=70)
                        if st.button("💾 저장", key=f"btn_note_{nid}"):
                            db.update_news_note(nid, new_note)
                            st.success("저장됨")
                            time.sleep(0.5)
                            st.rerun()
                    with c2:
                        st.write("")
                        st.write("")
                        if st.button("🗑️ 삭제", key=f"del_{nid}"):
                            db.toggle_news_save(nid, 0)
                            st.rerun()
                    st.divider()

    # ==========================
    # 2. 단어 추가 섹션
    # ==========================
    elif menu == "📸 단어 추가":
        st.subheader("📸 AI Vocabulary Manager")
        
        tab_scan, tab_list = st.tabs(["➕ 스캔 및 자동 저장", "📝 내 단어장 (일괄 관리)"])
        
        with tab_scan:
            st.markdown("#### 📂 단어장 선택")
            books = db.get_books()
            
            col_b1, col_b2 = st.columns([2, 1])
            with col_b1:
                book_options = ["🆕 새 단어장 만들기"] + books
                sel_option = st.selectbox("단어장 선택", book_options)
            
            final_book_name = ""
            with col_b2:
                if sel_option == "🆕 새 단어장 만들기":
                    final_book_name = st.text_input("새 이름 입력", placeholder="예: 토익_Day1")
                else:
                    final_book_name = sel_option

            st.divider()
            
            # 📌 입력 방식 선택
            input_method = st.radio("입력 방식", ["📸 이미지 스캔 (책/문서)", "✍️ 텍스트 직접 입력"], horizontal=True)
            
            if input_method == "📸 이미지 스캔 (책/문서)":
                img_file = st.file_uploader("학습할 이미지 업로드", type=['png', 'jpg', 'jpeg'])
                
                if img_file and st.button("🔍 분석 및 저장", type="primary"):
                    if not final_book_name:
                        st.warning("단어장 이름을 정해주세요.")
                    elif not api_key:
                        st.error("API Key가 없습니다.")
                    else:
                        with st.spinner(f"AI가 이미지를 분석하여 '{final_book_name}'에 저장 중..."):
                            pil_img = resize_image_for_api(img_file)
                            extracted = ai.extract_vocab(pil_img)
                            if extracted:
                                new_df = pd.DataFrame(extracted)
                                cnt = db.add_vocab_from_df(final_book_name, new_df)
                                st.success(f"✅ {cnt}개 단어가 저장되었습니다!")
                                st.dataframe(new_df) 
                                time.sleep(1.5) 
                                st.rerun() 
                            else:
                                st.error("단어를 추출하지 못했습니다.")
            
            else: # 텍스트 직접 입력 모드
                st.info("추가하고 싶은 영단어를 콤마(,)나 줄바꿈으로 구분해서 입력하세요.")
                text_input = st.text_area("단어 입력 (예: ambiguous, pragmatic, take into account)", height=150)
                
                if text_input and st.button("✨ AI 카드 생성 및 저장", type="primary"):
                    if not final_book_name:
                        st.warning("단어장 이름을 정해주세요.")
                    elif not api_key:
                        st.error("API Key가 없습니다.")
                    else:
                        with st.spinner(f"AI가 단어 정보를 생성하여 '{final_book_name}'에 저장 중..."):
                            extracted = ai.generate_vocab_from_text(text_input)
                            if extracted:
                                new_df = pd.DataFrame(extracted)
                                cnt = db.add_vocab_from_df(final_book_name, new_df)
                                st.success(f"✅ {cnt}개 단어 카드가 생성되었습니다!")
                                st.dataframe(new_df)
                                time.sleep(1.5)
                                st.rerun()
                            else:
                                st.error("단어 정보를 생성하지 못했습니다. 입력을 확인해주세요.")

        with tab_list:
            books = db.get_books()
            if books:
                c_sel, c_stat = st.columns([2, 1])
                with c_sel:
                    sel_book = st.selectbox("학습할 단어장", books, key="view_book")
                with c_stat:
                    status_filter = st.radio("상태", ["active", "memorized"], format_func=lambda x: "🔥 학습 중" if x=="active" else "✅ 암기 완료", horizontal=True)

                 # 검색 기능 추가
                search_query = st.text_input("🔍 단어/의미/예문 검색", placeholder="검색어 입력...", key="vocab_search")

                words = db.get_words(sel_book, status_filter, search_query)

                # CSV 내보내기 버튼
                if words:
                    csv_data = pd.DataFrame(words, columns=["ID", "Word", "Meaning", "Sentence", "Examples", "Grammar", "Usage"])
                    csv_bytes = csv_data.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 CSV 다운로드",
                        data=csv_bytes,
                        file_name=f"{sel_book}_{status_filter}.csv",
                        use_container_width=True
                    )

                if not words:
                    st.caption("저장된 단어가 없습니다.")
                else:
                    with st.container():
                        col_act1, col_act2, col_dummy = st.columns([1, 1, 3])
                        with col_act1:
                            if st.button("✅ 선택 완료 처리"):
                                checked_ids = [w[0] for w in words if st.session_state.get(f"chk_{w[0]}", False)]
                                if checked_ids:
                                    db.update_status_bulk(checked_ids, "memorized")
                                    st.success(f"{len(checked_ids)}개 단어 암기 완료!")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.warning("선택된 단어가 없습니다.")
                        with col_act2:
                            if st.button("🗑️ 선택 삭제"):
                                checked_ids = [w[0] for w in words if st.session_state.get(f"chk_{w[0]}", False)]
                                if checked_ids:
                                    db.delete_word_bulk(checked_ids)
                                    st.success(f"{len(checked_ids)}개 단어 삭제됨!")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.warning("선택된 단어가 없습니다.")

                    st.divider()

                    # 단어 리스트 표시 (각 단어 카드로)
                    for w in words:
                        word_id = w[0]
                        with st.container():
                            # 단어 카드 상단 (체크박스 + 슬라이더 + 단어 클릭)
                            col_click, col_word, col_audio = st.columns([1, 14, 1])

                            with col_click:
                                st.checkbox("", key=f"chk_{word_id}", label_visibility="collapsed")

                            with col_word:
                                st.markdown(f"**{w[1]}**")

                            with col_audio:
                                st.markdown(get_audio_html(w[1]), unsafe_allow_html=True)

                            # 슬라이더 표시
                            usage_count = w[6] if len(w) > 6 else 0
                            if usage_count > 0:
                                st.markdown(f"<small>📊 슬라이더: {usage_count}</small>", unsafe_allow_html=True)

                            # 단어 클릭 이벤트 (usage_count 증가)
                            if st.button("🔊 단어 클릭", key=f"click_word_{word_id}", use_container_width=True):
                                db.update_word_usage(word_id)
                                st.rerun()

                            st.markdown(f"📖 **Definition:** {w[2]}")
                            st.markdown(f"📜 *{w[3]}*")
                            st.caption(f"💡 {w[4]}")
                        st.divider()


                    for w in words:
                        word_id = w[0]
                        with st.container():
                            col_chk, col_content = st.columns([1, 15])
                            with col_chk:
                                st.checkbox("", key=f"chk_{word_id}", label_visibility="collapsed")
                            
                            with col_content:
                                c_word, c_audio = st.columns([1, 4])
                                with c_word:
                                    st.markdown(f"**{w[1]}**")
                                with c_audio:
                                    st.markdown(get_audio_html(w[1]), unsafe_allow_html=True)
                                
                                st.markdown(f"📖 **Definition:** {w[2]}")
                                st.markdown(f"📜 *{w[3]}*")
                                st.caption(f"💡 {w[4]}")
                            st.divider()
            else:
                st.info("단어장이 없습니다.")

    # ==========================
    # 3. 작문 퀴즈 섹션
    # ==========================
    elif menu == "🧠 Sentence Quiz":
        st.subheader("🧠 Sentence Making Quiz")
        st.caption("제시된 단어를 사용하여 자연스러운 영어 문장을 만들어보세요.")

        # 학습 통계 표시
        stats = db.get_stats()
        col_total, col_today, col_week = st.columns(3)
        with col_total:
            st.metric("📊 전체", f"{stats['total']['attempts']}회", f"정답률 {stats['total']['accuracy']}%")
        with col_today:
            st.metric("📅 오늘", f"{stats['today']['attempts']}회", f"정답률 {stats['today']['accuracy']}%")
        with col_week:
            st.metric("📈 이번 주", f"{stats['week']['attempts']}회", f"정답률 {stats['week']['accuracy']}%")
        
        if "quiz_curr" not in st.session_state:
            st.session_state.quiz_curr = None
            st.session_state.quiz_solved = False
            st.session_state.quiz_feedback = None

        if st.session_state.quiz_curr is None:
            if st.button("🚀 작문 퀴즈 시작 (Next)", type="primary"):
                q = db.get_quiz_word()
                if q:
                    st.session_state.quiz_curr = q
                    st.session_state.quiz_solved = False
                    st.session_state.quiz_feedback = None
                    st.rerun()
                else:
                    st.warning("⚠️ 단어장이 비어있습니다.")
                    if st.button("📸 단어 추가하러 가기", type="secondary"):
                        st.session_state.quiz_curr = None
                        st.session_state.quiz_solved = False
                        st.session_state.quiz_feedback = None
                        # 메뉴 변경 힌트 (실제 메뉴 변경은 Streamlit 제약으로 어려움)
                        st.info("왼쪽 메뉴에서 '📸 단어 추가'를 선택해주세요.")

        if st.session_state.quiz_curr:
            q = st.session_state.quiz_curr
            
            st.markdown(f"""
            <div class="quiz-container">
                <div class="quiz-word">{q[1]}</div>
                <div class="quiz-meaning">{q[2]}</div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown(get_audio_html(q[1]), unsafe_allow_html=True)
            
            with st.form("sentence_form"):
                user_sentence = st.text_input("📝 위 단어를 넣어서 문장을 만드세요:", disabled=st.session_state.quiz_solved)
                submitted = st.form_submit_button("AI 선생님께 검사받기", disabled=st.session_state.quiz_solved)
                
                if submitted:
                    if not user_sentence:
                        st.error("문장을 입력해주세요.")
                    else:
                        with st.spinner("AI가 문법과 자연스러움을 체크 중입니다..."):
                            result = ai.evaluate_sentence(q[1], user_sentence)
                            st.session_state.quiz_feedback = result
                            st.session_state.quiz_solved = True
                            
                            db.save_quiz_result(q[0], result.get("is_correct", False))
                            st.rerun()

            if st.session_state.quiz_solved and st.session_state.quiz_feedback:
                res = st.session_state.quiz_feedback
                if res.get("is_correct"):
                    st.success("🎉 훌륭해요! 아주 자연스러운 문장입니다.")
                    st.markdown(f"**AI 피드백:** {res.get('feedback')}")
                else:
                    st.error("😅 조금 아쉬워요! 다시 확인해볼까요?")
                    st.markdown(f"**AI 조언:** {res.get('feedback')}")
                
                with st.expander("👀 이 단어의 원래 예문(원문) 보기"):
                    st.info(f"{q[3]}")

                col_retry, col_next = st.columns(2)
                with col_retry:
                    if st.button("🔄 다시 도전하기"):
                        st.session_state.quiz_solved = False
                        st.session_state.quiz_feedback = None
                        st.rerun()
                with col_next:
                    if st.button("다음 문제 ➡️", type="primary"):
                        st.session_state.quiz_curr = None
                        st.rerun()

    # ==========================
    # 4. 설정 섹션
    # ==========================
    elif menu == "⚙️ 설정/백업":
        st.subheader("⚙️ Settings")

        tab_general, tab_news_schedule, tab_backup = st.tabs(["📝 단어장", "⏰ 뉴스 스케줄", "💾 백업"])

        with tab_general:
            books = db.get_books()
            if books:
                target = st.selectbox("단어장 선택", books, key="pdf_book_select")
                if st.button("PDF 다운로드", key="pdf_download_btn"):
                    if ensure_fonts():
                        pdf = FPDF()
                        pdf.add_page()
                        pdf.add_font('Nanum', '', Config.FONT_REG, uni=True)
                        pdf.set_font('Nanum', '', 14)
                        pdf.cell(0, 10, f"{target}", 0, 1, 'C')
                        words = db.get_words(target, 'active')
                        pdf.set_font('Nanum', '', 11)
                        for i, w in enumerate(words):
                            pdf.cell(0, 10, f"{i+1}. {w[1]}", 0, 1)
                            pdf.multi_cell(0, 8, f"Def: {w[2]}\nOrigin: {w[3]}", border='B')
                        st.download_button("다운로드", pdf.output(dest='S').encode('latin-1'), f"{target}.pdf")
            else:
                st.info("단어장이 없습니다.")

        with tab_news_schedule:
            st.markdown("### ⏰ 뉴스 자동 업데이트 스케줄")
            st.info("설정된 시간마다 최신 뉴스를 자동으로 수집하여 사이트에 업데이트합니다. (한국 시간 기준)")

            # 현재 스케줄 표시
            current_schedule = db.get_news_schedule_times()
            st.markdown("**현재 스케줄:**")
            for time_str in current_schedule:
                st.markdown(f"- ⏰ **{time_str}** KST")

            st.divider()

            # 스케줄 설정
            st.markdown("#### 🔧 스케줄 설정")
            st.caption("최대 5개의 시간을 설정할 수 있습니다.")

            col_time1, col_time2, col_time3 = st.columns(3)
            with col_time1:
                time1 = st.text_input("시간 1", value=current_schedule[0] if len(current_schedule) > 0 else "06:00", key="schedule_time_1", placeholder="HH:MM")
            with col_time2:
                time2 = st.text_input("시간 2", value=current_schedule[1] if len(current_schedule) > 1 else "12:00", key="schedule_time_2", placeholder="HH:MM")
            with col_time3:
                time3 = st.text_input("시간 3", value=current_schedule[2] if len(current_schedule) > 2 else "18:00", key="schedule_time_3", placeholder="HH:MM")

            col_time4, col_time5, col_btn = st.columns(3)
            with col_time4:
                time4 = st.text_input("시간 4", value=current_schedule[3] if len(current_schedule) > 3 else "", key="schedule_time_4", placeholder="HH:MM (선택사항)")
            with col_time5:
                time5 = st.text_input("시간 5", value=current_schedule[4] if len(current_schedule) > 4 else "", key="schedule_time_5", placeholder="HH:MM (선택사항)")

            with col_btn:
                st.write("")  # spacing
                st.write("")
                if st.button("💾 스케줄 저장", type="primary", key="save_schedule_btn"):
                    # 유효성 검사
                    times = []
                    for t in [time1, time2, time3, time4, time5]:
                        if t.strip():
                            # 시간 형식 검사 (HH:MM)
                            import re
                            if not re.match(r'^\d{1,2}:\d{2}$', t.strip()):
                                st.error(f"'{t}'는 올바른 시간 형식이 아닙니다. HH:MM 형식으로 입력해주세요.")
                                return
                            # 시간 범위 검사
                            hour, minute = map(int, t.strip().split(':'))
                            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                                st.error(f"'{t}'는 올바른 시간이 아닙니다. 시간: 0-23, 분: 0-59")
                                return
                            times.append(t.strip())

                    if times:
                        db.set_news_schedule_times(times)
                        st.success(f"✅ 스케줄이 저장되었습니다: {', '.join(times)} KST")
                        st.info("💡 스케줄러가 실행 중이어야 자동 업데이트가 작동합니다.")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("최소 하나 이상의 시간을 설정해주세요.")

            st.divider()

            # 스케줄러 상태
            st.markdown("#### 📊 스케줄러 상태")
            st.caption("별도의 스케줄러 프로세스가 실행 중이어야 자동 업데이트가 작동합니다.")

            col_scheduler_info, col_scheduler_cmd = st.columns(2)
            with col_scheduler_info:
                st.markdown("""
**실행 방법:**

```bash
# 방법 1: 텔레그램 봇 포함
python telegram_bot.py

# 방법 2: 뉴스 업데이트만
python news_scheduler.py
```
""")
            with col_scheduler_cmd:
                st.code(
                    "python telegram_bot.py\n# 또는\npython news_scheduler.py",
                    language="bash"
                )

            # 마지막 업데이트 시간 표시
            last_update = db.get_setting("last_news_update", "업데이트 기록 없음")
            st.markdown(f"**마지막 뉴스 업데이트:** {last_update}")

        with tab_backup:
            st.markdown("### 💾 데이터 백업")

            # DB 백업
            if os.path.exists(Config.DB_FILE):
                with open(Config.DB_FILE, "rb") as f:
                    st.download_button("💽 DB 백업 (.db)", f, "backup.db", use_container_width=True)
            else:
                st.warning("DB 파일이 없습니다.")

# ==========================================
# 🔄 백그라운드 서비스 (스케줄러, 텔레그램 봇)
# ==========================================
def run_scheduler(api_keys):
    """뉴스 스케줄러 백그라운드 실행"""
    try:
        import news_scheduler
        news_scheduler.main(api_keys)
    except Exception as e:
        logger.error(f"Scheduler error: {e}")

def run_telegram_bot():
    """텔레그램 봇 백그라운드 실행"""
    try:
        import telegram_bot
        telegram_bot.main()
    except Exception as e:
        logger.error(f"Telegram bot error: {e}")

def start_background_services(api_keys):
    """백그라운드 서비스 시작"""
    # 스케줄러 스레드 시작
    scheduler_thread = threading.Thread(target=run_scheduler, args=(api_keys,), daemon=True)
    scheduler_thread.start()
    logger.info("News scheduler started in background")

    # 텔레그램 봇 스레드 시작
    bot_thread = threading.Thread(target=run_telegram_bot, args=(api_keys,), daemon=True)
    bot_thread.start()
    logger.info("Telegram bot started in background")

if __name__ == "__main__":
    api_keys = {
        "GOOGLE_API_KEY": st.secrets.get("GOOGLE_API_KEY", ""),
        "GROQ_API_KEY": st.secrets.get("GROQ_API_KEY", ""),
        "XAI_API_KEY": st.secrets.get("XAI_API_KEY", "")
    }

    start_background_services(api_keys)

    main()