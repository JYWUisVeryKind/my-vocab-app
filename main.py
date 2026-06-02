from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import asyncio
import asyncpg
import os

app = FastAPI()

DATABASE_URL = os.getenv("DATABASE_URL")

# 將 Render 的 postgres:// 取代為 asyncpg 支援的 postgresql://
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

async def init_db():
    if DATABASE_URL:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS vocabulary (
                id SERIAL PRIMARY KEY,
                word TEXT UNIQUE NOT NULL,
                translation TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await conn.close()

@app.on_event("startup")
async def startup_event():
    await init_db()

class WordModel(BaseModel):
    word: str

def fetch_translation(word: str) -> str:
    import requests
    try:
        url = f"https://dict.youdao.com/suggest?q={word}&le=eng&num=1&doctype=json"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            explanation = data.get('data', {}).get('entries', [{}])[0].get('explain', '')
            if explanation:
                return explanation
        return "未找到翻譯，可手動編輯"
    except Exception:
        return "網路查詢失敗"

@app.get("/api/words")
async def get_words():
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch("SELECT id, word, translation FROM vocabulary ORDER BY id DESC")
    await conn.close()
    return [{"id": r["id"], "word": r["word"], "translation": r["translation"]} for r in rows]

@app.post("/api/words")
async def add_word(item: WordModel):
    word_clean = item.word.strip()
    if not word_clean:
        raise HTTPException(status_code=400, detail="單字不能為空")
    
    translation = fetch_translation(word_clean)
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("INSERT INTO vocabulary (word, translation) VALUES ($1, $2)", word_clean, translation)
        await conn.close()
        return {"status": "success", "word": word_clean, "translation": translation}
    except Exception:
        raise HTTPException(status_code=400, detail="單字已存在或儲存失敗")

@app.delete("/api/words/{word_id}")
async def delete_word(word_id: int):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("DELETE FROM vocabulary WHERE id = $1", word_id)
    await conn.close()
    return {"status": "success"}

@app.get("/", response_class=HTMLResponse)
def index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()
