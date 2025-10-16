# Piano di Test Locale: Worker Node E2E

## Obiettivo

Verificare che l'intero flusso funziona end-to-end **in locale** prima del deployment pubblico:

1. ✅ Worker node si avvia correttamente
2. ✅ Clone e registrazione del nodo
3. ✅ Esecuzione di un task demo
4. ✅ Dashboard aggiornata in tempo reale
5. ✅ Cleanup automatico di task orfani
6. ✅ Recovery da errori di rete simulati

---

## Setup Locale

### Prerequisiti

```bash
# Python 3.11+
python3 --version

# Docker (per eseguire i task)
docker --version

# Git
git --version

# Accesso al repository (GITHUB_TOKEN)
echo $GITHUB_TOKEN  # Deve essere impostato
```

### Preparazione

```bash
# 1. Crea un repository di TEST (non il vero dgrid!)
cd /tmp
mkdir dgrid-test-repo
cd dgrid-test-repo
git init

# 2. Configura repository di test
git config user.email "test@local"
git config user.name "Test User"

# 3. Crea la struttura di directory
mkdir -p nodes tasks/{queue,in_progress,completed,failed}
touch tasks/{queue,in_progress,completed,failed}/.gitkeep

# 4. Primo commit
git add -A
git commit -m "Initial test repo structure"

# 5. Impostare remoto (locale)
# Per il test, usiamo il repository locale stesso come "remoto"
# Oppure, usa un vero repository GitHub privato per test
```

### Configurazione Worker per Test

```bash
# Prepara l'ambiente del worker
cd /Users/fab/GitHub/dgrid

# Installa dipendenze (se non già fatto)
pip install -r worker/requirements.txt

# Configura variabili d'ambiente per TEST
export GIT_REPO_URL="file:///tmp/dgrid-test-repo"  # Locale per test
export NODE_ID="test-worker-001"
export HEARTBEAT_INTERVAL="10"  # 10 secondi per test veloce
export TASK_CHECK_INTERVAL="5"   # 5 secondi per test veloce
export DOCKER_TIMEOUT="30"        # 30 secondi max per task demo
export LOG_LEVEL="DEBUG"

# Verifica config è valida
python3 -c "from worker.config import validate_config; validate_config()"
```

---

## Test 1: Avvio e Registrazione

### Passo 1a: Avvia il worker in DEBUG mode

```bash
cd /Users/fab/GitHub/dgrid
python3 worker/main.py &
WORKER_PID=$!
```

### Passo 1b: Verifica i log

```bash
# Attendi 3 secondi e controlla se il log mostra:
# - Clone riuscito
# - Registrazione nodo
# - Heartbeat inviato

tail -50 logs/worker.log | grep -E "Clone|Register|Heartbeat"
```

### Passo 1c: Verifica il repository di test

```bash
cd /tmp/dgrid-test-repo
git log --oneline  # Deve mostrare commit di registro nodo
cat nodes/test-worker-001.json  # Verifica spec del nodo
```

### Expected Output

```json
{
  "node_id": "test-worker-001",
  "cpu_cores": 4,
  "memory_gb": 8.5,
  "disk_gb": 50.0,
  "registered_at": "2025-10-16T10:30:45.123456+00:00",
  "last_heartbeat": "2025-10-16T10:30:45.987654+00:00"
}
```

✅ **Checkpoint 1: Worker registrato correttamente**

---

## Test 2: Task Submission e Validazione

### Passo 2a: Crea un task demo

```bash
cd /tmp/dgrid-test-repo

# Crea un task semplice: print "Hello from D-GRID"
cat > tasks/queue/demo-hello-001.json << 'EOF'
{
  "task_id": "demo-hello-001",
  "script": "echo 'Hello from D-GRID Worker'; echo 'PID: '$$; sleep 2; echo 'Complete'",
  "timeout_seconds": 30
}
EOF

# Committi e pusha
git add tasks/queue/demo-hello-001.json
git commit -m "Add demo task"
git push origin main
```

### Passo 2b: Il worker dovrebbe vederlo

```bash
# Controlla il log del worker per:
# - Find task
# - Execute task in Docker
# - Report result

tail -100 logs/worker.log | grep -E "find_task|execute_task|report_task"
```

### Expected Behavior

```
[DEBUG] find_task_to_run: Found task demo-hello-001.json
[DEBUG] Moving task to in_progress/test-worker-001-demo-hello-001.json
[DEBUG] execute_task: Running container for demo-hello-001
[DEBUG] Docker output: Hello from D-GRID Worker
[DEBUG] Docker output: PID: 12345
[DEBUG] Docker output: Complete
[DEBUG] Task exit code: 0
[DEBUG] report_task_result: Task completed successfully
[DEBUG] Moving task result to completed/
```

