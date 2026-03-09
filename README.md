# W-RAY - Bitcoin Wallet Generator & Recovery Tool
```
 ██╗    ██╗      ██████╗  █████╗ ██╗   ██╗
 ██║    ██║      ██╔══██╗██╔══██╗╚██╗ ██╔╝
 ██║ █╗ ██║█████╗██████╔╝███████║ ╚████╔╝ 
 ██║███╗██║╚════╝██╔══██╗██╔══██║  ╚██╔╝  
 ╚███╔███╔╝      ██║  ██║██║  ██║   ██║   
  ╚══╝╚══╝       ╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   
```

**Advanced Bitcoin Wallet Generation and Recovery Tool with Passphrase Attack Engine**

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

See `LEGAL_DISCLAIMER.txt` for complete terms.

---

## 🚀 Features

### Core Features
- ✅ **BIP39 Mnemonic Generation** - Generate standard 12/24 word seed phrases
- ✅ **HD Wallet Derivation** - BIP44 compliant address generation
- ✅ **Multiple Address Types** - Legacy (P2PKH), SegWit (Bech32), P2SH
- ✅ **Passphrase Support** - Full BIP39 passphrase (13th word) implementation
- ✅ **Balance Checking** - Online and offline balance verification

### Advanced Features
- 🔥 **Passphrase Attack Engine** - Test multiple passphrases per seed
- 🔥 **Database Search** - Fast offline address matching with SQLite
- 🔥 **Target Address Attack** - Bruteforce specific Bitcoin addresses
- 🔥 **Wallet Recovery** - Restore wallets from seed phrases
- 🔥 **Smart Passphrase Generation** - Common passwords, patterns, hybrids

### Search Strategies
1. **Common Passphrases** - passwords, years, bitcoin-related terms
2. **Pattern Generation** - numbers, dates, combinations
3. **Hybrid Combinations** - word+number variations
4. **Custom Wordlists** - User-provided passphrase lists

---

## 📋 Requirements

- **Python 3.7+**
- **Operating System**: Windows, Linux, macOS
- **Dependencies**:
  - `mnemonic` - BIP39 implementation
  - `bitcoinlib` - Bitcoin key and address generation
  - `requests` - Online balance checking (optional)
  - `sqlite3` - Database management (included in Python)

---

## 🔧 Installation

### 1. Clone or Download
```bash
git clone https://github.com/yourusername/wray.git
cd w-ray
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

Or manually:
```bash
pip install mnemonic bitcoinlib requests
```

### 3. Run the Program
```bash
python w-ray.py
```

On Linux/Mac:
```bash
chmod +x w-ray.py
./w-ray.py
```

---

## 📖 Usage

### Quick Start

1. **Run the program**: `python wray.py`
2. **Choose an option** from the menu (1-9)
3. **Follow the prompts**

### Main Menu Options
```
[1] Generate Wallet & Check Balance
    - Generate random wallets
    - Check balance online via blockchain APIs
    - Single or continuous mode

[2] Search BTC Wallet with Balance (Database)
    - Generate wallets and check against local database
    - Works offline, very fast
    - Requires database setup (option 6)

[3] Search with Advanced Passphrase Attack
    - Test multiple passphrases per seed phrase
    - Uses smart passphrase generation strategies
    - Configurable via option 8

[4] Target Specific Address Attack
    - Bruteforce a specific Bitcoin address
    - Multiple attack modes available

[5] Recovery Bitcoin Wallet
    - Recover wallet from existing seed phrase
    - Supports optional passphrase

[6] Convert TXT/TSV to SQLite Database
    - Import Bitcoin address database
    - Smart format detection
    - Required for offline searching

[7] Database Statistics
    - View database information

[8] Passphrase Attack Settings
    - Configure attack parameters

