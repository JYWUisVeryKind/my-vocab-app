from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import asyncio
import asyncpg
import os
import requests
import json

app = FastAPI()

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# 簡易繁簡轉換字典（處理常見高頻字與結尾）
def to_traditional(text: str) -> str:
    # 這裡加入常見的單字查閱會遇到的簡轉繁對照
    mapping = {
        "查": "查", "个": "個", "两": "兩", "么": "麼", "动": "動", "国": "國",
        "语": "語", "对": "對", "导": "導", "复": "複", "时": "時", "机": "機",
        "发": "發", "电": "電", "体": "體", "会": "會", "经": "經", "义": "義",
        "结": "結", "给": "給", "统": "統", "论": "論", "设": "設", "证": "證",
        "评": "評", "识": "識", "说": "說", "软": "軟", "转": "轉", "连": "連",
        "进": "進", "选": "選", "较": "較", "还": "還", "总": "總", "应": "應",
        "变": "變", "开": "開", "间": "間", "关": "關", "类": "類", "验": "驗",
        "头": "頭", "实": "實", "业": "業", "产": "產", "长": "長", "专": "專",
        "东": "東", "车": "車", "显": "顯", "务": "務", "从": "從", "众": "眾",
        "书": "書", "买": "買", "卖": "賣", "质": "質", "无": "無", "标": "標"
    }
    # 先做基礎字集替換
    for s, t in mapping.items():
        text = text.replace(s, t)
    
    # 透過網頁公開 API 進行精準繁體化（若 API 失效則保留基礎替換結果）
    try:
        cc_url = f"https://api.iyk0.com/sc2tc/?text={text}"
        res = requests.get(cc_url, timeout=3)
        if res.status_code == 200 and res.json().get("code") == 200:
            return res.json().get("text", text)
    except Exception:
        pass
    return text

def fetch_translation(text: str) -> str:
    try:
        # 更換為有道長句/片語翻譯介面
        url = "https://fanyi.youdao.com/translate?&doctype=json&type=AUTO"
        data = {'i': text}
        response = requests.post(url, data=data, timeout=5)
        
        if response.status_code == 200:
            result = response.json()
            # 解析傳回的句子/片語翻譯
            translate_results = result.get('translateResult', [])
            if translate_results and translate_results[0]:
                tgt_text = "".join([tgt.get('tgt', '') for tgt in translate_results[0]])
                if tgt_text:
                    # 將結果轉換為繁體中文
                    return to_traditional(tgt_text)
        return "未找到翻譯，可手動編輯"
    except Exception as e:
        print(f"翻譯出錯: {e}")
        return "網路查詢失敗"

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
        raise HTTPException(status_code=400, detail="內容不能為空")
    
    translation = fetch_translation(word_clean)
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("INSERT INTO vocabulary (word, translation) VALUES ($1, $2)", word_clean, translation)
        await conn.close()
        return {"status": "success", "word": word_clean, "translation": translation}
    except Exception:
        raise HTTPException(status_code=400, detail="該內容已存在或儲存失敗")

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
