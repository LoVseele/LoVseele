#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Web 后端: 用标准库 http.server 提供生成 / 批改 / 下载接口, 并托管 web/ 前端。

    python server.py [--host 127.0.0.1] [--port 8000] [--open]

接口: POST /api/generate、POST /api/grade、GET /api/download、GET /api/health
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import (  # noqa: E402
    ANSWER_FILENAME,
    EXERCISE_FILENAME,
    GRADE_FILENAME,
    MAX_OPERATORS,
    ParseError,
    ProblemGenerator,
    grade,
    write_grade_file,
    write_problem_files,
)

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(PROJECT_ROOT, "web")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")

#: 允许下载的文件名 (白名单, 防止路径穿越)
ALLOWED_DOWNLOADS = {EXERCISE_FILENAME, ANSWER_FILENAME, GRADE_FILENAME}

#: 单次请求体上限 (10000 道题的文本远小于该值)
MAX_BODY_BYTES = 8 * 1024 * 1024

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


def _split_lines(text: str):
    """把多行文本切成非空行列表。"""
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


class ApiHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器。"""

    server_version = "MathExerciseServer/1.0"
    protocol_version = "HTTP/1.1"

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, body: bytes, content_type: str, status: int = 200,
                    extra_headers: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, message: str, status: int = 400) -> None:
        self._send_json({"error": message}, status=status)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        if length > MAX_BODY_BYTES:
            raise ValueError("请求体过大")
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(f"请求体不是合法 JSON: {error}") from error
        if not isinstance(data, dict):
            raise ValueError("请求体必须是 JSON 对象")
        return data

    def log_message(self, fmt, *args):  # noqa: A003 - 覆写基类
        sys.stdout.write(f"[{time.strftime('%H:%M:%S')}] {self.address_string()} {fmt % args}\n")
        sys.stdout.flush()

    def do_GET(self):  # noqa: N802 - 基类约定
        parsed = urllib.parse.urlparse(self.path)
        route = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if route in ("/", "/index.html"):
            return self._serve_static("index.html")
        if route.startswith("/static/"):
            return self._serve_static(route[len("/static/"):])
        if route == "/api/health":
            return self._send_json({"status": "ok", "version": "1.0.0",
                                    "python": sys.version.split()[0]})
        if route == "/api/files":
            return self._list_output_files()
        if route == "/api/download":
            return self._download(query.get("name", [""])[0])
        return self._send_error_json(f"未知路径: {route}", status=404)

    def do_POST(self):  # noqa: N802 - 基类约定
        route = urllib.parse.urlparse(self.path).path
        try:
            payload = self._read_json_body()
        except ValueError as error:
            return self._send_error_json(str(error), status=400)

        try:
            if route == "/api/generate":
                return self._handle_generate(payload)
            if route == "/api/grade":
                return self._handle_grade(payload)
        except ValueError as error:
            return self._send_error_json(str(error), status=400)
        except ParseError as error:
            return self._send_error_json(f"解析失败: {error}", status=400)
        except Exception as error:  # pragma: no cover - 兜底, 避免服务崩溃
            return self._send_error_json(f"服务端异常: {error}", status=500)

        return self._send_error_json(f"未知路径: {route}", status=404)

    def _serve_static(self, relative_path: str) -> None:
        safe_path = os.path.normpath(os.path.join(WEB_DIR, relative_path))
        if not safe_path.startswith(WEB_DIR) or not os.path.isfile(safe_path):
            return self._send_error_json(f"资源不存在: {relative_path}", status=404)

        extension = os.path.splitext(safe_path)[1].lower()
        with open(safe_path, "rb") as handle:
            body = handle.read()
        self._send_bytes(body, CONTENT_TYPES.get(extension, "application/octet-stream"))

    def _handle_generate(self, payload: dict) -> None:
        """生成题目: 返回题目与答案文本、统计信息, 并写入 output 目录。"""
        count = int(payload.get("n", 10))
        value_range = int(payload.get("r", 10))
        seed = payload.get("seed")
        max_operators = int(payload.get("maxOperators", MAX_OPERATORS))

        if count < 1:
            raise ValueError("题目数量 -n 必须是不小于 1 的自然数")
        if count > 200000:
            raise ValueError("题目数量过大 (上限 200000)")
        if value_range < 1:
            raise ValueError("数值范围 -r 必须是不小于 1 的自然数")
        if not 1 <= max_operators <= MAX_OPERATORS:
            raise ValueError(f"运算符个数必须在 1~{MAX_OPERATORS} 之间")

        rng = random.Random(int(seed)) if seed not in (None, "") else random.Random()

        started = time.perf_counter()
        problem_set = ProblemGenerator(value_range, rng=rng,
                                       max_operators=max_operators).generate(count)
        elapsed = time.perf_counter() - started

        exercise_lines = problem_set.exercise_lines()
        answer_lines = problem_set.answer_lines()
        exercise_path, answer_path = write_problem_files(
            OUTPUT_DIR, exercise_lines, answer_lines
        )

        # 大数量时只回传前若干题给浏览器渲染, 避免页面卡顿
        preview_limit = 300
        problems = [problem.to_dict() for problem in problem_set.problems[:preview_limit]]

        self._send_json({
            "stats": problem_set.summarize(),
            "problems": problems,
            "previewLimit": preview_limit,
            "elapsed": round(elapsed, 4),
            "exerciseText": "\n".join(exercise_lines),
            "answerText": "\n".join(answer_lines),
            "files": {
                "exercise": exercise_path,
                "answer": answer_path,
                "exerciseName": EXERCISE_FILENAME,
                "answerName": ANSWER_FILENAME,
            },
        })

    def _handle_grade(self, payload: dict) -> None:
        """批改答案: 返回对错统计、明细与 Grade.txt 内容。"""
        raw_exercise = payload.get("exercise", "")
        raw_answer = payload.get("answer", "")

        if isinstance(raw_exercise, list):
            exercise_lines = [str(item).strip() for item in raw_exercise if str(item).strip()]
        else:
            exercise_lines = _split_lines(raw_exercise)

        if isinstance(raw_answer, list):
            answer_lines = [str(item).strip() for item in raw_answer]
        else:
            answer_lines = [line.strip() for line in (raw_answer or "").splitlines()]

        if not exercise_lines:
            raise ValueError("题目内容为空, 请先生成题目或粘贴题目文本")

        result = grade(exercise_lines, answer_lines)
        grade_text = result.to_grade_text()
        grade_path = write_grade_file(OUTPUT_DIR, grade_text)

        self._send_json({
            "result": result.to_dict(),
            "gradeText": grade_text,
            "file": grade_path,
            "gradeName": GRADE_FILENAME,
        })

    def _list_output_files(self) -> None:
        files = []
        for name in (EXERCISE_FILENAME, ANSWER_FILENAME, GRADE_FILENAME):
            path = os.path.join(OUTPUT_DIR, name)
            if os.path.isfile(path):
                files.append({
                    "name": name,
                    "size": os.path.getsize(path),
                    "modified": time.strftime("%Y-%m-%d %H:%M:%S",
                                              time.localtime(os.path.getmtime(path))),
                })
        self._send_json({"files": files})

    def _download(self, name: str) -> None:
        if name not in ALLOWED_DOWNLOADS:
            return self._send_error_json("只允许下载 Exercises.txt / Answers.txt / Grade.txt", 400)
        path = os.path.join(OUTPUT_DIR, name)
        if not os.path.isfile(path):
            return self._send_error_json(f"文件尚未生成: {name}", 404)
        with open(path, "rb") as handle:
            body = handle.read()
        self._send_bytes(
            body,
            "text/plain; charset=utf-8",
            extra_headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )


def create_server(host: str, port: int) -> ThreadingHTTPServer:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    return ThreadingHTTPServer((host, port), ApiHandler)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="server.py",
        description="小学四则运算题目生成器 Web 后端 (纯标准库实现)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="监听地址, 默认 127.0.0.1")
    parser.add_argument("--port", type=int, default=8000, help="监听端口, 默认 8000")
    parser.add_argument("--open", action="store_true", help="启动后自动打开浏览器")
    args = parser.parse_args(argv)

    try:
        httpd = create_server(args.host, args.port)
    except OSError as error:
        print(f"启动失败: 端口 {args.port} 可能已被占用 ({error})", file=sys.stderr)
        print("可以换一个端口重试, 例如: python server.py --port 8010", file=sys.stderr)
        return 1

    url = f"http://{args.host}:{args.port}/"
    print("=" * 62)
    print("  小学四则运算题目生成器 - 后端服务已启动")
    print(f"  访问地址: {url}")
    print(f"  输出目录: {OUTPUT_DIR}")
    print("  按 Ctrl+C 停止服务")
    print("=" * 62)

    if args.open:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止。")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