[9] Exit
```

---

## 🗂️ Database Setup

### Option A: Use Existing Database Dump

1. Download a Bitcoin address dump (various sources available online)
2. Place the file as `btc_database.txt` or `btc_database.tsv`
3. Run option `[6]` to convert to SQLite
4. Choose conversion mode (scan or direct)

### Option B: Create Custom Database

Create `btc_database.txt` with format:
```
address<TAB>balance_in_satoshis
```

Example:
```
1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa	5000000000
3J98t1WpEZ73CNmYviecrnyiWrnqRhWNLy	100000000
bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh	25000000
```

Then run option `[6]` to convert.

---

## 🔐 Passphrase Attack

### How It Works

The passphrase attack engine tests multiple passphrases for each generated seed phrase:

1. **Empty passphrase** (most common)
2. **Common passwords** (password123, bitcoin, etc.)
3. **Patterns** (years 1980-2025, numbers 1-999)
4. **Hybrid combinations** (bitcoin123, btc2024, etc.)

### Configuration

Use option `[8]` to configure:
- Max passphrases per seed (default: 100)
- Enable/disable strategies
- Load custom passphrase lists

### Custom Passphrase List

Create `passphrases.txt`:
```
mypassword123
bitcoin2024
secretphrase
MyWallet!
```

---

## 📁 Output Files

| File | Description |
|------|-------------|
| `found_wallets.txt` | Wallets found in database (options 2, 3, 4) |
| `gen_wallets.txt` | Wallets generated with online balance (option 1) |
| `recovered_wallet.txt` | Wallet recovered from seed (option 5) |
| `btc_database.db` | SQLite database of Bitcoin addresses |

---

## 💡 Tips & Best Practices

### Performance
- **Fastest**: Option [2] - Offline database search
- **Thorough**: Option [3] - With passphrase attack
- **Slowest**: Option [1] - Online API calls

### Success Probability
- Random wallet generation: **~0% chance** (1 in 2^256)
- This is primarily an **educational tool**
- Real-world use: wallet recovery with partial information

### Database
- Larger database = more addresses = more chances
- Use SSD for better performance
- Keep database up to date

### Security
- ⚠️ **Never share** your seed phrases or private keys
- ⚠️ **Backup** your own wallets properly
- ⚠️ Use this tool **responsibly and legally**

---

## 🛠️ Advanced Usage

### Running 24/7

Linux/Mac:
```bash
nohup python wray.py > output.log 2>&1 &
```

Using screen:
```bash
screen -S wray
python wray.py
# Detach: CTRL+A then D
# Reattach: screen -r wray
```

### Multiple Instances

Run multiple instances in parallel:
```bash
mkdir instance1 instance2 instance3
cp wray.py btc_database.db instance1/
cp wray.py btc_database.db instance2/
cp wray.py btc_database.db instance3/
cd instance1 && python wray.py &
cd instance2 && python wray.py &
cd instance3 && python wray.py &
```

---

## 🔬 Technical Details

### Wallet Generation
- **Standard**: BIP39 mnemonic generation
- **Derivation**: BIP44 path `m/44'/0'/0'/0/0`
- **Entropy**: 128-bit (12 words) or 256-bit (24 words)
- **Passphrase**: BIP39 compliant 13th word

### Address Types
- **Legacy (P2PKH)**: Starts with `1`
- **P2SH**: Starts with `3`
- **SegWit (Bech32)**: Starts with `bc1`

### Database
- **Engine**: SQLite3
- **Indexing**: Address index for fast lookups
- **Caching**: In-memory cache for repeated queries
- **Batch operations**: Optimized for bulk inserts

---

## 📊 Statistics & Benchmarks

### Typical Performance (on modern hardware)

| Operation | Speed |
|-----------|-------|
| Wallet generation | ~100-1000/s |
| Database lookup | ~10,000-50,000/s |
| Online balance check | ~1-2/s (API limited) |
| Passphrase variations | ~50-200/s |

### Bitcoin Address Space

- Total possible addresses: **2^160** ≈ 1.46 × 10^48
- Probability of collision: Essentially **0%**
- For perspective: More addresses than atoms in 1,000 Earths

---

## 📄 License

This project is licensed under the MIT License - see the `LICENSE` file for details.

---

## ⚖️ Legal & Ethical Use

### Allowed Uses
✅ Educational purposes and learning
✅ Security research
✅ Wallet recovery (your own wallets)
✅ Testing and development
✅ Academic research

### Prohibited Uses
❌ Accessing wallets that don't belong to you
❌ Theft or fraud
❌ Violating laws or regulations
❌ Unauthorized access to funds

**By using this tool, you agree to use it legally and ethically.**

---

## 🙏 Acknowledgments

- Bitcoin Core developers
- BIP39 standard authors
- Python cryptography community
- Open source contributors

---

## ⚠️ Final Warning

**The probability of finding a wallet with funds through random generation is essentially ZERO.**

This tool demonstrates:
- How Bitcoin wallets work
- The security of cryptographic systems
- Why proper backup is crucial

**Use responsibly. Use legally. Use ethically.**

---

*W-RAY v2.1 - Advanced Bitcoin Wallet Generator & Recovery Tool*