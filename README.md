# 🧠 RAG Chat App

A **production-ready Retrieval-Augmented Generation (RAG)** chat system built with **FastAPI**, **React (Vite)**, **MongoDB**, **ChromaDB**, **Celery**, and **Redis**, containerized via **Docker Compose** and served through **Nginx** as a reverse proxy.

This project is structured and configured for seamless deployment on any Linux-based server (VPS, cloud instance, or local environment), following industry-standard practices.

---

## ⚙️ Tech Stack

| Layer                | Technology                  | Description                                                |
| -------------------- | --------------------------- | ---------------------------------------------------------- |
| **Frontend**         | React (Vite) + Tailwind CSS | Responsive client interface for chat interaction           |
| **Backend API**      | FastAPI                     | Handles user requests, vector retrieval, and LLM responses |
| **Task Queue**       | Celery + Redis              | Background processing for heavy or async operations        |
| **Vector DB**        | ChromaDB                    | Embedding and retrieval layer for RAG pipeline             |
| **Database**         | MongoDB                     | Persistent data storage (chat logs, users, metadata)       |
| **Reverse Proxy**    | Nginx                       | Routes incoming traffic to the correct services            |
| **Containerization** | Docker Compose              | Multi-service orchestration and environment isolation      |

---

## 🧩 System Architecture

                   ┌──────────────────────────────────────────────┐
                   │                    NGINX                     │
                   │         (Reverse Proxy + SSL Termination)    │
                   └──────────────┬───────────────────────────────┘
                                  │
                    ┌─────────────┴───────────────┐
                    │                             │
            ┌────────────────┐           ┌──────────────────┐
            │   Frontend     │           │     FastAPI      │
            │ (React + Vite) │           │  Backend + Celery│
            └────────────────┘           └─────────┬────────┘
                                                    │
                   ┌────────────────────────────────┼─────────────────────────┐
                   │                                │                         │
            ┌───────────────┐             ┌────────────────┐          ┌────────────────┐
            │   MongoDB     │             │     Redis       │          │   ChromaDB     │
            │ (Application  │             │ (Task Queue)    │          │ (Vector Store) │
            │   Data)       │             │                 │          │                │
            └───────────────┘             └────────────────┘          └────────────────┘

Each service runs as a separate container and communicates internally via a dedicated Docker network.  
Nginx exposes the app to the outside world on ports `80` and `443`.

---

## 🏗️ Project Structure

```
rag-chat-app/
├── client/ # React frontend (Vite)
│ ├── Dockerfile
│ └── dist/ # Production build output
│
├── server/ # FastAPI backend
│ ├── Dockerfile
│ ├── main.py
│ ├── celery_app.py
│ ├── requirements.txt
│ ├── .env.example
│ └── ...
│
├── nginx/
│ ├── nginx.conf # Reverse proxy config
│ └── ssl/ # Local development certs (optional)
│
├── docker-compose.yml # Multi-service orchestration
├── .env.example # Root env file (global vars)
└── README.md
```

---

## 🚀 Deployment

This app is designed to be **fully deployable out-of-the-box** using Docker Compose.

### 1. Clone the Repository

```bash
git clone https://github.com/sumer27feb/rag-chat-app.git
cd rag-chat-app
```

### 2. Configure Environment Variables

Copy example env files and adjust as needed:

```bash
cp server/.env.example server/.env
cp .env.example .env
```

Make sure to update database credentials, API keys, and secret keys if applicable.

---

### 3. Build and Start All Services

```bash
docker compose up -d --build
```

This will:

- Build and start the **frontend**, **backend**, **celery worker**, **Redis**, **MongoDB**, and **ChromaDB**
- Expose the frontend via Nginx on port `80` (HTTP)

Once built, the app will be available at:

```bash
Frontend: http://localhost/
API: http://localhost/api/
```

---

### 4. Persistent Volumes

All data and vector indices are persisted automatically through Docker volumes:

| Service  | Volume         | Description              |
| -------- | -------------- | ------------------------ |
| MongoDB  | `mongodb_data` | Database persistence     |
| ChromaDB | `chroma_data`  | Vector store persistence |

To remove all data (for a clean rebuild):

```bash
docker compose down -v
```

---

## 🌐 Production Server Setup (Linux VPS / Cloud)

For real-world deployment:

1. Install dependencies

```bash
sudo apt update
sudo apt install docker.io docker-compose -y
```

2. Clone and build

```bash
git clone https://github.com/sumer27feb/rag-chat-app.git
cd rag-chat-app
docker compose up -d --build
```

3. (Optional) Add your domain and SSL certs

```bash
Replace `nginx/ssl/myapp.local.crt` and `.key` with real certs, and update `nginx.conf`.
```

4. Access the app via your server IP or domain.

---

## 🧠 Development Workflow

- **Frontend:** Hot-reload via Vite dev server (`npm run dev`)
- **Backend:** Run FastAPI with Uvicorn (`uvicorn main:app --reload`)
- **Celery:** Run worker manually (`celery -A celery_app.celery worker --loglevel=info`)
- **Redis/Mongo/Chroma:** Automatically managed through Docker Compose

All services can be independently tested or debugged.

---

## 🧰 Common Commands

| Action                     | Command                                 |
| -------------------------- | --------------------------------------- |
| Build & run all containers | `docker compose up -d --build`          |
| View logs                  | `docker compose logs -f`                |
| Stop all containers        | `docker compose down`                   |
| Rebuild specific service   | `docker compose up -d --build server`   |
| Enter container shell      | `docker exec -it <container_name> bash` |

---

## 🧾 Notes

- Frontend served statically via **Nginx** (React build in `/usr/share/nginx/html`)
- Backend requests proxied under `/api/`
- **HTTPS** setup is optional for local and can be replaced by real certs in production
- No external cloud dependencies — runs fully self-contained via Docker network

---

## 🧩 Next Steps (Production Enhancements)

| Feature                         | Description                                                    |
| ------------------------------- | -------------------------------------------------------------- |
| 🔒 **SSL via Let’s Encrypt**    | Use `certbot` on VPS for automated certificate renewal         |
| 🐙 **CI/CD Pipeline**           | Add GitHub Actions or Docker Hub auto-builds                   |
| 📊 **Monitoring**               | Integrate Prometheus/Grafana or simple container healthchecks  |
| 🔑 **Auth Layer**               | Add JWT-based login or API key validation (if not present yet) |
| 🧠 **LLM Integration**          | Wire your FastAPI endpoints with OpenAI API / local model      |
| 🧰 **Logging & Error Handling** | Centralized logging using `uvicorn` + `Celery` logs            |

---

## 👨‍💻 Maintainer

**Sumer Dev Singh**  
Full-Stack Developer | AI + Backend Focused  
📍 Patna, Bihar (Remote Friendly)  
🔗 [Portfolio](https://sumer-dev-singh-portfolio.vercel.app)  
🐙 [GitHub](https://github.com/sumer27feb)  
💼 [LinkedIn](https://linkedin.com/in/sumer-dev-singh-35870a234)

---

> _“Deploy like a developer, structure like an engineer.”_  
> — RAG Chat App Infrastructure Philosophy
