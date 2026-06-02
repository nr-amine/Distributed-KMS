# Shamir's Secret Sharing — Distributed KMS

A distributed Key Management System (KMS) built as an L2 Math-CS project. It splits a 256-bit AES key into multiple shares using **Shamir's Secret Sharing**, with a lightweight C math engine and an async Python/FastAPI network layer.

---

## Overview

The goal was to build something that actually connected my two majors. The math is real (finite field arithmetic, Lagrange interpolation), and the system is fault-tolerant: any **2 out of 3 nodes** can reconstruct the original key, even if the third goes offline.

---

## How It Works

### 1. The `P = 257` Trick — Avoiding Big Integers

Standard Shamir's Secret Sharing requires a prime `P` strictly greater than the secret. For a full 256-bit key, that means dealing with enormous integers, usually through libraries like GMP.

Instead, I chunked the AES key into **32 individual bytes** (each in the range `[0, 255]`), then applied SSS to each byte independently over the finite field **GF(257)**. Since `257` is prime and greater than `255`, all arithmetic stays within standard 32-bit C `int` range — no external dependencies, no big integer overhead.

### 2. C Engine + Python Bindings (`ctypes`)

The finite field math (modular arithmetic, modular inverses, Lagrange interpolation) is implemented in C for performance. Python talks to it via `ctypes`.

An early bottleneck was crossing the Python/C boundary 32 times per key (once per byte). I fixed this by exposing a **batch processing function** in C: Python passes the full byte array as a single pointer, C handles everything in one call, and returns the result array. Much faster.

### 3. Async Node Architecture

The orchestrator distributes shares to 3 storage nodes concurrently using `asyncio` and `httpx`. If a node is unreachable, the exception is caught and reconstruction proceeds with the remaining two shares.

Each node stores its share in a local SQLite database via SQLAlchemy.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Math engine | C (pure, no external deps) |
| Python bindings | `ctypes` |
| API framework | FastAPI |
| Async HTTP | `httpx` + `asyncio` |
| Storage | SQLAlchemy + SQLite |

---

## Running Locally

### 1. Compile the C Engine

From the project root:

**Linux / macOS:**
```bash
gcc -shared -fPIC -o Engine.so Engine.c -O2
```

**Windows:**
```bash
gcc -shared -o Engine.dll Engine.c -O2 -s
```

---

### 2. Start the 3 Storage Nodes

Open 3 separate terminals:

**Terminal 1 — Paris Node:**
```bash
export DATABASE_URL="sqlite:///./paris.db"
uvicorn secret_guard:app --port 8001
```

**Terminal 2 — Mariana Node:**
```bash
export DATABASE_URL="sqlite:///./mariana.db"
uvicorn secret_guard:app --port 8002
```

**Terminal 3 — Moon Base Node:**
```bash
export DATABASE_URL="sqlite:///./moon.db"
uvicorn secret_guard:app --port 8003
```

> **Windows (PowerShell):** Replace `export KEY="value"` with `$env:KEY="value"`

---

### 3. Start the Orchestrator

In a 4th terminal:
```bash
uvicorn main_orchestrator:app --port 8000
```

---

## API Usage

### Split and distribute a key

```bash
curl -X POST http://127.0.0.1:8000/create_secret \
  -H "Content-Type: application/json" \
  -d '{"id": "my-key", "secret": "00112233445566778899aabbccddeeff"}'
```

You should see all 3 node terminals receive their share.

### Reconstruct the key

```bash
curl "http://127.0.0.1:8000/reconstruct_secret?secret_id=my-key"
```

Returns the original hex string.

### Test fault tolerance

Kill Terminal 3 (`Ctrl+C`), then run the reconstruct command again. It still works — 2 nodes are enough.

---

## Project Context

This is a portfolio/passion-project. The mathematical foundation (Lagrange interpolation over a finite field) is covered in the L2 curriculum, the implementation challenge was making it run efficiently without heavyweight dependencies.
