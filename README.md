# 🧠 RAG Chat App

A **Retrieval-Augmented Generation (RAG)** powered chat application that allows users to upload files (PDF, text, etc.) and ask **contextual questions** about their content. Built as part of my learning journey in **AI, backend engineering, and full-stack development**, this project demonstrates how to combine **modern AI frameworks with solid backend architecture**.

---

## 🚀 Features

- 📂 **File Upload & Ingestion** – Users can upload files which are processed and stored in a vector database (FAISS).
- 🔍 **Context-Aware QA** – Uses RAG pipeline to fetch relevant chunks and generate accurate answers with LLMs.
- 🛠️ **Frontend** – Built with **React + TypeScript** for a clean and responsive interface.
- ⚡ **Backend** – **FastAPI** for APIs, document ingestion, and orchestrating retrieval/generation.
- 🧩 **LangChain Integration** – Chunking, embeddings, retrieval pipeline.
- 🐳 **Dockerized Deployment** – Portable and production-ready setup with Docker & docker-compose.
- 🔑 **Secure Config Management** – Environment variables via `.env` (ignored in git).
- 📊 **Extensible Architecture** – Can plug in other vector DBs (Pinecone, Weaviate, ChromaDB).

---

## 🏗️ Tech Stack

**Frontend**

- Next.js / React (TypeScript)
- Tailwind CSS (for styling)

**Backend**

- FastAPI (Python)
- LangChain
- FAISS (vector search)

**AI / LLM**

- OpenAI API (can swap with other LLM providers)
- Custom embeddings pipeline

**DevOps**

- Docker, docker-compose
- GitHub for version control

---

## 📂 Project Structure

```
rag-chat-app/
│── frontend/         # React + TypeScript frontend
│   ├── src/
│   ├── package.json
│   └── tsconfig.json
│
│── backend/          # FastAPI backend
│   ├── app/
│   │   ├── main.py           # Entry point
│   │   ├── routes/           # API endpoints
│   │   ├── services/         # RAG logic
│   │   └── utils/            # Helpers
│   ├── requirements.txt
│   └── Dockerfile
│
│── docker/           # Docker & compose configs
│── .gitignore
│── README.md
```

---

## ⚙️ Setup & Installation

### 1. Clone the repo

```bash
git clone https://github.com/sumer27feb/rag-chat-app.git
cd rag-chat-app
```

### 2. Frontend setup

```bash
cd frontend
npm install
npm run dev
```

### 3. Backend setup

```bash
cd backend
python -m venv venv
source venv/bin/activate   # on Linux/Mac
venv\Scripts\activate      # on Windows

pip install -r requirements.txt
uvicorn app.main:app --reload
```

---

## 🧪 Usage

1. Upload a PDF/text file through the UI.
2. The backend ingests the file, chunks it, and stores embeddings in FAISS.
3. Ask questions in the chat – the app retrieves relevant chunks and passes them to the LLM.
4. Get **context-aware answers** instantly.

---

## 📖 Roadmap

- [ ] Authentication with JWT
- [ ] Support for multiple users & sessions
- [ ] Add Redis caching layer
- [ ] Integrate Sentry for monitoring
- [ ] Extend to support images/audio in RAG
- [ ] Deploy on cloud (Render / Vercel / AWS)

---

## 🧑‍💻 About the Author

👋 Hi, I’m **Sumer Dev Singh** – a full-stack developer & 2025 CSE graduate.  
I love building **backend architectures, AI-powered applications, and experimenting with LLMs**.

- 🌐 [Portfolio](https://sumer-dev-singh-portfolio.vercel.app)
- 💻 [GitHub](https://github.com/sumer27feb)
- 💼 [LinkedIn](https://www.linkedin.com/in/sumer-dev-singh-35870a234)

---

## ⚠️ Disclaimer

This project is **work in progress** 🚧. Expect frequent updates and refactors.  
It’s primarily a **learning and showcase project**, but will evolve into a fully-fledged AI assistant over time.

---
