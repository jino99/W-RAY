#!/usr/bin/env python3
"""
W-RAY v3.0 - Bitcoin Wallet Generator & Recovery Tool
Refactored for maximum performance, correctness, and UX.
"""

import os, sys, hashlib, time, sqlite3, struct, hmac
import multiprocessing
from multiprocessing import Process, Value, cpu_count
from typing import Optional, Dict, List
import asyncio

# ── Optional deps ────────────────────────────────────────────────────────────
try:
    from mnemonic import Mnemonic as _Mnemonic
    HAS_MNEMONIC = True
except ImportError:
    HAS_MNEMONIC = False

try:
    import coincurve as _cc
    HAS_COINCURVE = True
except ImportError:
    HAS_COINCURVE = False

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

try:
    import requests as _requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn, MofNCompleteColumn
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
    HAS_RICH = True
    console = Console()
except ImportError:
    HAS_RICH = False
    class _FallbackConsole:
        def print(self, *a, **kw): print(*a)
        def rule(self, t=""): print("─" * 60, t)
    console = _FallbackConsole()

# ── Constants ────────────────────────────────────────────────────────────────
BTC_DATABASE_FILE = "btc_database.db"
BTC_TXT_FILE      = "btc_database.txt"
BTC_TSV_FILE      = "btc_database.tsv"
FOUND_WALLETS_FILE = "found_wallets.txt"
GEN_WALLETS_FILE   = "gen_wallets.txt"
PASSPHRASE_FILE    = "passphrases.txt"

_SECP256K1_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141

PASSPHRASE_CONFIG = {
    'max_per_seed': 100,
    'strategies': ['common', 'patterns', 'hybrid'],
}

BANNER = r"""
 ██╗    ██╗      ██████╗   ████╗ ██╗   ██╗
 ██║    ██║      ██╔══██╗██╔══██╗╚██╗ ██╔╝
 ██║ █╗ ██║█████╗██████╔╝███████║ ╚████╔╝ 
 ██║███╗██║╚════╝██╔══██╗██╔══██║  ╚██╔╝  
 ╚███╔███╔╝      ██║  ██║██║  ██║   ██║   
  ╚══╝╚══╝       ╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   
"""

MENU = """
  [1] Generate Wallet & Check Balance
  [2] Search BTC Wallet with Balance (Database)
  [3] Search with Advanced Passphrase Attack
  [4] Target Specific Address Attack
  [5] Recover Bitcoin Wallet
  [6] Convert TXT/TSV to SQLite Database
  [7] Database Statistics
  [8] Passphrase Attack Settings
  [9] Exit
"""

# ── Pure-Python crypto primitives (correct fallback) ─────────────────────────

_B58_ALPHABET = b'123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'

def _b58encode(data: bytes) -> str:
    """Correct Base58Check encode."""
    n = int.from_bytes(data, 'big')
    result = []
    while n:
        n, r = divmod(n, 58)
        result.append(_B58_ALPHABET[r])
    for byte in data:
        if byte == 0:
            result.append(_B58_ALPHABET[0])
        else:
            break
    return bytes(reversed(result)).decode('ascii')

def _checksum(payload: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]

def _p2pkh_address(pubkey_bytes: bytes) -> str:
    h = hashlib.new('ripemd160', hashlib.sha256(pubkey_bytes).digest()).digest()
    payload = b'\x00' + h
    return _b58encode(payload + _checksum(payload))

def _p2sh_address(pubkey_hash: bytes) -> str:
    redeem = b'\x00\x14' + pubkey_hash
    sh = hashlib.new('ripemd160', hashlib.sha256(redeem).digest()).digest()
    payload = b'\x05' + sh
    return _b58encode(payload + _checksum(payload))

_BECH32_CHARSET = 'qpzry9x8gf2tvdw0s3jn54khce6mua7l'
_BECH32_GEN = [0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3]

def _bech32_polymod(values):
    chk = 1
    for v in values:
        b = chk >> 25
        chk = (chk & 0x1ffffff) << 5 ^ v
        for i in range(5):
            chk ^= _BECH32_GEN[i] if (b >> i) & 1 else 0
    return chk

def _bech32_hrp_expand(hrp):
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]

def _convertbits(data, frombits, tobits, pad=True):
    acc, bits, ret = 0, 0, []
    for v in data:
        acc = ((acc << frombits) | v) & 0xffffffff
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & ((1 << tobits) - 1))
    if pad and bits:
        ret.append((acc << (tobits - bits)) & ((1 << tobits) - 1))
    return ret

def _bech32_address(pubkey_bytes: bytes) -> str:
    h = hashlib.new('ripemd160', hashlib.sha256(pubkey_bytes).digest()).digest()
    data = [0] + _convertbits(h, 8, 5)
    hrp = 'bc'
    combined = _bech32_hrp_expand(hrp) + data
    chk = _bech32_polymod(combined + [0, 0, 0, 0, 0, 0]) ^ 1
    return hrp + '1' + ''.join(_BECH32_CHARSET[d] for d in data) + \
           ''.join(_BECH32_CHARSET[(chk >> 5 * (5 - i)) & 31] for i in range(6))

# BIP32 derivation (pure Python, used when coincurve unavailable)
def _bip32_derive_pure(seed: bytes, path: List[int]) -> bytes:
    I = hmac.new(b'Bitcoin seed', seed, hashlib.sha512).digest()
    k, c = I[:32], I[32:]
    for idx in path:
        if idx & 0x80000000:
            data = b'\x00' + k + struct.pack('>I', idx)
        else:
            # compressed pubkey from private key (pure python via secp256k1 math)
            pub = _privkey_to_pubkey_pure(k)
            data = pub + struct.pack('>I', idx)
        I2 = hmac.new(c, data, hashlib.sha512).digest()
        il, c = I2[:32], I2[32:]
        k = ((int.from_bytes(il, 'big') + int.from_bytes(k, 'big')) % _SECP256K1_N).to_bytes(32, 'big')
    return k

# Minimal secp256k1 point multiplication for pure-python fallback
_P  = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
_Gx = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
_Gy = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8

