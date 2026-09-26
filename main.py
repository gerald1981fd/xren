import os

from flask import *
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

app = Flask(__name__)

SUPABASE_URL = os.getenv("DB_LINK")
SUPABASE_KEY = os.getenv("DB_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY має бути в .env")

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


@app.route("/")
def home():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)
