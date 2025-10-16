# 📋 D-GRID Task Submission Guide

Questa guida ti insegna come sottomettere un task alla rete D-GRID decentralizzata.

---

## 🚀 Quick Start (5 minuti)

### 1. Crea il tuo file task

Crea un file `my-task.json` con questo formato:

```json
{
  "task_id": "my-first-task",
  "script": "echo 'Hello D-GRID!' && python3 -c \"print('Ready to compute')\"",
  "timeout_seconds": 30
}
```

### 2. Apri una Pull Request

1. **Fork** il repository `d-grid` su GitHub
2. **Crea un nuovo branch:**
   ```bash
   git checkout -b submit/my-first-task
   ```
3. **Aggiungi il file nella staging area:**
   ```bash
   mkdir -p tasks/unapproved
   cp my-task.json tasks/unapproved/
   git add tasks/unapproved/my-task.json
   git commit -m "Submit task: my-first-task"
   git push origin submit/my-first-task
   ```
4. **Apri una PR** verso `main` del repo principale

### 3. Attendi la Validazione Automatica

Il workflow `Validate Task Submission PR` partirà automaticamente. Verrà pubblicato un commento sulla PR con il risultato:

- ✅ **Se passa:** La validazione è superata. Un maintainer revisionerà e farà il merge.
- ❌ **Se fallisce:** Leggi l'errore, correggi il file, e ripushalo (la PR si aggiornerà automaticamente).

### 4. Merge = Approvazione

Quando un maintainer farà il **merge**, il tuo task sarà spostato da `tasks/unapproved/` a `tasks/queue/`.

### 5. Guarda il tuo task Eseguito

Tra pochi secondi, un worker node raccoglierà il task, lo eseguirà e il risultato sarà disponibile in:

```
tasks/completed/{NODE_ID}-{task_id}.json
```

---

## 📝 Schema Task Dettagliato

### Campi Obbligatori

| Campo | Tipo | Descrizione | Vincoli |
|-------|------|-------------|---------|
| `task_id` | string | Identificatore univoco del task | Alfanumerico + `-_`. Max 64 char. No spazi. |
| `script` | string | Comando/script shell da eseguire | Valido per `sh -c`. Max 5000 char. |
| `timeout_seconds` | integer | Tempo massimo di esecuzione | 10-300 secondi. **Massimo 5 minuti.** |

### Esempio Completo

```json
{
  "task_id": "data-processing-batch-001",
  "script": "python3 << 'EOF'\nimport json\ndata = {'items': list(range(100))}\nprint(json.dumps(data))\nEOF",
  "timeout_seconds": 60
}
```

---

## ✅ Linee Guida per il Task

### ✅ DO: Cosa Fare

- **Comandi semplici e self-contained** - Non dipendere da file esterni
- **Output su stdout** - Quello che vuoi vedere, stampa con `echo` o `print`
- **Timeouts realistici** - Stima il tempo, aggiungi 20% di margine
- **Python 3.11 stdlib** - Usa solo la libreria standard
- **Shell commands** - `sh` è il tuo shell, comandi comuni vanno bene

### ✅ ESEMPI: Task che Funzionano

**Calcolo Matematico:**
```json
{
  "task_id": "fibonacci-50",
  "script": "python3 -c \"def fib(n): return 1 if n<=1 else fib(n-1)+fib(n-2); print(fib(50))\"",
  "timeout_seconds": 120
}
```

**Processamento Testo:**
```json
{
  "task_id": "text-stats",
  "script": "python3 << 'EOF'\ntext = 'Hello world hello D-GRID'\nwords = text.split()\nprint(f'Word count: {len(words)}')\nEOF",
  "timeout_seconds": 10
}
```

**Comandi Shell Paralleli:**
```json
{
  "task_id": "parallel-echo",
  "script": "for i in 1 2 3 4 5; do (echo \"Task $i\" && sleep 0.1) & done; wait; echo 'All done'",
  "timeout_seconds": 30
}
```

### ❌ DON'T: Cosa NON Fare

- ❌ Assumere file nel filesystem (read-only)
- ❌ Fare richieste HTTP/rete (network=none)
- ❌ Installare pacchetti con `pip` (no internet)
- ❌ Lanciare GUI (no display)
- ❌ Task con timeout > 300s
- ❌ Docker-in-Docker
- ❌ Accesso al socket Docker host
- ❌ Esecuzione come root

### ❌ ESEMPI: Task che Falliscono

**Richiesta di Rete (FAIL):**
```json
{
  "task_id": "bad-network",
  "script": "curl https://example.com",
  "timeout_seconds": 30
}
```
→ ❌ Network disabilitato. Il curl fallirà.