def _point_add(P, Q):
    if P is None: return Q
    if Q is None: return P
    if P[0] == Q[0]:
        if P[1] != Q[1]: return None
        m = (3 * P[0] * P[0] * pow(2 * P[1], _P - 2, _P)) % _P
    else:
        m = ((Q[1] - P[1]) * pow(Q[0] - P[0], _P - 2, _P)) % _P
    x = (m * m - P[0] - Q[0]) % _P
    y = (m * (P[0] - x) - P[1]) % _P
    return (x, y)

def _point_mul(k, P):
    R, Q = None, P
    while k:
        if k & 1: R = _point_add(R, Q)
        Q = _point_add(Q, Q)
        k >>= 1
    return R

def _privkey_to_pubkey_pure(privkey: bytes) -> bytes:
    pt = _point_mul(int.from_bytes(privkey, 'big'), (_Gx, _Gy))
    prefix = b'\x02' if pt[1] % 2 == 0 else b'\x03'
    return prefix + pt[0].to_bytes(32, 'big')

# ── Fast wallet generation (coincurve path) ──────────────────────────────────

_PATH44 = [0x8000002C, 0x80000000, 0x80000000, 0, 0]
_PATH49 = [0x80000031, 0x80000000, 0x80000000, 0, 0]
_PATH84 = [0x80000054, 0x80000000, 0x80000000, 0, 0]

def _derive_coincurve(seed: bytes, path: List[int]) -> bytes:
    I = hmac.new(b'Bitcoin seed', seed, hashlib.sha512).digest()
    k, c = I[:32], I[32:]
    for idx in path:
        if idx & 0x80000000:
            data = b'\x00' + k + struct.pack('>I', idx)
        else:
            data = _cc.PublicKey.from_secret(k).format(compressed=True) + struct.pack('>I', idx)
        I2 = hmac.new(c, data, hashlib.sha512).digest()
        il, c = I2[:32], I2[32:]
        k = ((int.from_bytes(il, 'big') + int.from_bytes(k, 'big')) % _SECP256K1_N).to_bytes(32, 'big')
    return k

def _pubkey_hash(privkey: bytes) -> bytes:
    if HAS_COINCURVE:
        pub = _cc.PublicKey.from_secret(privkey).format(compressed=True)
    else:
        pub = _privkey_to_pubkey_pure(privkey)
    return hashlib.new('ripemd160', hashlib.sha256(pub).digest()).digest()

def _derive_fn(seed, path):
    return _derive_coincurve(seed, path) if HAS_COINCURVE else _bip32_derive_pure(seed, path)

def generate_addresses(seed: bytes):
    """Return (legacy, p2sh, bech32) for a seed. Each path derived exactly once."""
    priv44 = _derive_fn(seed, _PATH44)
    priv49 = _derive_fn(seed, _PATH49)
    priv84 = _derive_fn(seed, _PATH84)
    if HAS_COINCURVE:
        pub44 = _cc.PublicKey.from_secret(priv44).format(compressed=True)
        pub49 = _cc.PublicKey.from_secret(priv49).format(compressed=True)
        pub84 = _cc.PublicKey.from_secret(priv84).format(compressed=True)
    else:
        pub44 = _privkey_to_pubkey_pure(priv44)
        pub49 = _privkey_to_pubkey_pure(priv49)
        pub84 = _privkey_to_pubkey_pure(priv84)
    h49 = hashlib.new('ripemd160', hashlib.sha256(pub49).digest()).digest()
    return _p2pkh_address(pub44), _p2sh_address(h49), _bech32_address(pub84)


# ── Database Manager ──────────────────────────────────────────────────────────

