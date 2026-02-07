# FileToLink 🔗

## ⚡ Transform Files into Shareable Direct Links

**FileToLink** is a powerful and efficient application/bot (likely a Telegram Bot written in Python) designed to instantly convert files uploaded to Telegram into **permanent, direct download and streaming links**. This project is ideal for users looking to quickly share media, documents, or any other file type, leveraging Telegram's robust file storage capabilities to generate rapid-access links.
***

### Deploy in various Apps✔✨<br>
[![Deploy to Koyeb](https://www.koyeb.com/static/images/deploy/button.svg)](https://app.koyeb.com/deploy?type=git&repository=https://github.com/GouthamSER/FileToLink&branch=main)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/GouthamSER/FileToLink)
***
***

## ✨ Features

* **Direct Link Generation**: 🌐 Instantly convert uploaded files into a permanent HTTP/HTTPS **Direct Download Link**.
* **Streaming Support**: 🎥 Media files (video, audio) can be streamed directly in a web browser or media player using the generated link.
* **High-Speed Downloads**: 🚀 Leverage direct links for rapid file retrieval, bypassing Telegram client limitations.
* **Support for Large Files**: 💾 Supports files up to Telegram's current limit (e.g., 2GB or 4GB).
* **Cross-Platform Compatibility**: 📱💻 Supports traditional VPS deployment as well as mobile-based deployment via **Termux** (see installation below).

***

## 📂 Project Structure Analysis

Based on the nature of a File-to-Link bot, here is an analysis of the key files and folders and their likely purposes:

| File/Folder | Purpose |
| :--- | :--- |
| `bot.py` | The main execution file containing the bot's core logic, message handlers, and the function for generating links. |
| `info.py`| Stores configuration variables such as API keys, bot tokens, and database credentials. **Do not commit sensitive data to the repository.** ⚠️ |
| `requirements.txt` | Lists all necessary Python libraries (e.g., `pyrogram`, `pymongo`, `aiohttp`) required to run the bot. |
| `database/` | A directory containing scripts for database interaction, including setting up MongoDB, user management, and file indexing functions. |
| `plugins/` | A directory for modular features and additional commands like `/stats`, `/broadcast`, or filters. |
| `Procfile` / `Dockerfile` | Configuration files for deployment on platforms like Heroku, Railway, or Docker, specifying the command to start the bot. |

***

## ⚙️ Getting Started

### Prerequisites

To run this project, you will typically need:

* A **Telegram Account** 👤
* **Python 3.10+** installed or new version of python 🐍
* A **MongoDB** database (for persistent storage and indexing) 🧭

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/GouthamSER/FileToLink
    cd FileToLink
    ```
2.  **Install dependencies:**
    ```bash
    pip3 install -r requirements.txt
    pip install -r requirements.txt --break-system-packages
    ```
3.  **Set up configuration** (see next section).
4.  **Run the bot:**
    ```bash
    python3 bot.py
    ```

***

## 🔑 Configuration (Environment Variables)

You must set the following environment variables. It is best practice to use a `info.py` file for local development or set them directly on your hosting platform.

| Variable | Description | Source |
| :--- | :--- | :--- |
| `BOT_TOKEN` | Your Telegram Bot Token obtained from **@BotFather**. | **Required** |
| `API_ID` | Your Telegram API ID from **my.telegram.org**. | **Required** |
| `API_HASH` | Your Telegram API HASH from **my.telegram.org**. | **Required** |
| `LOG_CHANNEL` | ID of the private Telegram channel where the files are permanently stored. The bot **must be an admin** here. | **Required** |
| `DATABASE_URI` | MongoDB connection URI for indexing files and storing user data. | **Required** |
| `ADMINS` | A space-separated list of User IDs for bot administrators. | *Optional* |
| `LOG_CHANNEL` | ID of a channel for logging bot activity, errors, and status updates. | *Optional* |

***

## 🚀 Usage

Interact with the bot on Telegram to get started.

### User Commands

| Command | Description |
| :--- | :--- |
| `/start` | Starts the bot and displays a welcome message. 👋 |
| **(Upload File)** | Simply forward or upload any file/media to the bot to instantly receive the direct link. 📤 |


### Admin Commands

| Command | Description |
| :--- | :--- |
| `/stats` | Get current bot statistics (e.g., total users, indexed file count). 📊 |
| `/broadcast` | Send a message to all users of the bot. 📢 |
| `/delete <reply>` | Delete a file from the database/index by replying to the file message in the bot's chat. 🗑️ |

***

## 🤝 Contributing

Contributions are welcome! Please feel free to open an issue or submit a pull request. 🛠️

---

## 📄 License

This project is typically licensed under the **GPL-2.0** or **Apache-2.0** license. Please include a `LICENSE` file in your repository for the official license information.

You can learn more about building this type of application by watching this tutorial: [DEMO BOT](https://www.youtube.com/shorts/iT440kJfuNc). ▶️