**Installazione pip (FAIL):**
```json
{
  "task_id": "bad-pip",
  "script": "pip install numpy && python3 -c \"import numpy; print(numpy.pi)\"",
  "timeout_seconds": 60
}
```
→ ❌ No internet. pip fallirà.

**Timeout troppo lungo (FAIL):**
```json
{
  "task_id": "bad-timeout",
  "script": "sleep 1000",
  "timeout_seconds": 9999
}
```
→ ❌ timeout_seconds > 300. Validazione fallisce in PR.

---

## 🔍 Validazione Automatica

Il workflow `process-task-pr.yml` esegue questi controlli **in ordine**:

### 1️⃣ Structural Validation
- ✅ Esattamente 1 file nella PR
- ✅ File in `tasks/unapproved/`
- ✅ Estensione `.json`

### 2️⃣ JSON Schema Validation
- ✅ JSON valido (no parse errors)
- ✅ Campo `task_id` presente e non vuoto (max 64 char, alfanumerico + `-_`)
- ✅ Campo `script` presente e non vuoto (max 5000 char)
- ✅ Campo `timeout_seconds` presente e intero (10-300)

### 3️⃣ Commento Automatico
- Se ✅: Un commento verde ti dice che la validazione è passata
- Se ❌: Un commento rosso ti spiega quale controllo è fallito

---

## 📊 Monitoraggio Risultati

### Dashboard di Stato

Visita: https://{user}.github.io/d-grid/

Vedrai in real-time:
- 🟢 Nodi attivi
- ⏳ Task in coda
- 🔄 Task in esecuzione
- ✅ Task completati
- ❌ Task falliti

### File di Risultato

Dopo l'esecuzione, il tuo risultato sarà in:

**Se successo (exit_code=0):**
```
tasks/completed/worker-XYZ-my-first-task.json
```

**Se fallisce (exit_code≠0):**
```
tasks/failed/worker-XYZ-my-first-task.json
```

**Formato Risultato:**
```json
{
  "task_id": "my-first-task",
  "node_id": "worker-prod-01",
  "exit_code": 0,
  "stdout": "Hello D-GRID!\nReady to compute\n",
  "stderr": "",
  "timestamp": "2025-10-16T10:15:23Z",
  "status": "success"
}
```

---

## 🆘 Troubleshooting

### Il mio task è stato validato ma non eseguito

**Possibile causa:** Nessun worker disponibile.
**Soluzione:** I worker node eseguono task in ordine FIFO. Se la coda è lunga, attendi. Se nessun worker è attivo, il task rimarrà in coda indefinitamente.

### La validazione fallisce con "timeout_seconds non è un intero"

**Possibile causa:** Lo hai messo come stringa anziché numero.
```json
// ❌ SBAGLIATO
{
  "timeout_seconds": "30"
}

// ✅ GIUSTO
{
  "timeout_seconds": 30
}
```

### Il mio script funziona localmente ma fallisce nel task

**Possibili cause:**
1. **Dipendenze non incluse** - Alpine Linux non ha tutte le librerie. Usa la stdlib.
2. **Percorsi file hardcoded** - Il filesystem è read-only. Passa i parametri nel comando.
3. **Assunzioni sulla rete** - Network è disabilitato. Non puoi fare HTTP.

**Soluzione:** Testa il comando in un container locale:
```bash
docker run --rm --network=none --read-only --user=1000:1000 python:3.11-alpine sh -c "TUO_COMANDO_QUI"
```

### Exit code -2: Timeout

Il tuo script ha superato `timeout_seconds`.

**Soluzione:** Aumenta il timeout (max 300) o ottimizza lo script.

---

## 🎯 Caso d'Uso: Batch Processing

Vuoi eseguire una serie di calcoli? Submitta più task:

**Task 1:**
```json
{
  "task_id": "batch-part-1",
  "script": "python3 -c \"print('Processing items 1-1000')\"",
  "timeout_seconds": 120
}
```

**Task 2:**
```json
{
  "task_id": "batch-part-2",
  "script": "python3 -c \"print('Processing items 1001-2000')\"",
  "timeout_seconds": 120
}
```

Saranno distribuiti tra i worker node disponibili e eseguiti in parallelo.

---

## 📞 Supporto

- 📖 **Documentazione:** Leggi `TASK_FORMAT.md` per dettagli tecnici
- 🐛 **Bug/Problemi:** Apri un issue su GitHub
- 💬 **Discussioni:** Usa Discussions su GitHub

---

**Buon computing!** 🚀

*D-GRID - Decentralized Git-Relay Infrastructure for Distributed Tasks*