class DatabaseManager:
    """
    SQLite-only database manager — no in-memory loading.
    Safe for use from the main process; workers open their own connections
    via DatabaseManager.worker_connect(db_file).
    """
    _PRAGMAS = (
        "PRAGMA journal_mode=WAL",
        "PRAGMA cache_size=-131072",   # 128 MB page cache
        "PRAGMA temp_store=MEMORY",
        "PRAGMA synchronous=OFF",
        "PRAGMA mmap_size=4294967296", # 4 GB mmap — OS handles paging
        "PRAGMA read_uncommitted=1",
    )

    def __init__(self, db_file: str):
        self.db_file = db_file
        self.conn    = None
        self.cursor  = None

    def connect(self) -> bool:
        try:
            self.conn = sqlite3.connect(self.db_file, check_same_thread=False)
            for p in self._PRAGMAS:
                self.conn.execute(p)
            self.cursor = self.conn.cursor()
            return True
        except Exception as e:
            console.print(f"[red][!] DB connect error: {e}[/red]")
            return False

    @staticmethod
    def worker_connect(db_file: str):
        """Open a fresh read-only connection inside a worker process."""
        conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True,
                               check_same_thread=False)
        for p in DatabaseManager._PRAGMAS:
            conn.execute(p)
        return conn

    def create_table(self):
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS btc_addresses
            (address TEXT PRIMARY KEY, balance INTEGER NOT NULL)''')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_addr ON btc_addresses(address)')
        self.conn.commit()

    def check_addresses_batch(self, addresses: List[str]) -> Dict[str, int]:
        """Batch SQLite lookup; returns {addr: balance} for hits only."""
        if not addresses:
            return {}
        hits: Dict[str, int] = {}
        try:
            ph = ','.join('?' * len(addresses))
            self.cursor.execute(
                f'SELECT address,balance FROM btc_addresses WHERE address IN ({ph})',
                addresses)
            for addr, bal in self.cursor.fetchall():
                hits[addr] = bal
        except Exception:
            pass
        return hits

    def get_address_count(self) -> int:
        try:
            self.cursor.execute('SELECT COUNT(*) FROM btc_addresses')
            return self.cursor.fetchone()[0]
        except Exception:
            return 0

    def get_total_balance(self) -> int:
        try:
            self.cursor.execute('SELECT SUM(balance) FROM btc_addresses')
            r = self.cursor.fetchone()
            return r[0] or 0
        except Exception:
            return 0

    def get_statistics(self) -> Dict:
        n = self.get_address_count()
        b = self.get_total_balance()
        return {
            'total_addresses': n,
            'total_balance_satoshis': b,
            'total_balance_btc': b / 1e8,
        }

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None


# ── Worker process (Option 2 hot path) ───────────────────────────────────────

def _worker_generate(shared_counter, result_pipe_w, stop_flag, db_file):
    """
    Worker: generates wallets, checks addresses against SQLite, sends only hits.
    Each worker opens its own read-only SQLite connection — no IPC bottleneck.
    """
    import hashlib, hmac, struct, sqlite3, os as _os
    from mnemonic import Mnemonic as _M

    try:
        import coincurve as _cc
        _has_cc = True
    except ImportError:
        _has_cc = False

    _N        = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
    _mnemo    = _M("english")
    _sha256   = hashlib.sha256
    _ripemd   = lambda b: hashlib.new('ripemd160', b).digest()
    _hmac_new = hmac.new
    _sha512   = hashlib.sha512
    _pack     = struct.pack
    _urandom  = _os.urandom

    # ── BIP39: bypass slow mnemonic.generate() — generate entropy directly ──
    _wordlist = _mnemo.wordlist  # list of 2048 words
    def _fast_mnemonic():
        # 128-bit entropy → 12 words (same as strength=128)
        ent = _urandom(16)
        h   = _sha256(ent).digest()[0]
        # append 4-bit checksum
        bits = int.from_bytes(ent, 'big') << 4 | (h >> 4)
        return ' '.join(_wordlist[(bits >> (11 * (11 - i))) & 0x7FF] for i in range(12))

    B58 = b'123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    def _b58(data):
        n = int.from_bytes(data, 'big')
        r = []
        while n:
            n, rem = divmod(n, 58)
            r.append(B58[rem])
        for byte in data:
            if byte == 0: r.append(B58[0])
            else: break
        return bytes(reversed(r)).decode()

    def _chk(p): return _sha256(_sha256(p).digest()).digest()[:4]

    # ── BIP32: derive one child from (k, c) ──────────────────────────────────
    def _child(k, c, idx):
        if idx & 0x80000000:
            data = b'\x00' + k + _pack('>I', idx)
        else:
            pub = (_cc.PublicKey.from_secret(k).format(compressed=True)
                   if _has_cc else _pub_pure(k))
            data = pub + _pack('>I', idx)
        I2 = _hmac_new(c, data, _sha512).digest()
        il, c2 = I2[:32], I2[32:]
        k2 = ((int.from_bytes(il, 'big') + int.from_bytes(k, 'big')) % _N).to_bytes(32, 'big')
        return k2, c2

    _P  = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
    _Gx = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
    _Gy = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8
    def _padd(P, Q):
        if P is None: return Q
        if Q is None: return P
        if P[0] == Q[0]:
            if P[1] != Q[1]: return None
            m = (3*P[0]*P[0]*pow(2*P[1],_P-2,_P)) % _P
        else:
            m = ((Q[1]-P[1])*pow(Q[0]-P[0],_P-2,_P)) % _P
        x = (m*m - P[0] - Q[0]) % _P
        return (x, (m*(P[0]-x)-P[1]) % _P)
    def _pmul(k, P):
        R, Q = None, P
        while k:
            if k & 1: R = _padd(R, Q)
            Q = _padd(Q, Q); k >>= 1
        return R
    def _pub_pure(priv):
        pt = _pmul(int.from_bytes(priv,'big'), (_Gx,_Gy))
        return (b'\x02' if pt[1]%2==0 else b'\x03') + pt[0].to_bytes(32,'big')

    def _pub(priv):
        return _cc.PublicKey.from_secret(priv).format(compressed=True) if _has_cc else _pub_pure(priv)

    def _pkh(priv): return _ripemd(_sha256(_pub(priv)).digest())

    def _legacy(h):
        p = b'\x00' + h; return _b58(p + _chk(p))
    def _p2sh(h):
        sh = _ripemd(_sha256(b'\x00\x14' + h).digest())
        p = b'\x05' + sh; return _b58(p + _chk(p))

    _BC = 'qpzry9x8gf2tvdw0s3jn54khce6mua7l'
    _BG = [0x3b6a57b2,0x26508e6d,0x1ea119fa,0x3d4233dd,0x2a1462b3]
    def _bech32(h):
        def _pm(v):
            chk = 1
            for x in v:
                b = chk >> 25; chk = (chk & 0x1ffffff) << 5 ^ x
                for i in range(5): chk ^= _BG[i] if (b>>i)&1 else 0
            return chk
        acc, bits, data = 0, 0, [0]
        for v in h:
            acc = ((acc << 8) | v) & 0xffffffff; bits += 8
            while bits >= 5: bits -= 5; data.append((acc >> bits) & 31)
        if bits: data.append((acc << (5 - bits)) & 31)
        chk = _pm([3,3,0,2,3] + data + [0]*6) ^ 1
        return 'bc1' + ''.join(_BC[d] for d in data) + ''.join(_BC[(chk>>5*(5-i))&31] for i in range(6))

    # Hardened index constants
    _H44, _H49, _H84 = 0x8000002C, 0x80000031, 0x80000054
    _H0  = 0x80000000

    # Open worker-local SQLite connection
    try:
        conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True, check_same_thread=False)
        conn.execute("PRAGMA cache_size=-131072")
        conn.execute("PRAGMA mmap_size=4294967296")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA synchronous=OFF")
        cur = conn.cursor()
    except Exception:
        conn = None; cur = None

    BATCH = 512
    local_n = 0
    batch_records = []
    # Pre-build placeholder string for fixed batch size (3 addrs × BATCH)
    _ph_full = ','.join('?' * (BATCH * 3))

    def _check_batch(records):
        if not cur: return
        addrs = []
        for mn, a1, a3, abc in records:
            addrs.append(a1); addrs.append(a3); addrs.append(abc)
        ph = _ph_full if len(addrs) == BATCH * 3 else ','.join('?' * len(addrs))
        try:
            cur.execute(f'SELECT address,balance FROM btc_addresses WHERE address IN ({ph})', addrs)
            hits = {a: b for a, b in cur.fetchall()}
        except Exception:
            return
        if not hits: return
        for mn, a1, a3, abc in records:
            matches = {t: (a, hits[a]) for t, a in
                       [('legacy',a1),('p2sh',a3),('segwit',abc)] if a in hits}
            if matches:
                try:
                    result_pipe_w.send((mn, a1, a3, abc, matches))
                except (BrokenPipeError, OSError):
                    pass

    stop_val = stop_flag  # local ref avoids attribute lookup in hot loop

    while not stop_val.value:
        mnemonic = _fast_mnemonic()
        seed     = _mnemo.to_seed(mnemonic, passphrase="")

        # BIP32 master key — computed once per seed
        I    = _hmac_new(b'Bitcoin seed', seed, _sha512).digest()
        mk, mc = I[:32], I[32:]

        # Derive m/purpose'/0'/0' — shared prefix for all 3 paths
        # then branch: /0/0 for each
        # m/44'/0'/0'/0/0
        k, c = _child(mk, mc, _H44)
        k, c = _child(k,  c,  _H0)
        k, c = _child(k,  c,  _H0)
        k, c = _child(k,  c,  0)
        k44, _ = _child(k, c, 0)

        # m/49'/0'/0'/0/0
        k, c = _child(mk, mc, _H49)
        k, c = _child(k,  c,  _H0)
        k, c = _child(k,  c,  _H0)
        k, c = _child(k,  c,  0)
        k49, _ = _child(k, c, 0)

        # m/84'/0'/0'/0/0
        k, c = _child(mk, mc, _H84)
        k, c = _child(k,  c,  _H0)
        k, c = _child(k,  c,  _H0)
        k, c = _child(k,  c,  0)
        k84, _ = _child(k, c, 0)

        a1  = _legacy(_pkh(k44))
        a3  = _p2sh(_pkh(k49))
        abc = _bech32(_pkh(k84))

        batch_records.append((mnemonic, a1, a3, abc))
        local_n += 1

        if local_n >= BATCH:
            _check_batch(batch_records)
            batch_records = []
            with shared_counter.get_lock():
                shared_counter.value += local_n
            local_n = 0

    if local_n:
        if batch_records:
            _check_batch(batch_records)
        with shared_counter.get_lock():
            shared_counter.value += local_n

    if conn:
        conn.close()


# ── Async balance checker ─────────────────────────────────────────────────────

_BALANCE_APIS = [
    ("Blockstream",    "https://blockstream.info/api/address/{addr}",
     lambda j: (j.get('chain_stats',{}).get('funded_txo_sum',0) -
                j.get('chain_stats',{}).get('spent_txo_sum',0)) / 1e8),
    ("Mempool.space",  "https://mempool.space/api/address/{addr}",
     lambda j: (j.get('chain_stats',{}).get('funded_txo_sum',0) -
                j.get('chain_stats',{}).get('spent_txo_sum',0)) / 1e8),
    ("BlockCypher",    "https://api.blockcypher.com/v1/btc/main/addrs/{addr}/balance",
     lambda j: j.get('final_balance', 0) / 1e8),
]

async def _async_check_balance(address: str) -> Optional[float]:
    """Try each API in order; handle 429 with backoff; non-blocking."""
    if not HAS_AIOHTTP:
        return _sync_check_balance(address)
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
        for name, url_tpl, parser in _BALANCE_APIS:
            url = url_tpl.format(addr=address)
            for attempt in range(2):
                try:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            return parser(await resp.json(content_type=None))
                        if resp.status == 429:
                            await asyncio.sleep(3 * (attempt + 1))
                            continue
                        break
                except Exception:
                    break
    return None

def check_balance_online(address: str) -> Optional[float]:
    """Sync wrapper — runs async check in a new event loop."""
    try:
        return asyncio.run(_async_check_balance(address))
    except Exception:
        return _sync_check_balance(address)

def _sync_check_balance(address: str) -> Optional[float]:
    """Synchronous fallback using requests."""
    if not HAS_REQUESTS:
        return None
    for name, url_tpl, parser in _BALANCE_APIS:
        url = url_tpl.format(addr=address)
        for attempt in range(2):
            try:
                r = _requests.get(url, timeout=10)
                if r.status_code == 200:
                    return parser(r.json())
                if r.status_code == 429:
                    time.sleep(3 * (attempt + 1))
                    continue
                break
            except Exception:
                break
    return None

# ── Passphrase generator ──────────────────────────────────────────────────────

class PassphraseGenerator:
    def __init__(self):
        self.common = self._load_common()
        self.patterns = self._build_patterns()

    def _load_common(self) -> List[str]:
        base = ["", "password","123456","12345678","qwerty","abc123","password123",
                "bitcoin","satoshi","crypto","wallet","blockchain","BTC","hodl",
                "lambo","moon","test","secret","passphrase","admin","root"]
        if os.path.exists(PASSPHRASE_FILE):
            try:
                with open(PASSPHRASE_FILE, encoding='utf-8') as f:
                    for line in f:
                        p = line.strip()
                        if p and p not in base:
                            base.append(p)
            except Exception:
                pass
        return base

    def _build_patterns(self) -> List[str]:
        p = [str(y) for y in range(1980, 2026)]
        p += [str(i) for i in range(1, 1000)]
        for w in ['bitcoin','btc','satoshi','crypto','wallet']:
            for i in range(100):
                p += [f"{w}{i}", f"{w.upper()}{i}", f"{w.capitalize()}{i}"]
        return p

    def get_passphrases(self, seed_words: List[str], max_count: int = 100) -> List[str]:
        seen, result = set(), []
        def _add(lst):
            for p in lst:
                if p not in seen and len(result) < max_count:
                    seen.add(p); result.append(p)
        _add(self.common)
        _add(self.patterns)
        # hybrids
        suffixes = ['123','!','2024','2023','21','22','23','24']
        for w in seed_words[:10]:
            for s in suffixes:
                _add([f"{w}{s}"])
        # ensure empty passphrase is first
        if "" in result: result.remove("")
        result.insert(0, "")
        return result[:max_count]


# ── Rich UI helpers ───────────────────────────────────────────────────────────

def _print_banner():
    os.system('clear' if os.name != 'nt' else 'cls')
    if HAS_RICH:
        console.print(f"[bold cyan]{BANNER}[/bold cyan]")
        console.print(Panel.fit(
            "[bold yellow]Bitcoin Wallet Generator & Recovery Tool[/bold yellow]\n"
            "[dim]Advanced Passphrase Attack Engine v3.0[/dim]",
            border_style="cyan"))
    else:
        print(BANNER)
        print("  Bitcoin Wallet Generator & Recovery Tool  v3.0")
        print("=" * 60)

def _print_menu():
    if HAS_RICH:
        console.print(Panel(MENU, title="[bold cyan]MAIN MENU[/bold cyan]",
                            border_style="cyan", box=box.ROUNDED))
    else:
        print(MENU)

def _wallet_table(wallet: dict):
    if not HAS_RICH:
        for k, v in wallet.items():
            if k != 'private_key':
                print(f"  {k}: {v}")
        return
    t = Table(box=box.SIMPLE, show_header=False, padding=(0,1))
    t.add_column("Key",   style="dim cyan",  no_wrap=True)
    t.add_column("Value", style="white", overflow="fold")
    skip = {'private_key', 'wif'}
    for k, v in wallet.items():
        if k not in skip and v and v != 'N/A':
            t.add_row(k, str(v))
    console.print(t)

def _stats_table(stats: dict, db_file: str):
    if not HAS_RICH:
        print(f"  Total Addresses: {stats['total_addresses']:,}")
        print(f"  Total Balance:   {stats['total_balance_btc']:.8f} BTC")
        return
    t = Table(title="[bold]Database Statistics[/bold]", box=box.ROUNDED,
              border_style="cyan", show_header=False)
    t.add_column("Field", style="cyan")
    t.add_column("Value", style="white")
    t.add_row("Total Addresses", f"{stats['total_addresses']:,}")
    t.add_row("Total Balance",   f"{stats['total_balance_btc']:.8f} BTC")
    t.add_row("Lookup Mode",     "SQLite (WAL + mmap)")
    if os.path.exists(db_file):
        sz = os.path.getsize(db_file) / (1024 * 1024)
        t.add_row("DB File Size", f"{sz:.2f} MB")
    console.print(t)

# ── Database conversion helpers ───────────────────────────────────────────────

def _find_source_file() -> Optional[str]:
    for f in [BTC_TXT_FILE, BTC_TSV_FILE]:
        if os.path.exists(f):
            return f
    return None

def _perform_conversion(src: str, db_file: str, sep: Optional[str],
                        addr_col: int, bal_col: Optional[int], has_header: bool) -> bool:
    if os.path.exists(db_file):
        os.remove(db_file)
    db = DatabaseManager(db_file)
    if not db.connect():
        return False
    db.create_table()

    total, skipped, batch = 0, 0, []
    BATCH = 10_000

    def _flush():
        nonlocal total
        db.cursor.executemany(
            'INSERT OR REPLACE INTO btc_addresses (address,balance) VALUES (?,?)', batch)
        db.conn.commit()
        total += len(batch)
        batch.clear()

    line_num = 0
    if HAS_RICH:
        file_lines = sum(1 for _ in open(src, encoding='utf-8', errors='ignore'))
        prog_ctx = Progress(SpinnerColumn(), TextColumn("[cyan]{task.description}"),
                            BarColumn(), MofNCompleteColumn(), TimeElapsedColumn())
        task_id = None
    else:
        prog_ctx = None

    try:
        with open(src, encoding='utf-8', errors='ignore') as f:
            if HAS_RICH and prog_ctx:
                prog_ctx.start()
                task_id = prog_ctx.add_task("Converting...", total=file_lines)
            for line in f:
                line_num += 1
                if HAS_RICH and prog_ctx and task_id is not None:
                    prog_ctx.update(task_id, advance=1)
                line = line.strip()
                if not line or (has_header and line_num == 1):
                    continue
                try:
                    parts = line.split(sep) if sep else [line]
                    if addr_col >= len(parts):
                        skipped += 1; continue
                    address = parts[addr_col].strip()
                    if not (address.startswith(('1','3','bc1','tb1'))):
                        skipped += 1; continue
                    balance = 0
                    if bal_col is not None and bal_col < len(parts):
                        bs = ''.join(c for c in parts[bal_col] if c.isdigit())
                        balance = int(bs) if bs else 0
                    batch.append((address, balance))
                    if len(batch) >= BATCH:
                        _flush()
                except Exception:
                    skipped += 1
            if batch:
                _flush()
    finally:
        if HAS_RICH and prog_ctx:
            prog_ctx.stop()

    db.close()
    console.print(f"[green][+] Done: {total:,} addresses, {skipped:,} skipped[/green]")
    return True

def convert_database_menu():
    src = _find_source_file()
    if not src:
        console.print(f"[red][!] No source file found ({BTC_TXT_FILE} or {BTC_TSV_FILE})[/red]")
        return False
    console.print(f"[cyan][+] Source: {src}  ({os.path.getsize(src)/1024/1024:.1f} MB)[/cyan]")
    console.print("[1] Auto-detect format (recommended)\n[2] Direct (TAB-separated, no validation)")
    mode = input("Mode: ").strip()
    if mode == '2':
        if input("Proceed? (y/n): ").lower() != 'y': return False
        return _perform_conversion(src, BTC_DATABASE_FILE, '\t', 0, 1, False)
    # Auto-detect
    sep, addr_col, bal_col, has_header = '\t', 0, 1, False
    with open(src, encoding='utf-8', errors='ignore') as f:
        sample = [f.readline().strip() for _ in range(5)]
    console.print("[dim]Sample lines:[/dim]")
    for i, l in enumerate(sample[:3], 1):
        console.print(f"  {i}. {l[:100]}")
    try:
        addr_col = int(input(f"Address column index [0]: ").strip() or "0")
        bal_input = input("Balance column index [1] (or 'none'): ").strip()
        bal_col = None if bal_input.lower() == 'none' else int(bal_input or "1")
        has_header = input("First line is header? (y/n) [n]: ").strip().lower() == 'y'
        sep_input = input("Separator (tab/comma/space) [tab]: ").strip().lower()
        sep = {'comma': ',', 'space': ' ', 'tab': '\t'}.get(sep_input, '\t')
    except Exception:
        pass
    if input("Proceed? (y/n): ").lower() != 'y': return False
    return _perform_conversion(src, BTC_DATABASE_FILE, sep, addr_col, bal_col, has_header)


# ── Main application class ────────────────────────────────────────────────────

class WRay:
    def __init__(self):
        self.db: Optional[DatabaseManager] = None
        self.passgen = PassphraseGenerator()
        self.mnemo   = _Mnemonic("english") if HAS_MNEMONIC else None
        self._load_db()

    # ── DB ────────────────────────────────────────────────────────────────────

    def _load_db(self):
        if not os.path.exists(BTC_DATABASE_FILE):
            console.print(f"[yellow][!] Database '{BTC_DATABASE_FILE}' not found. Use option [6] to create it.[/yellow]")
            return
        print(f"[*] Connecting to database '{BTC_DATABASE_FILE}'...", end="", flush=True)
        if self.db:
            self.db.close()
        self.db = DatabaseManager(BTC_DATABASE_FILE)
        if self.db.connect():
            count = self.db.get_address_count()
            print(f"\r[+] Database ready: {count:,} addresses" + " " * 20)
        else:
            print(f"\r[!] Failed to open database" + " " * 20)
            self.db = None

    # ── Wallet generation ─────────────────────────────────────────────────────

    def _mnemonic(self) -> str:
        return self.mnemo.generate(strength=128) if self.mnemo else "abandon " * 11 + "about"

    def _wallet(self, mnemonic: str, passphrase: str = "", all_types: bool = False) -> dict:
        """Generate wallet dict. Uses pure-python crypto (no bitcoinlib dependency)."""
        seed = (self.mnemo.to_seed(mnemonic, passphrase=passphrase)
                if self.mnemo
                else hashlib.pbkdf2_hmac('sha512', mnemonic.encode(),
                                         b'mnemonic' + passphrase.encode(), 2048))
        priv44 = _derive_fn(seed, _PATH44)

        if HAS_COINCURVE:
            pub44 = _cc.PublicKey.from_secret(priv44).format(compressed=True)
        else:
            pub44 = _privkey_to_pubkey_pure(priv44)

        legacy = _p2pkh_address(pub44)
        p2sh   = 'N/A'
        bech32 = 'N/A'

        if all_types:
            priv49 = _derive_fn(seed, _PATH49)
            priv84 = _derive_fn(seed, _PATH84)
            h49 = _pubkey_hash(priv49)
            p2sh = _p2sh_address(h49)
            if HAS_COINCURVE:
                pub84 = _cc.PublicKey.from_secret(priv84).format(compressed=True)
            else:
                pub84 = _privkey_to_pubkey_pure(priv84)
            bech32 = _bech32_address(pub84)

        wif_raw = b'\x80' + priv44 + b'\x01'
        wif = _b58encode(wif_raw + _checksum(wif_raw))

        return {
            'mnemonic':        mnemonic,
            'passphrase':      passphrase,
            'private_key':     priv44.hex(),
            'wif':             wif,
            'legacy_address':  legacy,
            'p2sh_address':    p2sh,
            'segwit_address':  bech32,
        }

    def _save_found(self, wallet: dict, matches: Dict):
        total_btc = sum(m['balance_btc'] for m in matches.values())
        with open(FOUND_WALLETS_FILE, 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*70}\n")
            f.write(f"FOUND - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total: {total_btc:.8f} BTC\n")
            f.write(f"Mnemonic: {wallet['mnemonic']}\n")
            if wallet.get('passphrase'):
                f.write(f"Passphrase: {wallet['passphrase']}\n")
            f.write(f"PrivKey: {wallet['private_key']}\n")
            f.write(f"WIF: {wallet.get('wif','N/A')}\n")
            for t, d in matches.items():
                f.write(f"{t}: {d['address']}  {d['balance_btc']:.8f} BTC\n")
            f.write(f"{'='*70}\n")
        if HAS_RICH:
            console.print(Panel(
                f"[bold green]MATCH FOUND![/bold green]\n"
                f"Balance: [yellow]{total_btc:.8f} BTC[/yellow]\n"
                f"Mnemonic: {wallet['mnemonic']}\n"
                f"Saved to: {FOUND_WALLETS_FILE}",
                border_style="green"))
        else:
            print(f"\n[FOUND] {total_btc:.8f} BTC — saved to {FOUND_WALLETS_FILE}")

    # ── Option 1: Generate & check balance ───────────────────────────────────

    def generate_and_check_balance(self):
        console.print("\n[1] Single wallet\n[2] Continuous generation")
        mode = input("Mode: ").strip()
        if mode == '1':
            w = self._wallet(self._mnemonic(), all_types=True)
            _wallet_table(w)
            if HAS_REQUESTS or HAS_AIOHTTP:
                console.print("[cyan][*] Checking balance...[/cyan]")
                bal = check_balance_online(w['legacy_address'])
                console.print(f"  Legacy: {bal:.8f} BTC" if bal is not None else "  [red]API unavailable[/red]")
        elif mode == '2':
            self._continuous_gen()

    def _continuous_gen(self):
        if not (HAS_REQUESTS or HAS_AIOHTTP):
            console.print("[red][!] Install requests or aiohttp for online balance checks[/red]")
            return
        console.print("[cyan][*] Continuous generation — CTRL+C to stop[/cyan]")
        attempts, found, start = 0, 0, time.time()
        try:
            while True:
                w = self._wallet(self._mnemonic())
                attempts += 1
                bal = check_balance_online(w['legacy_address'])
                if bal is not None and bal > 0:
                    found += 1
                    self._save_found(w, {'legacy_address': {
                        'address': w['legacy_address'],
                        'balance_satoshis': int(bal * 1e8),
                        'balance_btc': bal}})
                elapsed = time.time() - start
                print(f"\r[*] {attempts:,} | {attempts/elapsed:.1f}/s | found:{found}", end='', flush=True)
        except KeyboardInterrupt:
            print()

    # ── Option 2: Database search (multiprocessing + Bloom) ──────────────────

    def search_basic(self):
        if not self.db:
            console.print("[red][!] Database not loaded[/red]"); return

        stats      = self.db.get_statistics()
        n_workers  = max(1, cpu_count())
        stop_flag  = Value('b', 0)
        counter    = Value('L', 0)

        pipes = [multiprocessing.Pipe(duplex=False) for _ in range(n_workers)]
        workers = []
        # Redirect stderr to /dev/null to suppress "Process Process-N:" termination noise
        devnull = open(os.devnull, 'w')
        for r_conn, w_conn in pipes:
            p = Process(target=_worker_generate,
                        args=(counter, w_conn, stop_flag, self.db.db_file), daemon=True)
            p.start()
            workers.append(p)
            w_conn.close()

        read_ends = [r for r, _ in pipes]

        if HAS_RICH:
            console.print(Panel(
                f"Workers: [cyan]{n_workers}[/cyan]  |  "
                f"DB addresses: [cyan]{stats['total_addresses']:,}[/cyan]\n"
                f"[dim]CTRL+C to stop[/dim]",
                title="[bold cyan]DATABASE SEARCH[/bold cyan]", border_style="cyan"))
        else:
            print(f"\n[*] Workers: {n_workers} | DB: {stats['total_addresses']:,} | CTRL+C to stop")

        found, start = 0, time.time()
        last_update  = start
        _ERASE = '\r\033[2K'  # carriage return + erase entire line

        try:
            import select as _select
            # Suppress subprocess stderr noise during the run
            old_stderr = sys.stderr
            sys.stderr = devnull
            while True:
                try:
                    ready, _, _ = _select.select(read_ends, [], [], 0.05)
                except Exception:
                    ready = []

                for conn in ready:
                    while conn.poll():
                        try:
                            mn, a1, a3, abc, matches = conn.recv()
                            found += 1
                            fmt_matches = {t: {'address': a, 'balance_satoshis': b, 'balance_btc': b/1e8}
                                           for t, (a, b) in matches.items()}
                            self._save_found({'mnemonic': mn, 'passphrase': '',
                                              'private_key': 'N/A', 'wif': 'N/A',
                                              'legacy_address': a1, 'p2sh_address': a3,
                                              'segwit_address': abc}, fmt_matches)
                        except (EOFError, OSError):
                            break

                now = time.time()
                if now - last_update >= 1.0:
                    elapsed = now - start
                    spd = int(counter.value / elapsed) if elapsed else 0
                    print(f"{_ERASE}[*] Seeds: {counter.value:,} | ~{spd:,}/s | "
                          f"Addr/s: ~{spd*3:,} | Found: {found}", end='', flush=True)
                    last_update = now

        except KeyboardInterrupt:
            stop_flag.value = 1
            elapsed = time.time() - start
            sys.stderr = old_stderr
            print(f"{_ERASE}[*] Stopped — {counter.value:,} seeds in {elapsed:.1f}s "
                  f"({int(counter.value/elapsed) if elapsed else 0:,}/s) | Found: {found}")
        finally:
            sys.stderr = old_stderr
            devnull.close()
            stop_flag.value = 1
            for p in workers:
                p.terminate()
            for p in workers:
                p.join(timeout=2)
            for conn in read_ends:
                conn.close()

    # ── Option 3: Passphrase attack ───────────────────────────────────────────

    def search_with_passphrase_attack(self):
        if not self.db:
            console.print("[red][!] Database not loaded[/red]"); return
        console.print("[cyan][*] Passphrase attack — CTRL+C to stop[/cyan]")
        seeds, passes, found, start = 0, 0, 0, time.time()
        try:
            while True:
                mn = self._mnemonic()
                seeds += 1
                for pp in self.passgen.get_passphrases(mn.split(), PASSPHRASE_CONFIG['max_per_seed']):
                    w = self._wallet(mn, pp)
                    passes += 1
                    addrs = [w['legacy_address']]
                    hits = self.db.check_addresses_batch(addrs)
                    if hits:
                        found += 1
                        matches = {t: {'address':a,'balance_satoshis':hits[a],'balance_btc':hits[a]/1e8}
                                   for t,a in [('legacy_address',w['legacy_address'])] if a in hits}
                        self._save_found(w, matches)
                elapsed = time.time() - start
                print(f"\r[*] Seeds:{seeds:,} | Passes:{passes:,} | "
                      f"{int(passes/elapsed) if elapsed else 0}/s | Found:{found}", end='', flush=True)
        except KeyboardInterrupt:
            print()

    # ── Option 4: Target address ──────────────────────────────────────────────

    def target_specific_address(self):
        target = input("\nTarget Bitcoin address: ").strip()
        if not target:
            return
        console.print(f"[cyan][*] Targeting: {target}[/cyan]")
        console.print("[1] Random seeds\n[2] Random seeds + passphrases\n[3] Known seed + passphrase bruteforce")
        mode = input("Mode: ").strip()

        addr_key = ('legacy_address' if target.startswith('1') else
                    'p2sh_address'   if target.startswith('3') else 'segwit_address')

        if mode == '3':
            mn = input("Seed phrase: ").strip()
            if not mn: return
            pps = self.passgen.get_passphrases(mn.split(), 10000)
            console.print(f"[cyan][*] Testing {len(pps):,} passphrases...[/cyan]")
            if HAS_RICH:
                with Progress(SpinnerColumn(), BarColumn(), MofNCompleteColumn(),
                               TimeElapsedColumn()) as prog:
                    task = prog.add_task("Bruteforcing...", total=len(pps))
                    for pp in pps:
                        w = self._wallet(mn, pp)
                        prog.advance(task)
                        if w.get(addr_key) == target:
                            console.print(f"[bold green]FOUND! Passphrase: '{pp}'[/bold green]")
                            self._save_found(w, {addr_key: {'address':target,'balance_satoshis':0,'balance_btc':0}})
                            return
            else:
                for i, pp in enumerate(pps):
                    w = self._wallet(mn, pp)
                    if w.get(addr_key) == target:
                        print(f"\n[FOUND] Passphrase: '{pp}'")
                        return
                    if i % 100 == 0:
                        print(f"\r[*] {i}/{len(pps)}", end='', flush=True)
            console.print("[yellow][!] Not found[/yellow]")
            return

        # Modes 1 & 2
        use_pp = (mode == '2')
        attempts, start = 0, time.time()
        try:
            while True:
                mn = self._mnemonic()
                pps = self.passgen.get_passphrases(mn.split(), 50) if use_pp else [""]
                for pp in pps:
                    w = self._wallet(mn, pp)
                    attempts += 1
                    if w.get(addr_key) == target:
                        console.print(f"[bold green]TARGET FOUND after {attempts:,} attempts![/bold green]")
                        self._save_found(w, {addr_key: {'address':target,'balance_satoshis':0,'balance_btc':0}})
                        return
                elapsed = time.time() - start
                print(f"\r[*] {attempts:,} | {int(attempts/elapsed) if elapsed else 0}/s", end='', flush=True)
        except KeyboardInterrupt:
            print()

    # ── Option 5: Recovery ────────────────────────────────────────────────────

    def recovery_wallet(self):
        mn = input("\nSeed phrase (12 or 24 words): ").strip()
        if not mn or len(mn.split()) not in (12, 24):
            console.print("[red][!] Invalid seed length[/red]"); return
        if self.mnemo and not self.mnemo.check(mn):
            if input("[!] Seed invalid. Continue? (y/n): ").lower() != 'y': return
        pp = input("Passphrase (Enter for none): ").strip()
        w  = self._wallet(mn, pp, all_types=True)
        _wallet_table(w)
        if input("\nShow private key? (y/n): ").lower() == 'y':
            console.print(f"  PrivKey: {w['private_key']}\n  WIF: {w['wif']}")
        if self.db:
            addrs = [w['legacy_address'], w['p2sh_address'], w['segwit_address']]
            hits  = self.db.check_addresses_batch([a for a in addrs if a != 'N/A'])
            if hits:
                console.print("[bold green]Addresses found in database![/bold green]")
                for addr, bal in hits.items():
                    console.print(f"  {addr}  →  {bal/1e8:.8f} BTC")
        if input("\nSave to file? (y/n): ").lower() == 'y':
            with open('recovered_wallet.txt', 'w', encoding='utf-8') as f:
                for k, v in w.items():
                    f.write(f"{k}: {v}\n")
            console.print(f"[green][+] Saved to recovered_wallet.txt[/green]")

    # ── Option 7: DB stats ────────────────────────────────────────────────────

    def show_database_stats(self):
        if not self.db:
            console.print("[red][!] Database not loaded[/red]"); return
        _stats_table(self.db.get_statistics(), BTC_DATABASE_FILE)

    # ── Option 8: Settings ────────────────────────────────────────────────────

    def configure_settings(self):
        console.print(f"\n  max_per_seed: {PASSPHRASE_CONFIG['max_per_seed']}")
        console.print(f"  strategies:   {PASSPHRASE_CONFIG['strategies']}")
        console.print("\n[1] Change max passphrases per seed\n[2] Reload passphrase file")
        c = input("Choice: ").strip()
        if c == '1':
            try:
                v = int(input("New max (1-1000): "))
                if 1 <= v <= 1000:
                    PASSPHRASE_CONFIG['max_per_seed'] = v
            except ValueError:
                pass
        elif c == '2':
            self.passgen = PassphraseGenerator()
            console.print("[green][+] Reloaded[/green]")

    def __del__(self):
        if self.db:
            self.db.close()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    _print_banner()

    if not HAS_MNEMONIC:
        console.print("[yellow][!] 'mnemonic' not installed — pip install mnemonic[/yellow]")
    if not HAS_COINCURVE:
        console.print("[yellow][!] 'coincurve' not installed — pip install coincurve  (pure-python fallback active, ~10x slower)[/yellow]")
    if not (HAS_AIOHTTP or HAS_REQUESTS):
        console.print("[yellow][!] Install aiohttp or requests for online balance checks[/yellow]")
    if not HAS_RICH:
        console.print("[yellow][!] Install 'rich' for enhanced UI — pip install rich[/yellow]")

    app = WRay()

    dispatch = {
        '1': app.generate_and_check_balance,
        '2': app.search_basic,
        '3': app.search_with_passphrase_attack,
        '4': app.target_specific_address,
        '5': app.recovery_wallet,
        '6': lambda: (convert_database_menu(), app._load_db()),
        '7': app.show_database_stats,
        '8': app.configure_settings,
    }

    while True:
        _print_menu()
        try:
            choice = input("  Choose an option: ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[cyan]Goodbye![/cyan]")
            sys.exit(0)

        if choice == '9':
            console.print("\n[cyan]Goodbye![/cyan]")
            sys.exit(0)

        fn = dispatch.get(choice)
        if fn:
            try:
                fn()
            except KeyboardInterrupt:
                console.print("\n[yellow][!] Interrupted[/yellow]")
        else:
            console.print("[red][!] Invalid option[/red]")


if __name__ == "__main__":
    if sys.platform != 'win32':
        multiprocessing.set_start_method('fork', force=True)
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow][!] Interrupted[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[red][!] Fatal: {e}[/red]")
        import traceback; traceback.print_exc()
        sys.exit(1)