### Verifica Risultato

```bash
# Il file dovrebbe essere spostato a completed/
ls -la tasks/completed/
ls -la tasks/failed/  # Deve essere vuoto

# Controlla il file di risultato
cat tasks/completed/demo-hello-001-result.json
# Deve contenere: stdout, stderr, exit_code
```

✅ **Checkpoint 2: Task eseguito correttamente con output catturato**

---

## Test 3: Dashboard Generazione

### Passo 3a: Lancia lo script di dashboard

```bash
cd /tmp/dgrid-test-repo
python3 /Users/fab/GitHub/dgrid/.github/scripts/generate_dashboard.py
```

### Expected Output

```
======================================================================
🚀 D-GRID Mission Control Dashboard Generator
======================================================================

📍 Percorsi:
  Repo root: /tmp/dgrid-test-repo
  Nodes dir: /tmp/dgrid-test-repo/nodes
  Tasks dir: /tmp/dgrid-test-repo/tasks

1️⃣  Scansione dello stato dei nodi...
   ✓ Nodo 'test-worker-001': 🟢 ATTIVO (5 secondi fa)
   → 1 nodi totali

2️⃣  Pulizia task orfani...
   ✓ Nessun task orfano trovato

3️⃣  Conteggio task per stato...
  queue: 0 task
  in_progress: 0 task
  completed: 1 task
  failed: 0 task

4️⃣  Generazione HTML della dashboard...
5️⃣  Salvataggio dashboard...
   ✓ Dashboard salvata in /tmp/dgrid-test-repo/index.html

======================================================================
✅ Generazione dashboard completata con successo
======================================================================
```

### Passo 3b: Verifica il file HTML

```bash
# Apri il file in un browser
open /tmp/dgrid-test-repo/index.html

# Oppure ispeziona il contenuto
grep -o "🟢 ATTIVO" /tmp/dgrid-test-repo/index.html
grep -o "demo-hello-001" /tmp/dgrid-test-repo/index.html  # Oppure nel conteggio
```

✅ **Checkpoint 3: Dashboard generata con stato corretto**

---

## Test 4: Auto-Healing - Task Orfano

### Passo 4a: Simula una disconnessione

```bash
# KILL il worker (simula crash)
kill $WORKER_PID

# Crea un task bloccato (simula worker che aveva un task in esecuzione)
cd /tmp/dgrid-test-repo

cat > tasks/in_progress/test-worker-001-demo-stuck-001.json << 'EOF'
{
  "task_id": "demo-stuck-001",
  "script": "sleep 999",
  "timeout_seconds": 60
}
EOF

# Committi il task orfano
git add tasks/in_progress/test-worker-001-demo-stuck-001.json
git commit -m "Simulated orphaned task"
git push origin main

# Aggiorna il nodo come INATTIVO (modifica heartbeat in passato)
python3 << 'PYTHON'
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

node_file = Path("nodes/test-worker-001.json")
with open(node_file) as f:
    data = json.load(f)

# Metti il heartbeat a 10 minuti fa
past = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
data['last_heartbeat'] = past

with open(node_file, 'w') as f:
    json.dump(data, f, indent=2)

print(f"Updated heartbeat to: {past}")
PYTHON

git add nodes/test-worker-001.json
git commit -m "Simulate inactive worker"
git push origin main
```

### Passo 4b: Esegui il dashboard generator

```bash
python3 /Users/fab/GitHub/dgrid/.github/scripts/generate_dashboard.py
```

### Expected Behavior

Lo script dovrebbe:
1. Rilevare il nodo come INATTIVO (heartbeat > 5 min fa)
2. Trovare il task orfano `test-worker-001-demo-stuck-001.json`
3. Spostarlo con `git mv` da `in_progress/` a `queue/`
4. Committare e pushare il cambio

```
======================================================================
1️⃣  Scansione dello stato dei nodi...
   ✓ Nodo 'test-worker-001': 🔴 INATTIVO (10 minuti fa)
   → 1 nodi totali

2️⃣  Pulizia task orfani...
   ❗️ Task orfano: test-worker-001-demo-stuck-001.json
      Nodo 'test-worker-001' inattivo. Rimetto in coda...
      ✓ Rimosso in demo-stuck-001.json

✅ Cleanup completato: 1 task rimessi in coda
✓ Commit e push completati
```

### Passo 4c: Verifica il risultato

```bash
# Il file deve essere spostato a queue/
ls -la tasks/queue/
ls -la tasks/in_progress/  # Deve essere vuoto

cat tasks/queue/demo-stuck-001.json  # Deve essere il task orfano
```

✅ **Checkpoint 4: Auto-healing funziona - task orfano recuperato**

