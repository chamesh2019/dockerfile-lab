import os

from flask import Flask

app = Flask(__name__)


@app.get("/")
def index():
    name = os.environ.get("GREETING_NAME", "world")
    return f"hello, {name}\n", 200, {"Content-Type": "text/plain; charset=utf-8"}


@app.get("/healthz")
def healthz():
    return "ok\n", 200, {"Content-Type": "text/plain; charset=utf-8"}
