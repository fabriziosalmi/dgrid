# D-GRID Task Format Specification

## Sicurezza First 🔒

Le task in D-GRID sono eseguite in container Docker **ultra-isolati**. Per prevenire abusi:

- ✅ **L'immagine Docker è FISSA:** Sempre `python:3.11-alpine` (immutabile)
- ✅ **La rete è DISABILITATA:** `--network=none`
- ✅ **Il filesystem è READ-ONLY:** Protetto da scritture
- ✅ **Nessun utente root:** Esecuzione come `uid=1000`
- ✅ **Timeout rigoroso:** Max 300 secondi (5 minuti)
- ✅ **Limiti di processo:** Max 10 processi per container
- ✅ **Output limitato:** Max 10KB stdout + stderr

**Non è possibile:**
- Personalizzare l'immagine Docker
- Accedere alla rete
- Modificare il filesystem
- Eseguire come root
- Lanciare daemon di mining crypto

---

## Formato Task (JSON)

Ogni task è un file JSON sottomesso nella directory `tasks/unapproved/`.
Il nome del file **non importa** (viene rinominato al merge).

### Campi Obbligatori

```json
{
  "task_id": "unique-task-identifier",
  "script": "shell command or multiline script",
  "timeout_seconds": 60
}
```

### Descrizione Campi

| Campo | Tipo | Required | Vincoli | Esempio |
|-------|------|----------|---------|---------|
| `task_id` | string | ✅ | Univoco. Alfanumerico + `-_`. Max 64 char. | `"compute-pi-001"` |
| `script` | string | ✅ | Comando shell valido per `sh -c`. Multiline OK. | `"python3 -c 'print(42)'"` |
| `timeout_seconds` | integer | ✅ | Tra 10 e 300 secondi (5 min max). | `60` |

---

## Esempi Validi

### Esempio 1: Task Python Semplice

```json
{
  "task_id": "compute-pi-001",
  "script": "python3 -c \"import math; print(f'Pi: {math.pi}')\"",
  "timeout_seconds": 30
}
```

### Esempio 2: Script Multi-riga

```json
{
  "task_id": "data-pipeline-002",
  "script": "python3 << 'EOF'\nimport json\ndata = {'items': [1, 2, 3]}\nprint(json.dumps(data))\nEOF",
  "timeout_seconds": 60
}
```

### Esempio 3: Calcolo Parallelo

```json
{
  "task_id": "parallel-compute-003",
  "script": "for i in 1 2 3 4 5; do (python3 -c \"print('Worker $i')\") & done; wait",
  "timeout_seconds": 120
}
```

---

## Limitazioni e Best Practice

### ✅ Cosa Funziona

- Python 3.11 con librerie standard
- Comandi shell (echo, grep, sort, cat, etc.)
- Calcoli computazionali (numpy-like con pure Python)
- Elaborazione testi
- Generazione di output (stdout)
- Background jobs con `&` e `wait`

### ❌ Cosa NON Funziona

- Accesso a file esterni (filesystem read-only)
- Chiamate di rete HTTP/TCP (network=none)
- Visualizzazione grafica (nessun display)
- Installazione pacchetti con `pip` (no internet)
- Daemon/servizi long-running (timeout 5 min max)
- Docker-in-Docker (no socket access)
- Su di Linux (Alpine Linux only - no glibc)

### Timeout

Il timeout **massimo** è **300 secondi (5 minuti)**. Se il comando impiega più tempo, viene terminato:

```json
{
  "task_id": "long-computation",
  "script": "python3 heavy_computation.py",
  "timeout_seconds": 300
}
```

**Attenzione:** Se timeout viene superato, il processo viene killato e l'exit code sarà -2.

---

## Risultati e Monitoraggio

### Posizione Risultati

Dopo l'esecuzione, il risultato sarà disponibile in:

```
tasks/completed/{NODE_ID}-{task_id}.json
```

oppure in caso di errore:

```
tasks/failed/{NODE_ID}-{task_id}.json
```

### Formato Risultato

```json
{
  "task_id": "compute-pi-001",
  "node_id": "worker-prod-01",
  "exit_code": 0,
  "stdout": "Pi: 3.141592653589793\n",
  "stderr": "",
  "timestamp": "2025-10-16T10:15:23Z",
  "status": "success"
}
```

### Codici di Exit

| Exit Code | Significato |
|-----------|-------------|
| `0` | ✅ Task eseguito con successo |
| `1-255` | ❌ Errore durante l'esecuzione (dipende dal comando) |
| `-1` | ❌ Errore interno (JSON malformato, file non trovato, etc.) |
| `-2` | ⏱️ Timeout superato (> timeout_seconds) |

---

## Processo di Sottomissione

1. **Crea il file JSON** seguendo il formato sopra.
2. **Crea una Pull Request** aggiungendo il file in `tasks/unapproved/`.
   - Puoi aggiungere SOLO 1 file per PR (requisito di sicurezza).
3. **Il workflow automatico verificherà:**
   - ✅ Esattamente un file JSON
   - ✅ Nome nel formato corretto
   - ✅ JSON valido (no parse errors)
   - ✅ Campi obbligatori presenti
   - ✅ Tipi di dato corretti
   - ✅ Valori entro i limiti (timeout: 10-300)
4. **Se il check passa:** La PR avrà una ✅ verde. Un maintainer potrà revieware il task.
5. **Il maintainer farà il merge:** Questo sposterà il file da `unapproved/` a `queue/`.
6. **Il prossimo worker disponibile eseguirà il task.**

---

## Sicurezza e Compliance

### Policy di Isolamento (Non Negoziabile)

1. **Container Isolation:** Ogni task in container isolato e monouso
2. **No Network:** Nessun accesso a rete, database, API esterne
3. **Read-Only Filesystem:** Impossibile modificare il sistema
4. **Resource Limits:** CPU 1 core, memoria 512MB, max 10 processi
5. **Timeout Enforcement:** Max 5 minuti per task
6. **Execution User:** Non-root (uid=1000)

### Red Flags - Task Rifiutati

Saranno automaticamente rifiutati:
- ❌ Task con timeout > 300s
- ❌ Task con timeout < 10s
- ❌ Task senza `task_id` o `script`
- ❌ JSON malformato
- ❌ `task_id` duplicati
- ❌ Più di 1 file per PR

---

## FAQ

### P: Posso usare librerie esterne (NumPy, Requests, etc.)?

**R:** No. Python:3.11-alpine contiene solo la stdlib. Proponi un PR per estendere l'immagine con pacchetti aggiuntivi.

### P: Posso scaricare file da internet?

**R:** No. Network è disabilitato (`--network=none`). Se serve dati, committa nel repo.

### P: Cosa succede se il timeout viene superato?

**R:** Il processo viene killato. Exit code: `-2`. Il risultato sarà comunque salvato in `tasks/failed/`.

### P: Posso modificare il filesystem?

**R:** No. Il filesystem del container è montato read-only. Qualsiasi tentativo di scrittura fallirà.

### P: Posso usare variabili d'ambiente?

**R:** No (MVP). Passa i parametri nel comando stesso o hardcoda i valori.

### P: Posso lanciare background jobs?

**R:** Sì! Usa `&` e assicurati di fare `wait` prima della fine dello script per attendere i job.

```json
{
  "task_id": "parallel-example",
  "script": "python3 task1.py & python3 task2.py & wait; echo 'Done'",
  "timeout_seconds": 120
}
```

---

**Last Updated:** 2025-10-16
**Version:** 1.0
**Status:** 🔒 Security-First Design
**Approval Path:** User Submit PR → Automation Validates → Human Reviews → Merge = Approval