---

## Test 5: Ciclo Completo (Opzionale ma Consigliato)

### Passo 5a: Ricrea il worker

```bash
# Riavvia il worker con config aggiornata
# Questa volta avrà il task orfano da eseguire

export NODE_ID="test-worker-002"  # Nuovo nodo per distinguere
python3 worker/main.py &
WORKER_PID=$!

# Attendi 20 secondi per far girare il worker
sleep 20
```

### Passo 5b: Verifica che prende il task recuperato

```bash
tail -50 logs/worker.log | grep demo-stuck-001
# Deve mostrare che il task è stato trovato e eseguito
```

### Passo 5c: Genera di nuovo la dashboard

```bash
python3 /Users/fab/GitHub/dgrid/.github/scripts/generate_dashboard.py
```

### Expected Output

```
Statistics:
  - Nodi attivi: 1 (test-worker-002)
  - Nodi inattivi: 1 (test-worker-001)
  - Queue: 0
  - In progress: 0
  - Completed: 2 (demo-hello-001, demo-stuck-001)
  - Failed: 0
```

✅ **Checkpoint 5: Ciclo completo funziona**

---

## Checklist di Validazione

Stampare questa lista e spuntare man mano:

```
FASE 1: AVVIO
[ ] Worker si avvia senza errori
[ ] Repository clonato
[ ] Nodo registrato in nodes/
[ ] Primo heartbeat committato e pushato

FASE 2: ESECUZIONE TASK
[ ] Task riconosciuto dal worker
[ ] File spostato atomicamente a in_progress/
[ ] Container Docker eseguito
[ ] Output catturato (stdout, stderr, exit_code)
[ ] Risultato spostato a completed/
[ ] Cambio committato e pushato

FASE 3: DASHBOARD
[ ] Dashboard HTML generato
[ ] Stato nodi visualizzato (attivo/inattivo)
[ ] Conteggi task corretti
[ ] Timestamp aggiornato

FASE 4: AUTO-HEALING
[ ] Nodo simulato come inattivo
[ ] Task orfano rilevato
[ ] Task rimosso da in_progress/ con git mv
[ ] Task messo in queue/
[ ] Cleanup committato e pushato

FASE 5: CICLO COMPLETO (Opzionale)
[ ] Nuovo worker prende task da queue/
[ ] Task orfano eseguito con successo
[ ] Dashboard mostra: 2 completati, 0 in_progress

VALIDAZIONE FINALE
[ ] Nessun data loss
[ ] Nessun race condition
[ ] Nessun task duplicato
[ ] Nessun task perso
[ ] Tutto recuperabile da GitHub
```

---

## Comandi Utili per Debugging

### Ispezionare lo stato del repository

```bash
cd /tmp/dgrid-test-repo

# Lista tutti i file in tutti gli stati
find . -name "*.json" -not -path "./.git/*" | sort

# Conta task per stato
echo "Queue:"; ls tasks/queue/ | wc -l
echo "In Progress:"; ls tasks/in_progress/ | wc -l
echo "Completed:"; ls tasks/completed/ | wc -l
echo "Failed:"; ls tasks/failed/ | wc -l

# Visualizza il log di git
git log --oneline -20
```

### Ispezionare il worker

```bash
# Log del worker
tail -100 /Users/fab/GitHub/dgrid/logs/worker.log

# Verificare il PID del worker
ps aux | grep main.py | grep -v grep

# Kill il worker
kill $WORKER_PID

# Riavvia con DEBUG verboso
PYTHONUNBUFFERED=1 python3 worker/main.py 2>&1 | tee debug.log
```

### Cleanup dopo i test

```bash
# Ferma il worker
pkill -f "python3 worker/main.py"

# Pulisci il repo test
rm -rf /tmp/dgrid-test-repo

# Ricrea per il prossimo test
mkdir /tmp/dgrid-test-repo
cd /tmp/dgrid-test-repo
git init
# ... (vedi Setup Locale)
```

---

## Timeline Attesa

| Step | Tempo |
|------|-------|
| Test 1 (Avvio) | 1 min |
| Test 2 (Task) | 2 min |
| Test 3 (Dashboard) | 1 min |
| Test 4 (Auto-Healing) | 2 min |
| Test 5 (Ciclo Completo) | 3 min |
| **TOTALE** | **~10 min** |

---

## Conclusione

Se tutti i checkpoint passano ✅, sei pronto per:

1. **Docker Build** - Containerizzare il worker
2. **GitHub Setup** - Pushare il repo ufficiale e abilitare Pages
3. **🚀 LAUNCH** - Invitare i primi volontari

**Status:** 🟢🟢🟡⚪⚪ **80% → 90% TARGET**
