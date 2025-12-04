# 🎧 Alesha: YouTube Live Chat Translator Bot 🤖

**Alesha** is a Python-based bot that reads messages from a YouTube Live Chat, detects the language, translates them to Russian, and responds with an AI-generated message in **both the original language and Russian**.

---

## ✨ Features

- 🚘 Automatically connects to your **current YouTube live stream**
- 🌍 Translates any **non-Russian** messages to Russian
- 🤖 Responds using **OpenAI GPT-based AI**
- ⟲ Replies in **original language** + **Russian**
- 🧐 Detects message language using `langdetect`
- 🗣️ Uses **DeepL API** for high-quality translations
- 🔐 API keys and credentials are securely managed

---

## 📂 Project Structure

```
Alesha/
├── alesha.py               # Main bot logic
├── auth.py                 # Handles YouTube OAuth2 authentication
├── get_live_chat_id.py     # Fetches live stream and live chat ID
├── run_alesha.sh           # Bash script to automate startup
├── config.json             # Stores keys (ignored by git)
├── client_secret.json      # YouTube client credentials (ignored by git)
├── token.json              # OAuth2 token (generated after auth, ignored)
├── test_ai_response.py     # Unit test for AI response function
├── .gitignore              # Git ignore rules
└── README.md               # Project description (this file)
```

---

## ⚙️ Requirements

- Python 3.10+  
- Virtual Environment (recommended)
- YouTube Data API access + OAuth credentials
- DeepL API Key
- OpenAI API Key

---

## 🔐 Setup & Configuration

### 1. Clone the repo:
```bash
git clone git@github.com:janebautina/Alesha.git
cd Alesha
```

### 2. Set up virtual environment:
```bash
python3 -m venv yt_env
source yt_env/bin/activate
```

### 3. Install dependencies:
```bash
pip install -r requirements.txt
```

### 4. Add your credentials:

Create a `config.json` file with this structure (do **not** commit it):
```json
{
  "DEEPL_API_KEY": "your_deepl_api_key_here",
  "OPENAI_API_KEY": "your_openai_api_key_here",
  "TOKEN_FILE": "token.json",
  "YOUTUBE_CLIENT_SECRET": "client_secret...",
  "YOUTUBE_API_KEY": "AzaSy...",
  "SUPABASE_URL": "https://your-project.com",
  "SUPABASE_KEY": "your-anon-or-service-role-key"

}
```

Place your YouTube OAuth2 credentials in `client_secret.json`.

---

## 🚀 Running the Bot

Use the bash script to:
- Authenticate with YouTube
- Fetch live chat ID
- Start the bot

```bash
./run_alesha.sh
```

## 🖥️ Run the Frontend UI

Navigate to the web directory and start the development server:

```bash
cd web
npm install
npm run dev
```

Then open your browser and go to `http://localhost:3000`

## 🔌 Start the WebSocket Server (if not embedded)

Run the WebSocket server to handle real-time message broadcasting:

```bash
python3 ws_server.py
```

Runs on `ws://localhost:8765`

Frontend connects here to receive messages

---


## 🦪 Running Tests

### Test AI Response Function
Test your AI response function (without needing a real YouTube stream):
```bash
python3 test_ai_response.py
```

### Test Database Connection
Test your Supabase database connection:
```bash
python3 test_supabase_standalone.py
```

**Note:** Make sure you have created the `messages` table in your Supabase database first. Run this SQL in your Supabase SQL editor:

```sql
create table if not exists messages (
  id serial primary key,
  message_id text unique not null,
  author text not null,
  content text not null,
  language text,
  timestamp double precision not null,
  platform text default 'youtube',
  created_at timestamp with time zone default now()
);
```

---

## 🔒 Security Notice

The following files are **ignored by Git** and should never be committed:

- `config.json`
- `client_secret.json`
- `token.json`
- `yt_env/`

---

## 📌 TODO / Ideas

- [ ] Highlight replies in chat with color or formatting
- [ ] Log translations and responses to a file
- [ ] Dockerize the setup
- [ ] Add Twitch support
- [ ] Deploy to cloud (e.g., Heroku, GCP)

---

## Progress

- [x] YouTube Live Chat integration
- [x] Alesha persona + AI ответы
- [x] Supabase: messages table
- [x] WebSocket server for frontend
- [x] Safe YouTube message length (no more cut-off messages 💬)
- [ ] Поддержка нескольких стримеров через Telegram-бота
- [ ] UI-панель в вебе для просмотра сообщений / статистики
## 🙌 Contributing

---

Contributions and ideas welcome!  
Open an issue or create a pull request.

---

## 📄 License

MIT License © [janebautina](https://github.com/janebautina)