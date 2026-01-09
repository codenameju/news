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
        "Economy": "https://news.google.com/rss/topics/CAAqIggKIhxDQkFTRHdvSkwyMHZNR2RtY0hNekVnSmxiaWdBUAE?hl=ko&gl=KR&ceid=KR:ko",
        "Tech": "https://news.google.com/rss/topics/CAAqIggKIhxDQkFTRHdvSkwyMHZNR1F4TG5vZUVnSmxiaWdBUAE?hl=ko&gl=KR&ceid=KR:ko",
        "Society": "https://news.google.com/rss/topics/CAAqIggKIhxDQkFTRHdvSkwyMHZNR2_yDQhNekVnSmxiaWdBUAE?hl=ko&gl=KR&ceid=KR:ko",
        "World": "https://news.google.com/rss/topics/CAAqIggKIhxDQkFTRHdvSkwyMHZNR2_yDQhNekVnSmxiaWdBUAE?hl=ko&gl=KR&ceid=KR:ko"
    }

st.set_page_config(page_title=Config.PAGE_TITLE, page_icon=Config.PAGE_ICON, layout="wide")

# ==========================================
# 🛠️ 1. 유틸리티
# ==========================================
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
    Youdao API 사용 (단어 전용)
    """
    if not text: return ""
    
    # 텍스트 정제
    clean_text = str(text).replace('\n', ' ').replace('"', '').replace("'", "").strip()
    if not clean_text: return ""
    
    encoded_text = urllib.parse.quote(clean_text)
    tts_url = f"https://dict.youdao.com/dictvoice?audio={encoded_text}&type=1"
    
    return f"""
    <audio controls style="height: 25px; width: 220px; margin-top:5px; margin-bottom:5px;">
        <source src="{tts_url}" type="audio/mpeg">
    </audio>
    """

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
                        UNIQUE(book, word)
                    )''')
            c.execute('''CREATE TABLE IF NOT EXISTS quiz_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        word_id INTEGER, is_correct BOOLEAN, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            conn.commit()

    def check_url_exists(self, url):
        with self.get_connection() as conn:
            res = conn.execute("SELECT 1 FROM news WHERE url=?", (url,)).fetchone()
            return res is not None

    def save_news_bulk(self, news_list):
        if not news_list: return 0
        today = datetime.date.today().isoformat()
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
        today = datetime.date.today().isoformat()
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
        query = "SELECT id, word, meaning, sentence, example, grammar FROM vocab WHERE book=? AND status=?"
        params = [book, status]

        if search_query and search_query.strip():
            search_term = f"%{search_query.strip()}%"
            query += " AND (word LIKE ? OR meaning LIKE ? OR sentence LIKE ?)"
            params.extend([search_term, search_term, search_term])

        query += " ORDER BY id DESC"

        with self.get_connection() as conn:
            return conn.execute(query, params).fetchall()

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
            
    def get_stats(self):
        """학습 통계 (전체, 일일, 주간)"""
        with self.get_connection() as conn:
            # 전체 통계
            res = conn.execute("SELECT COUNT(*), SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) FROM quiz_log").fetchone()
            total = res[0] if res[0] else 0
            correct = res[1] if res[1] else 0

            # 오늘 통계
            today = datetime.date.today().isoformat()
            res_today = conn.execute(
                "SELECT COUNT(*), SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) FROM quiz_log WHERE DATE(created_at) = ?",
                (today,)
            ).fetchone()
            today_total = res_today[0] if res_today[0] else 0
            today_correct = res_today[1] if res_today[1] else 0

            # 이번 주 통계 (최근 7일)
            week_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
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

        1. **📊 현상 (The Fact)**: What happened? (Include exact numbers).
        2. **🔍 원인 분석 (Why)**: WHY did this happen? (Root cause).
        3. **🔮 전망 및 경고 (Outlook)**: Risk or implication.

        Output JSON keys:
        - "title": Korean title
        - "summary": "A single string combining the 3 points above with newlines."
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
                    csv_data = pd.DataFrame(words, columns=["ID", "Word", "Meaning", "Sentence", "Examples", "Grammar"])
                    csv_bytes = csv_data.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 CSV 다운로드",
                        data=csv_bytes,
                        file_name=f"{sel_book}_{status_filter}.csv",
                        mime="text/csv"
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

                    for w in words:
                        word_id = w[0]
                        with st.container():
                            col_chk, col_content = st.columns([1, 15])
                            with col_chk:
                                st.checkbox("", key=f"chk_{word_id}")
                            
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
        
        books = db.get_books()
        if books:
            target = st.selectbox("단어장 선택", books)
            if st.button("PDF 다운로드"):
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

        st.divider()
        if os.path.exists(Config.DB_FILE):
            with open(Config.DB_FILE, "rb") as f:
                st.download_button("💽 DB 백업 (.db)", f, "backup.db")

if __name__ == "__main__":
    main()