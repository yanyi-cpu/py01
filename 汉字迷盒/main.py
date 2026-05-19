import os
import re
import logging
from datetime import datetime
from typing import Any, Optional

import pymysql
from fastapi import FastAPI
from openai import OpenAI
from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# ============================================
# MySQL 配置 — 改成你自己的
# ============================================
MYSQL_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "123456",
    "database": "ai_chat",
    "charset": "utf8mb4",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
)

app = FastAPI(title="AI 对话系统")
app.mount("/static", StaticFiles(directory="static"), name="static")

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)


# ============================================
# 数据库工具
# ============================================

def get_db():
    """获取 MySQL 连接（记得用完 close）"""
    return pymysql.connect(**MYSQL_CONFIG)


def init_db():
    """建库建表（幂等）"""
    # 先建库
    cfg = {k: v for k, v in MYSQL_CONFIG.items() if k != "database"}
    conn = pymysql.connect(**cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE DATABASE IF NOT EXISTS `%s` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                % MYSQL_CONFIG["database"]
            )
        conn.commit()
    finally:
        conn.close()

    # 建表
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id VARCHAR(30) PRIMARY KEY,
                    title VARCHAR(30) NOT NULL DEFAULT '',
                    char_name TEXT,
                    char_personality TEXT,
                    char_appearance TEXT,
                    char_background TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    session_id VARCHAR(30) NOT NULL,
                    role VARCHAR(20) NOT NULL,
                    content TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_session (session_id),
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        db.commit()
    finally:
        db.close()


# 启动时初始化
init_db()


# ============================================
# 业务逻辑（不变）
# ============================================

def build_system_prompt(ch: dict) -> str:
    name = ch.get("name", "").strip()
    personality = ch.get("personality", "").strip()
    appearance = ch.get("appearance", "").strip()
    background = ch.get("background", "").strip()

    parts = ["你将扮演一个角色与用户对话。请严格遵守以下角色设定，沉浸式扮演，不要跳出角色。"]
    if name:
        parts.append(f"你的名字：{name}")
    if personality:
        parts.append(f"性格特征：{personality}")
    if appearance:
        parts.append(f"外貌描述：{appearance}")
    if background:
        parts.append(f"背景故事：{background}")
    parts.append("请根据以上设定，用符合角色身份的语气、口吻与用户进行自然对话。要简短精炼，不要长篇大论。")

    return "\n".join(parts)


def make_session_id(title: str) -> str:
    """把 AI 标题转为安全 ID，处理重名"""
    name = re.sub(r'[^一-龥a-zA-Z0-9_\-]', '', title).strip()
    if not name:
        name = "未命名对话"
    if len(name) > 20:
        name = name[:20]

    db = get_db()
    try:
        base = name
        counter = 1
        with db.cursor() as cur:
            while True:
                cur.execute("SELECT 1 FROM sessions WHERE id = %s", (name,))
                if cur.fetchone() is None:
                    break
                name = f"{base}_{counter}"
                counter += 1
    finally:
        db.close()
    return name


def generate_title(messages: list) -> str:
    prompt = (
        "请用3到8个汉字概括以下对话的主题，"
        "只输出概括文字，不要输出引号、标点或任何其他内容：\n\n"
    )
    dialogue = []
    for m in messages:
        role = "用户" if m["role"] == "user" else "角色"
        dialogue.append(f"{role}：{m['content']}")
    prompt += "\n".join(dialogue)

    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=20
        )
        title = resp.choices[0].message.content.strip()
        title = title.replace("《", "").replace("》", "").replace("「", "").replace("」", "")
        title = title.replace('"', '').replace("'", '')
        return title if title else "新对话"
    except Exception:
        return "新对话"


# ============================================
# 数据模型
# ============================================

class ApiResponse(BaseModel):
    code: int
    message: str
    data: Any


class CharacterConfig(BaseModel):
    name: str = ""
    personality: str = ""
    appearance: str = ""
    background: str = ""


class ChatRequest(BaseModel):
    session_id: str = ""
    message: str
    character: Optional[CharacterConfig] = None


# ============================================
# 路由
# ============================================

@app.get("/")
def root():
    return FileResponse("static/index.html")


@app.get("/manifest.json")
def pwa_manifest():
    return FileResponse("manifest.json")


@app.get("/service-worker.js")
def pwa_sw():
    return FileResponse("service-worker.js")


# ---- 会话列表 ----

@app.get("/api/sessions")
def get_sessions() -> ApiResponse:
    db = get_db()
    try:
        with db.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                "SELECT id, title FROM sessions ORDER BY updated_at DESC"
            )
            rows = cur.fetchall()
        return ApiResponse(code=200, message="成功", data=rows)
    finally:
        db.close()


# ---- 获取单个会话 ----

@app.get("/api/sessions/{session_id}")
def get_session(session_id: str) -> ApiResponse:
    db = get_db()
    try:
        with db.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SELECT * FROM sessions WHERE id = %s", (session_id,))
            session = cur.fetchone()
            if session is None:
                return ApiResponse(code=404, message="会话不存在", data=None)

            cur.execute(
                "SELECT role, content FROM messages WHERE session_id = %s ORDER BY id ASC",
                (session_id,)
            )
            messages = cur.fetchall()

        return ApiResponse(code=200, message="成功", data={
            "session_id": session["id"],
            "title": session["title"],
            "character": {
                "name": session["char_name"] or "",
                "personality": session["char_personality"] or "",
                "appearance": session["char_appearance"] or "",
                "background": session["char_background"] or "",
            },
            "messages": messages
        })
    finally:
        db.close()


