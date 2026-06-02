from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import sqlite3
import requests

app = FastAPI()

# 初始化 SQLite 資料庫
def init_db():
    conn = sqlite3.connect("vocab.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vocabulary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT UNIQUE NOT NULL,
            translation TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# 定義前端傳過來的資料格式
class WordModel(BaseModel):
    word: str

# 查詢免費字典 API 獲取中文翻譯
def fetch_translation(word: str) -> str:
    try:
        # 使用有道翻譯的公開 API 進行簡配版查詢
        url = f"https://dict.youdao.com/suggest?q={word}&le=eng&num=1&doctype=json"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            explanation = data.get('data', {}).get('entries', [{}])[0].get('explain', '')
            if explanation:
                return explanation
        return "未找到翻譯，可手動編輯"
    except Exception:
        return "網路查詢失敗，可手動儲存"

# API：獲取所有單字
@app.get("/api/words")
def get_words():
    conn = sqlite3.connect("vocab.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, word, translation FROM vocabulary ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "word": r[1], "translation": r[2]} for r in rows]

# API：新增單字（自動查翻譯）
@app.post("/api/words")
def add_word(item: WordModel):
    word_clean = item.word.strip()
    if not word_clean:
        raise HTTPException(status_code=400, detail="單字不能為空")
    
    translation = fetch_translation(word_clean)
    
    try:
        conn = sqlite3.connect("vocab.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO vocabulary (word, translation) VALUES (?, ?)", (word_clean, translation))
        conn.commit()
        conn.close()
        return {"status": "success", "word": word_clean, "translation": translation}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="單字已存在於筆記本中")

# API：刪除單字
@app.delete("/api/words/{word_id}")
def delete_word(word_id: int):
    conn = sqlite3.connect("vocab.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vocabulary WHERE id = ?", (word_id,))
    conn.commit()
    conn.close()
    return {"status": "success"}

# 預設首頁：直接載入前端畫面
@app.get("/", response_class=HTMLResponse)
def index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()