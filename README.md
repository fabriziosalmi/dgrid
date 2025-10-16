# D-GRID: Decentralized Git-Relay Infrastructure for Distributed Tasks

> 🚀 **Operazione Blitz-Launch** - Usare Git come un database transazionale e di stato distribuito.

## 🎯 La Visione

D-GRID è un sistema decentralizzato e serverless dove:

- **Git è il database** - Lo stato di tutto il sistema (nodi, task, risultati) è tracciato su GitHub.
- **GitHub Pages è il dashboard** - Una dashboard pubblica e read-only dello stato dell'infrastruttura.
- **Worker Node autonomi** - Nodi Python in container Docker che si registrano, eseguono task e reportano risultati.
- **Zero dipendenze centralizzate** - Niente API centralizzate, niente database esterno, niente orchestratore.

## 🏗️ Architettura

```
┌─────────────────────────────────────────────────────────┐
│                  GitHub Repository                      │
│  (Single Source of Truth - stato distribuito)          │
├─────────────────────────────────────────────────────────┤
│  nodes/                  → Registro nodi attivi         │
│  tasks/queue/            → Task in attesa               │
│  tasks/in_progress/      → Task in esecuzione          │
│  tasks/completed/        → Task completati             │
│  tasks/failed/           → Task falliti                │
└─────────────────────────────────────────────────────────┘
         ↕ (Pull/Push via Git)
┌─────────────────────────────────────────────────────────┐
│         GitHub Pages (Dashboard di Stato)              │
│  (Read-only, aggiornato da GitHub Actions)            │
└─────────────────────────────────────────────────────────┘
         ↑ (Generato da)
┌─────────────────────────────────────────────────────────┐
│         GitHub Actions (Orchestrazione)                │
│  • Validazione task in ingresso                        │
│  • Generazione dashboard di stato                      │
└─────────────────────────────────────────────────────────┘
         ↑ (Triggerati da)
┌──────────┬──────────┬──────────┬──────────┐
│ Worker 1 │ Worker 2 │ Worker 3 │ Worker N │
│ (Python) │ (Python) │ (Python) │ (Python) │
│ (Docker) │ (Docker) │ (Docker) │ (Docker) │
└──────────┴──────────┴──────────┴──────────┘
```

## 🔧 Stack Tecnologico

| Componente | Tecnologia | Motivo |
|-----------|-----------|--------|
| **Worker Node** | Python 3.11 | Velocità di sviluppo, librerie mature |
| **Container** | Docker Alpine | Leggerissimo (~150MB), sicuro, incluso Python |
| **Coordinamento** | Git + GitHub | Single source of truth, decentralizzato, storico |
| **Dashboard** | GitHub Pages + HTML | Gratuito, integrato con GitHub |
| **CI/CD** | GitHub Actions | Gratuito, serverless, integrato |

## 🚀 Come Funziona

### 1. Worker Node Lifecycle

```
┌─────────────────────────────────────────────┐
│ Worker avvia (docker run)                  │
└──────────────┬──────────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────────┐
│ 1. Clone repo (o pull se esiste)            │
│ 2. Registrazione nodo: nodes/{id}.json      │
│ 3. Commit e push registrazione              │
└──────────────┬──────────────────────────────┘
               │
               ↓
        ┌──────────────┐
        │ LOOP INIZIO  │
        └──────────────┘
               │
        ┌──────┴──────┐
        │ Pull rebase │  (Sempre aggiornato)
        └──────┬──────┘
               │
        ┌──────┴────────────────────┐
        │ Task disponibile?         │
        └──────┬─────────────────────┘
               │
        ┌──────┴──────────────────────────────┐
        │                                     │
        │                                     │
    [SÌ]│                                     │[NO]
        │                                     │
        ↓                                     ↓
┌─────────────────┐              ┌──────────────────┐
│ git mv atomic   │              │ Invia heartbeat  │
│ queue→in_prog   │              │ Aggiorna node    │
│ (transazione!)  │              │ .last_heartbeat  │
└────────┬────────┘              └────────┬─────────┘
         │                                │
         ↓                                │
┌─────────────────┐                       │
│ Commit e push   │                       │
│ (1° che pushes  │                       │
│  vince!)        │                       │
└────────┬────────┘                       │
         │                                │
         ↓                                │
┌─────────────────┐                       │
│ Execute Docker  │                       │
│ container       │                       │
└────────┬────────┘                       │
         │                                │
         ↓                                │
┌─────────────────┐                       │
│ Report result   │                       │
│ completed/ o    │                       │
│ failed/         │                       │
└────────┬────────┘                       │
         │                                │
         │                    ┌───────────┘
         ↓                    ↓
        ┌──────────────────────────┐
        │ Sleep (PULL_INTERVAL)    │
        └──────────────┬───────────┘
                       │
                       └─ (torna a Pull)
```

### 2. Task Submission Flow

```
Fork/Clone → Crea file task in tasks/queue/ → PR →
Merge (validato) → GitHub Actions legge lo stato →
Worker node lo trova → Esecuzione → Risultato pushato
```