# ---- 更新角色 ----

@app.put("/api/sessions/{session_id}/character")
def update_character(session_id: str, character: CharacterConfig) -> ApiResponse:
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "UPDATE sessions SET char_name=%s, char_personality=%s, "
                "char_appearance=%s, char_background=%s WHERE id=%s",
                (character.name, character.personality,
                 character.appearance, character.background, session_id)
            )
            if cur.rowcount == 0:
                return ApiResponse(code=404, message="会话不存在", data=None)
        db.commit()
        return ApiResponse(code=200, message="角色已更新", data={
            "name": character.name,
            "personality": character.personality,
            "appearance": character.appearance,
            "background": character.background
        })
    finally:
        db.close()


# ---- 删除会话 ----

@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str) -> ApiResponse:
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("DELETE FROM sessions WHERE id = %s", (session_id,))
        db.commit()
        return ApiResponse(code=200, message="已删除", data=None)
    finally:
        db.close()


# ---- 聊天 ----

@app.post("/api/chat")
def chat(request: ChatRequest) -> ApiResponse:
    logging.info(f"收到消息 — session={request.session_id or '(新)'}, msg={request.message[:50]}")

    # ==================== 新对话 ====================
    if not request.session_id:
        ch = request.character or CharacterConfig()
        ch_dict = {
            "name": ch.name,
            "personality": ch.personality,
            "appearance": ch.appearance,
            "background": ch.background
        }
        system_prompt = build_system_prompt(ch_dict)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request.message}
        ]

        logging.info("-----> 新对话请求AI")
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=1.0
        )
        ai_text = response.choices[0].message.content
        logging.info(f"<----- AI响应: {ai_text[:80]}")

        # 生成标题 + ID
        exchange = [
            {"role": "user", "content": request.message},
            {"role": "assistant", "content": ai_text}
        ]
        title = generate_title(exchange)
        session_id = make_session_id(title)

        # 写入 MySQL（用事务）
        db = get_db()
        try:
            with db.cursor() as cur:
                cur.execute(
                    "INSERT INTO sessions (id, title, char_name, char_personality, "
                    "char_appearance, char_background) VALUES (%s,%s,%s,%s,%s,%s)",
                    (session_id, title, ch_dict["name"], ch_dict["personality"],
                     ch_dict["appearance"], ch_dict["background"])
                )
                cur.execute(
                    "INSERT INTO messages (session_id, role, content) VALUES (%s,%s,%s)",
                    (session_id, "user", request.message)
                )
                cur.execute(
                    "INSERT INTO messages (session_id, role, content) VALUES (%s,%s,%s)",
                    (session_id, "assistant", ai_text)
                )
            db.commit()
        finally:
            db.close()

        return ApiResponse(code=200, message="创建成功", data={
            "session_id": session_id,
            "title": title,
            "reply": ai_text
        })

    # ==================== 继续对话 ====================
    db = get_db()
    try:
        # 查会话
        with db.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SELECT * FROM sessions WHERE id = %s", (request.session_id,))
            session = cur.fetchone()
        if session is None:
            return ApiResponse(code=404, message="会话不存在", data=None)

        ch = {
            "name": session["char_name"] or "",
            "personality": session["char_personality"] or "",
            "appearance": session["char_appearance"] or "",
            "background": session["char_background"] or "",
        }
        system_prompt = build_system_prompt(ch)

        # 查历史消息
        with db.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                "SELECT role, content FROM messages WHERE session_id = %s ORDER BY id ASC",
                (request.session_id,)
            )
            history = cur.fetchall()

        messages = [{"role": "system", "content": system_prompt}]
        for m in history:
            messages.append({"role": m["role"], "content": m["content"]})
        messages.append({"role": "user", "content": request.message})

        logging.info("-----> 继续对话请求AI")
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=1.0
        )
        ai_text = response.choices[0].message.content
        logging.info(f"<----- AI响应: {ai_text[:80]}")

        # 保存两条新消息
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO messages (session_id, role, content) VALUES (%s,%s,%s)",
                (request.session_id, "user", request.message)
            )
            cur.execute(
                "INSERT INTO messages (session_id, role, content) VALUES (%s,%s,%s)",
                (request.session_id, "assistant", ai_text)
            )
            # 顺手更新会话时间
            cur.execute(
                "UPDATE sessions SET updated_at = NOW() WHERE id = %s",
                (request.session_id,)
            )
        db.commit()
    finally:
        db.close()

    return ApiResponse(code=200, message="成功", data={
        "session_id": request.session_id,
        "title": session["title"],
        "reply": ai_text
    })


# ============================================
# 异常处理
# ============================================

@app.exception_handler(Exception)
def handle_exception(request: Request, exc: Exception):
    logging.error(f"异常 — {request.url} — {exc}")
    return JSONResponse(content={"code": 500, "message": "服务器异常", "data": None})


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8099)
