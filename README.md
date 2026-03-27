# W-RAY — Bitcoin Wallet Generator & Recovery Tool
```
 ██╗    ██╗      ██████╗  █████╗ ██╗   ██╗
 ██║    ██║      ██╔══██╗██╔══██╗╚██╗ ██╔╝
 ██║ █╗ ██║█████╗██████╔╝███████║ ╚████╔╝ 
 ██║███╗██║╚════╝██╔══██╗██╔══██║  ╚██╔╝  
 ╚███╔███╔╝      ██║  ██║██║  ██║   ██║   
  ╚══╝╚══╝       ╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   
```
![Python](https://img.shields.io/badge/Python-3.7%2B-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)
![Status](https://img.shields.io/badge/Project-Active-success)
![Security](https://img.shields.io/badge/Security-Audit%20Recommended-orange)

**Advanced Bitcoin Wallet Generation and Recovery Tool with Passphrase Attack Engine**

Created by jino99 — v3.0

---

## ⚠️ LEGAL DISCLAIMER

**This tool is provided for EDUCATIONAL and RESEARCH purposes ONLY.**

- Using this tool to access Bitcoin wallets that do not belong to you is **ILLEGAL**
- The probability of randomly finding a wallet with balance is **astronomically low**
- This tool is intended for:
  - Learning about Bitcoin wallet generation
  - Testing wallet recovery mechanisms
  - Understanding BIP39 and HD wallet derivation
  - Security research and education

**By using this tool, you agree to use it legally and ethically.**

See `Legal Disclaimer.txt` for complete terms.

---

## 🚀 Features

### Core
- ✅ BIP39 Mnemonic Generation (12/24 word seed phrases)
- ✅ HD Wallet Derivation (BIP44/49/84)
- ✅ All Address Types — Legacy (`1...`), P2SH (`3...`), Native SegWit (`bc1...`)
- ✅ Full BIP39 passphrase (13th word) support
- ✅ Online balance checking via multiple APIs with async fallback

### Advanced
- 🔥 **Multiprocessing DB Search** — each worker runs its own SQLite reader, zero IPC bottleneck
- 🔥 **100M+ row database support** — SQLite WAL + mmap, no RAM loading, instant startup
- 🔥 **Passphrase Attack Engine** — common, pattern, hybrid, custom wordlist strategies
- 🔥 **Target Address Attack** — bruteforce a specific address with known seed
- 🔥 **Wallet Recovery** — derive all address types from any seed phrase

---

## 📋 Requirements

- **Python 3.7+**
- **OS:** Linux (recommended), macOS, Windows

| Package | Role | Required? |
|---------|------|-----------|
| `mnemonic` | BIP39 seed generation | ✅ Required |
| `coincurve` | Fast secp256k1 (~10x speedup) | Strongly recommended |
| `aiohttp` | Async balance API calls | Recommended |
| `requests` | Sync balance API fallback | Recommended |
| `rich` | Terminal UI (tables, panels) | Recommended |

---

## 🔧 Installation

```bash
git clone https://github.com/jino99/w-ray.git
cd w-ray
pip install -r requirements.txt
python w-ray.py
```

---

## 📖 Menu

```
[1] Generate Wallet & Check Balance
[2] Search BTC Wallet with Database        ← multiprocessing, 100M+ rows
[3] Advanced Passphrase Attack
[4] Target Specific Address Attack
[5] Recover Bitcoin Wallet
[6] Convert TXT/TSV to SQLite
[7] Database Statistics
[8] Passphrase Attack Settings
[9] Exit
```

---

## 🗂️ Database Setup

### Format
```
address<TAB>balance_in_satoshis
```

### Convert your flat file
1. Place `btc_database.txt` or `btc_database.tsv` in the working directory
2. Run option **[6]** — auto-detects separator, column layout, and header
3. The resulting `btc_database.db` is ready immediately — no RAM loading required

### Large databases (100M+ rows)
- Startup is **instant** — the tool connects to SQLite and reads nothing into RAM
- Each worker process opens its own read-only connection with 128 MB page cache and 4 GB mmap
- Lookups are O(log n) via the `address` primary key index

---

## 🔐 Passphrase Attack (Option 3)

Strategies tried per seed:
1. Common passwords + custom `passphrases.txt`
2. Numeric patterns (years, sequences)
3. Hybrids (seed word + suffix)

Customize via option **[8]**.

---

## 📁 Output Files

| File | Description |
|------|-------------|
| `found_wallets.txt` | Wallets matched in database |
| `gen_wallets.txt` | Generated wallets with online balance |
| `recovered_wallet.txt` | Recovery results |
| `btc_database.db` | SQLite database |

---

## 🔬 Technical Details

- BIP39 entropy: 128-bit (12 words) or 256-bit (24 words)
- Derivation paths: `m/44'/0'/0'/0/0` (Legacy), `m/49'/0'/0'/0/0` (P2SH), `m/84'/0'/0'/0/0` (SegWit)
- Crypto backend: `coincurve` (libsecp256k1) when available, pure-Python secp256k1 fallback
- DB: SQLite WAL mode, `PRAGMA mmap_size=4GB`, `PRAGMA cache_size=-128MB`, no full-table scans
- IPC: workers send **hits only** through pipes — pipe stays near-empty at all times

---

## 📊 Performance

| Operation | Speed |
|-----------|-------|
| Wallet generation (coincurve) | 500–2000/s per core |
| DB lookup (SQLite, 100M rows) | 50k–200k addr/s per worker |
| Online API balance check | 1–2/s (rate-limited) |

Option 2 scales linearly with CPU cores — each core runs a full generate+lookup pipeline independently.

---

## ⚖️ Ethical Use

- ✔ Recovery of your own wallets
- ✔ Education and research
- ❌ Unauthorized access to others' wallets
- ❌ Theft or any illegal activity

---

## 📄 License

MIT — see `LICENSE`.