## 📋 Struttura Directory

```
d-grid/
├── .github/
│   └── workflows/
│       ├── process-task-pr.yml     # Validazione task in ingresso
│       └── update-gh-pages.yml     # Generazione dashboard
├── nodes/
│   └── {node_id}.json              # Stato di ogni nodo
├── tasks/
│   ├── queue/                      # Task in attesa
│   ├── in_progress/                # Task in esecuzione (acquisiti atomicamente)
│   ├── completed/                  # Task completati con successo
│   └── failed/                     # Task falliti
├── worker/
│   ├── main.py                     # Entry point
│   ├── config.py                   # Configurazione
│   ├── logger_config.py            # Logger unificato
│   ├── git_handler.py              # Operazioni Git
│   ├── state_manager.py            # Registrazione e heartbeat
│   ├── task_runner.py              # Esecuzione task
│   └── requirements.txt            # Dipendenze Python
├── .gitignore
├── Dockerfile                       # Build immagine worker
├── README.md                        # Istruzioni di lancio
└── progress.md                      # Questo file (tracciamento missione)
```

## 🎲 Formato Task

Un task è un file JSON in `tasks/queue/`:

```json
{
  "id": "task-001",
  "image": "python:3.11-alpine",
  "command": "python -c \"print('Hello, D-GRID!')\"",
  "created_at": "2025-10-16T10:00:00Z",
  "timeout": 3600,
  "submitted_by": "user@example.com"
}
```

Il risultato sarà in `tasks/completed/{node_id}-{task_name}.log`:

```json
{
  "task_id": "task-001",
  "node_id": "worker-001",
  "exit_code": 0,
  "stdout": "Hello, D-GRID!",
  "stderr": "",
  "timestamp": "2025-10-16T10:01:23Z",
  "status": "success"
}
```

## 🔐 Sicurezza (MVP)

**Nota:** Questa è una prima versione. Per produzione:
- [ ] Validazione e signing dei task
- [ ] Sandboxing più robusto dei container
- [ ] Rate limiting dei worker
- [ ] Quorum per operazioni critiche

## 🚀 Quick Start

### Per il Maintainer (Setup Iniziale)

```bash
# 1. Crea repo su GitHub
# 2. Clone localmente
git clone https://github.com/<user>/d-grid.git
cd d-grid

# 3. Abilita GitHub Pages (Settings → Pages → Source: gh-pages branch)
# 4. Abilita GitHub Actions (Settings → Actions)
# 5. Crea secrets se necessari (GIT_TOKEN per auth)
```

### Per i Worker Node (Lancio)

```bash
# Con Docker
docker run -d \
  -e NODE_ID=worker-001 \
  -e DGRID_REPO_URL=https://github.com/<user>/d-grid.git \
  -e GIT_TOKEN=ghp_... \
  -v /var/run/docker.sock:/var/run/docker.sock \
  <user>/d-grid-worker:latest

# O: Python locale (dev)
cd worker
pip install -r requirements.txt
python main.py
```

### Per Sottomettere un Task

```bash
# 1. Fork d-grid
# 2. Crea un file in tasks/queue/
cat > tasks/queue/my-task.json << 'EOF'
{
  "id": "my-task-001",
  "image": "python:3.11-alpine",
  "command": "echo 'Ciao dal task!' && python -c 'import sys; print(sys.version)'",
  "created_at": "2025-10-16T10:00:00Z",
  "timeout": 60,
  "submitted_by": "me@example.com"
}
EOF

# 3. Commit e push
git add tasks/queue/my-task.json
git commit -m "Add task: my-task-001"
git push origin main

# 4. Attendi che un worker lo raccolga
# 5. Verifica il risultato in tasks/completed/
```

## 📊 Dashboard

Disponibile su `https://<user>.github.io/d-grid/`

Mostra in real-time:
- 🟢 Nodi attivi (ultimo heartbeat)
- ⏳ Task in coda
- 🔄 Task in esecuzione
- ✅ Task completati
- ❌ Task falliti

## 🛣️ Roadmap

### Fase 1: ✅ Fondamenta
- Worker node core
- State manager
- Task runner

### Fase 2: 🚧 GitHub Actions & Dashboard
- Validazione task in ingresso
- Generazione dashboard
- GitHub Pages setup

### Fase 3: 🎯 Deployment
- Build e push Docker image
- README dettagliato
- Lancio pubblico

### Fase 4: 🔮 Post-Launch
- Test E2E
- Gestione dipendenze task
- Sistema di reputazione
- Gestione pulizia stato

## 🤝 Contribuire

Chiunque può lanciare un worker node! Basta:

```bash
docker run -e DGRID_REPO_URL=... -e NODE_ID=mynode -v /var/run/docker.sock:/var/run/docker.sock d-grid-worker
```

## 📝 License

MIT - Usa pure, fai esperimenti, crea il tuo D-GRID!

---

**Missione Status:** 🚀 **OPERAZIONE BLITZ-LAUNCH IN CORSO**

*La decentralizzazione inizia da qui.*
