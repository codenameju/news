# News & Voca Pro - AI 영어 학습 플랫폼

RSS 피드에서 경제 뉴스를 자동으로 수집하고 AI로 분석하여 텔레그램으로 전송하는 어플리케이션입니다.

## 🚀 기능

- 📰 **AI 경제 브리핑**: RSS 피드에서 뉴스 수집 및 AI 분석
- 📚 **AI 단어장**: 이미지/텍스트에서 단어 추출 및 학습 관리
- 🧠 **Sentence Quiz**: 단어를 사용하여 문장 만들기 퀴즈
- 📱 **텔레그램 알림**: 스케줄링된 뉴스 및 단어 퀴즈
- ⏰ **자동 업데이트**: 정기적인 뉴스 수집

## 🛠️ 실행 방법

### 방법 1: Streamlit 앱 (메인 앱)

```bash
streamlit run app.py
```

**기능:**
- 뉴스 브라우징
- 단어장 관리
- 문장 퀴즈
- 설정/백업

---

### 방법 2: 뉴스 스케줄러 (1시간마다 뉴스 수집)

```bash
python news_scheduler.py
```

**기능:**
- RSS 피드에서 뉴스 수집
- AI로 뉴스 분석
- 데이터베이스에 저장

**API 키 설정**:
```bash
export GOOGLE_API_KEY=your_key
export GROQ_API_KEY=your_key  # 선택사항
export XAI_API_KEY=your_key     # 선택사항
```

---

### 방법 3: 텔레그램 봇 (알림 전송)

```bash
python telegram_bot.py
```

**기능:**
- 06:00, 12:00, 18:00 KST: 뉴스 알림 (DB에서 미전송 뉴스만)
- 3시간마다: 단어 퀴즈 (랜덤 미학습 단어 5개)

**환경 변수 설정** (.env 파일):
```bash
TELEGRAM_TOKEN=8550186803:AAGEDWmforGFn_QQyWUY8E6b6jDHN8LJZXM
TELEGRAM_CHAT_ID=5272469108
GOOGLE_API_KEY=your_key
GROQ_API_KEY=your_key
XAI_API_KEY=your_key
```

---

### 방법 4: Webhook 핸들러 ("다시 받기" 버튼)

**Webhook 설정 (한 번만 실행)**:
```bash
export WEBHOOK_URL=https://your-domain.com
python webhook_handler.py --set-webhook
```

**Webhook 서버 실행**:
```bash
python webhook_handler.py
```

---

## 📊 아키텍처

```
┌─────────────────┐
│ news_scheduler │  1시간마다 뉴스 수집
│   .py        │  (RSS → AI → DB)
└────────┬────────┘
         │
         ▼
┌─────────────────┐     06:00, 12:00, 18:00 KST
│   Database     │◄───┐
│  (SQLite)      │     │ DB에서 미전송 뉴스 조회
└────────┬────────┘     │
         │              ▼
         │     ┌─────────────────┐
         │     │ telegram_bot.py │  텔레그램으로 전송
         │     │                 │  3시간마다 단어 퀴즈
         │     └─────────────────┘
         │              │
         │              ▼
         │     ┌─────────────────┐
         └────▶│  Telegram Bot  │
               │    (API)      │
               └─────────────────┘
```

---

## 🔧 설정

### 뉴스 스케줄 (Streamlit 앱)
1. 앱 접속
2. `⚙️ 설정/백업` 탭 선택
3. `⏰ 뉴스 스케줄` 탭 선택
4. 시간 설정 (최대 5개, HH:MM 형식)
5. `💾 스케줄 저장` 클릭

### API 키 설정 (.streamlit/secrets.toml)
```toml
[default]
GOOGLE_API_KEY = "your-google-api-key"
GROQ_API_KEY = "your-groq-api-key"
XAI_API_KEY = "your-xai-api-key"
```

---

## 📦 의존성

```bash
pip install -r requirements.txt
```

**주요 패키지:**
- streamlit: 웹 앱 프레임워크
- google-genai: AI 모델 (Gemini)
- groq: AI 모델 (Groq)
- openai: AI 모델 (xAI/Grok)
- feedparser: RSS 피드 파싱
- schedule: 작업 스케줄링
- flask: Webhook 서버

---

## 🗄️ 데이터베이스

**데이터베이스 파일**: `my_english_study_final.db`

**테이블:**
- `news`: 뉴스 기사
- `vocab`: 단어장
- `quiz_log`: 퀴즈 기록
- `settings`: 설정

---

## 🧪 테스트

```bash
python test_telegram_bot.py
```

**테스트 항목:**
- 텔레그램 연결
- 뉴스 수집
- 카드뉴스 생성
- 단어 퀴즈

---

## 📝 참고

- **뉴스 소스**: BBC News RSS (Economy, Society, World)
- **AI 모델 순위**: Groq → xAI → Gemini (속도/쿼터 기준)
- **시간대**: 한국 시간 (KST)
- **중복 방지**: URL 기반 중복 체크

---

## 📄 라이선스

MIT License
