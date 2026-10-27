import os
import sys
from flask import Flask

app = Flask(__name__)

message = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("STATUS_MESSAGE", "OK")

@app.get("/")
def index():
    return message, 200, {"Content-Type": "text/plain"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
