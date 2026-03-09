#!/usr/bin/env python3
"""
W-RAY - Bitcoin Wallet Generator & Recovery Tool
Advanced Bitcoin wallet generation and balance checking tool with passphrase support
"""

import os
import sys
import hashlib
import secrets
import time
import sqlite3
import itertools
from typing import Optional, Dict, List, Set

# ASCII Banner
BANNER = """
 ██╗    ██╗      ██████╗   ████╗ ██╗   ██╗
 ██║    ██║      ██╔══██╗██╔══██╗╚██╗ ██╔╝
 ██║ █╗ ██║█████╗██████╔╝███████║ ╚████╔╝ 
 ██║███╗██║╚════╝██╔══██╗██╔══██║  ╚██╔╝  
 ╚███╔███╔╝      ██║  ██║██║  ██║   ██║   
  ╚══╝╚══╝       ╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Bitcoin Wallet Generator & Recovery Tool
   Advanced Passphrase Attack Engine v2.1
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

MENU = """
[1] Generate Wallet & Check Balance
[2] Search BTC Wallet with Balance (Database)
[3] Search with Advanced Passphrase Attack
[4] Target Specific Address Attack
[5] Recovery Bitcoin Wallet
[6] Convert TXT/TSV to SQLite Database
[7] Database Statistics
[8] Passphrase Attack Settings
[9] Exit

"""

# Configuration
BTC_DATABASE_FILE = "btc_database.db"
BTC_TXT_FILE = "btc_database.txt"
BTC_TSV_FILE = "btc_database.tsv"
FOUND_WALLETS_FILE = "found_wallets.txt"
GEN_WALLETS_FILE = "gen_wallets.txt"
PASSPHRASE_FILE = "passphrases.txt"

# Passphrase attack configuration
PASSPHRASE_CONFIG = {
    'enabled': True,
    'max_per_seed': 100,
    'strategies': ['common', 'patterns', 'hybrid'],
    'max_length': 20,
    'min_length': 0
}

try:
    from mnemonic import Mnemonic
    HAS_MNEMONIC = True
except ImportError:
    HAS_MNEMONIC = False
    print("[!] WARNING: Module 'mnemonic' not found")
    print("[!] Install with: pip install mnemonic")
    print("[!] Program will run in simplified mode\n")
# API rate limiting
API_CALL_DELAY = 1.0
LAST_API_CALL = 0

try:
    from bitcoinlib.keys import HDKey
    from bitcoinlib.encoding import addr_bech32
    HAS_BITCOINLIB = True
except ImportError:
    HAS_BITCOINLIB = False
    print("[!] WARNING: Module 'bitcoinlib' not found")
    print("[!] Install with: pip install bitcoinlib")
    print("[!] Program will run in simplified mode\n")

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    print("[!] WARNING: Module 'requests' not found")
    print("[!] Install with: pip install requests")
    print("[!] Balance checking will not be available\n")


class PassphraseGenerator:
    """Advanced passphrase generation and attack strategies"""
    
    def __init__(self):
        self.common_passphrases = self.load_common_passphrases()
        self.patterns = self.generate_patterns()
    
    def load_common_passphrases(self) -> List[str]:
        """Load common passphrases from file or use defaults"""
        passphrases = [
            "",  # Empty passphrase (most common!)
            "password", "123456", "12345678", "qwerty", "abc123",
            "password123", "12345", "1234567", "123456789",
            "bitcoin", "satoshi", "crypto", "wallet", "blockchain",
            "BTC", "hodl", "lambo", "moon", "test", "secret",
            "passphrase", "mypassword", "admin", "root", "toor",
        ]
        
        if os.path.exists(PASSPHRASE_FILE):
            try:
                with open(PASSPHRASE_FILE, 'r', encoding='utf-8') as f:
                    for line in f:
                        phrase = line.strip()
                        if phrase and phrase not in passphrases:
                            passphrases.append(phrase)
                print(f"[+] Loaded {len(passphrases)} passphrases from {PASSPHRASE_FILE}")
            except Exception as e:
                print(f"[!] Error loading passphrase file: {e}")
        
        return passphrases
    
    def generate_patterns(self) -> List[str]:
        """Generate common patterns for passphrases"""
        patterns = []
        
        for year in range(1980, 2026):
            patterns.append(str(year))
        
        for i in range(1, 1000):
            patterns.append(str(i))
        
        btc_words = ['bitcoin', 'btc', 'satoshi', 'crypto', 'wallet']
        for word in btc_words:
            for i in range(100):
                patterns.append(f"{word}{i}")
                patterns.append(f"{word.upper()}{i}")
                patterns.append(f"{word.capitalize()}{i}")
        
        return patterns
    
    def generate_hybrid_passphrases(self, base_words: List[str], max_combinations: int = 1000) -> List[str]:
        """Generate hybrid passphrases combining words and numbers"""
        hybrids = []
        
        for w1, w2 in itertools.islice(itertools.combinations(base_words[:20], 2), max_combinations // 4):
            hybrids.append(f"{w1}{w2}")
            hybrids.append(f"{w1}_{w2}")
            hybrids.append(f"{w1}-{w2}")
        
        suffixes = ['123', '!', '2024', '2023', '2022', '21', '22', '23', '24']
        for word in base_words[:30]:
            for suffix in suffixes:
                hybrids.append(f"{word}{suffix}")
        
        prefixes = ['my', 'the', 'super', 'mega']
        for prefix in prefixes:
            for word in base_words[:20]:
                hybrids.append(f"{prefix}{word}")
        
        return hybrids[:max_combinations]
    
    def get_passphrases_for_seed(self, seed_words: List[str], strategy: str = 'all', max_count: int = 100) -> List[str]:
        """Get passphrases to test for a given seed"""
        passphrases = set()
        
        if strategy in ['all', 'common']:
            passphrases.update(self.common_passphrases[:max_count // 3])
        
        if strategy in ['all', 'patterns']:
            passphrases.update(self.patterns[:max_count // 3])
        
        if strategy in ['all', 'hybrid']:
            hybrids = self.generate_hybrid_passphrases(seed_words, max_count // 3)
            passphrases.update(hybrids)
        
        result = list(passphrases)[:max_count]
        
        if "" in result:
            result.remove("")
        result.insert(0, "")
        
        return result


class DatabaseManager:
    """Manages SQLite database for Bitcoin addresses with balances"""
    
    def __init__(self, db_file: str):
        self.db_file = db_file
        self.conn = None
        self.cursor = None
        self.cache = {}
        self.cache_enabled = True
        self.cache_max_size = 100000
        self.cache_hits = 0
        self.cache_misses = 0
    
    def connect(self):
        """Connect to SQLite database"""
        try:
            self.conn = sqlite3.connect(self.db_file)
            self.cursor = self.conn.cursor()
            return True
        except Exception as e:
            print(f"[!] Error connecting to database: {e}")
            return False
    
    def create_table(self):
        """Create table for Bitcoin addresses with balances"""
        try:
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS btc_addresses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    address TEXT UNIQUE NOT NULL,
                    balance INTEGER NOT NULL
                )
            ''')
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_address ON btc_addresses(address)')
            self.conn.commit()
            return True
        except Exception as e:
            print(f"[!] Error creating table: {e}")
            return False
    
    def insert_address(self, address: str, balance: int):
        """Insert an address with balance into database"""
        try:
            self.cursor.execute('INSERT OR REPLACE INTO btc_addresses (address, balance) VALUES (?, ?)', 
                              (address.strip(), balance))
            return True
        except Exception as e:
            return False
    
    def check_address(self, address: str) -> Optional[int]:
        """Check if address exists in database and return balance (with caching)"""
        if self.cache_enabled and address in self.cache:
            self.cache_hits += 1
            return self.cache[address]
        
        self.cache_misses += 1
        
        try:
            self.cursor.execute('SELECT balance FROM btc_addresses WHERE address = ?', (address,))
            result = self.cursor.fetchone()
            balance = result[0] if result else None
            
            if self.cache_enabled:
                
                if len(self.cache) >= self.cache_max_size:
                    remove_count = self.cache_max_size // 5
                    for _ in range(remove_count):
                        self.cache.pop(next(iter(self.cache)), None)
                
                self.cache[address] = balance
            
            return balance
        except Exception as e:
            return None
    
    def check_multiple_addresses(self, addresses: List[str]) -> Dict[str, int]:
        """Check multiple addresses at once (optimized)"""
        results = {}
        uncached = []
        
        if self.cache_enabled:
            for addr in addresses:
                if addr in self.cache:
                    if self.cache[addr] is not None:
                        results[addr] = self.cache[addr]
                else:
                    uncached.append(addr)
        else:
            uncached = addresses
        
        if uncached:
            try:
                placeholders = ','.join('?' * len(uncached))
                query = f'SELECT address, balance FROM btc_addresses WHERE address IN ({placeholders})'
                self.cursor.execute(query, uncached)
                
                for addr, balance in self.cursor.fetchall():
                    results[addr] = balance
                    if self.cache_enabled:
                        if len(self.cache) >= self.cache_max_size:
                            remove_count = self.cache_max_size // 5
                            for _ in range(remove_count):
                                self.cache.pop(next(iter(self.cache)), None)
                        self.cache[addr] = balance
                
                if self.cache_enabled:
                    for addr in uncached:
                        if addr not in results:
                            if len(self.cache) < self.cache_max_size:
                                self.cache[addr] = None
            except Exception as e:
                pass
        
        return results
    
    def get_address_count(self) -> int:
        """Get total number of addresses in database"""
        try:
            self.cursor.execute('SELECT COUNT(*) FROM btc_addresses')
            result = self.cursor.fetchone()
            return result[0] if result else 0
        except Exception as e:
            return 0
    
    def get_total_balance(self) -> int:
        """Get total balance of all addresses in satoshis"""
        try:
            self.cursor.execute('SELECT SUM(balance) FROM btc_addresses')
            result = self.cursor.fetchone()
            return result[0] if result and result[0] else 0
        except Exception as e:
            return 0
    
    def get_statistics(self) -> Dict:
        """Get database statistics"""
        try:
            stats = {
                'total_addresses': self.get_address_count(),
                'total_balance_satoshis': self.get_total_balance()
            }
            stats['total_balance_btc'] = stats['total_balance_satoshis'] / 100000000
            stats['cache_size'] = len(self.cache) if self.cache_enabled else 0
            return stats
        except Exception as e:
            return {}
            
    def clear_cache(self):
        """Clear the cache to free memory"""
        self.cache.clear()
        self.cache_hits = 0
        self.cache_misses = 0
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


def find_database_source_file() -> Optional[str]:
    """Find available database source file (TXT or TSV) - TXT has priority"""
    # Check in current directory
    current_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
    
    txt_path = os.path.join(current_dir, BTC_TXT_FILE)
    tsv_path = os.path.join(current_dir, BTC_TSV_FILE)
    
    if os.path.exists(txt_path):
        return txt_path
    elif os.path.exists(tsv_path):
        return tsv_path
    else:
        # Try also without path
        if os.path.exists(BTC_TXT_FILE):
            return BTC_TXT_FILE
        elif os.path.exists(BTC_TSV_FILE):
            return BTC_TSV_FILE
        return None


def detect_and_parse_txt_format(file_path: str, sample_lines: int = 50) -> dict:
    """Intelligently detect TXT/TSV file format and return parsing configuration"""
    print("\n" + "="*70)
    print("ANALYZING FILE FORMAT")
    print("="*70)
    print(f"[*] Reading first {sample_lines} lines for analysis...\n")
    
    try:
        lines = []
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for i, line in enumerate(f):
                if i >= sample_lines:
                    break
                line = line.strip()
                if line:
                    lines.append(line)
        
        if not lines:
            print("[!] File is empty or unreadable")
            return None
        
        print(f"[+] Successfully read {len(lines)} sample lines")
        
        print("\n" + "="*70)
        print("SAMPLE DATA FROM FILE:")
        print("="*70)
        for i, line in enumerate(lines[:5], 1):
            display_line = line[:100] + "..." if len(line) > 100 else line
            print(f"{i}. {display_line}")
        print("="*70 + "\n")
        
        # Detect separator
        separators = [
            ('\t', 'TAB'),
            (',', 'COMMA'),
            (';', 'SEMICOLON'),
            ('|', 'PIPE'),
            ('  ', 'DOUBLE-SPACE'),
            (' ', 'SPACE')
        ]
        
        detected_sep = None
        sep_name = None
        
        sep_counts = {}
        for sep, name in separators:
            count = lines[0].count(sep)
            if count > 0:
                sep_counts[sep] = (count, name)
        
        if sep_counts:
            best_sep = None
            best_score = 0
            
            for sep, (count, name) in sep_counts.items():
                consistency = sum(1 for line in lines[:10] if line.count(sep) == count)
                if consistency > best_score:
                    best_score = consistency
                    best_sep = sep
                    sep_name = name
            
            if best_sep and best_score >= 5:
                detected_sep = best_sep
                print(f"[+] Detected separator: {sep_name}")
                print(f"[+] Consistency: {best_score}/{min(10, len(lines))} lines")
        
        if not detected_sep:
            print("[!] No consistent separator detected")
            print("[*] Trying single-column mode...")
            detected_sep = None
        
        if detected_sep:
            columns = lines[0].split(detected_sep)
            print(f"[+] Detected {len(columns)} columns\n")
            
            print("="*70)
            print("COLUMN ANALYSIS:")
            print("="*70)
            
            column_types = []
            for i, col in enumerate(columns):
                col_clean = col.strip()
                
                is_address = False
                if col_clean:
                    if (col_clean.startswith('1') and 26 <= len(col_clean) <= 35 and col_clean.isalnum()):
                        is_address = True
                    elif (col_clean.startswith('3') and 26 <= len(col_clean) <= 35 and col_clean.isalnum()):
                        is_address = True
                    elif (col_clean.startswith('bc1') and 42 <= len(col_clean) <= 62):
                        is_address = True
                    elif (col_clean.startswith('tb1')):
                        is_address = True
                
                is_balance = col_clean.isdigit() and len(col_clean) >= 4
                is_timestamp = any(x in col_clean.lower() for x in ['2019', '2020', '2021', '2022', '2023', '2024', '-', '/'])
                
                if is_address:
                    col_type = "ADDRESS"
                elif is_balance:
                    col_type = "BALANCE"
                elif is_timestamp:
                    col_type = "DATE/TIME"
                elif col_clean.isdigit():
                    col_type = "NUMBER (ID?)"
                elif col_clean.isalpha():
                    col_type = "TEXT/TYPE"
                else:
                    col_type = "UNKNOWN"
                
                column_types.append(col_type)
                
                display_col = col_clean[:50] + "..." if len(col_clean) > 50 else col_clean
                print(f"  Column {i}: {display_col}")
                print(f"             â†’ Type: {col_type}")
            
            print("="*70 + "\n")
            
            address_col = None
            balance_col = None
            
            for i, col_type in enumerate(column_types):
                if col_type == "ADDRESS" and address_col is None:
                    address_col = i
                elif col_type == "BALANCE" and balance_col is None:
                    balance_col = i
            
            if address_col is not None:
                valid_count = 0
                for line in lines[:20]:
                    parts = line.split(detected_sep)
                    if address_col < len(parts):
                        addr = parts[address_col].strip()
                        if (addr.startswith('1') or addr.startswith('3') or 
                            addr.startswith('bc1') or addr.startswith('tb1')):
                            valid_count += 1
                
                print(f"[*] Address column validation: {valid_count}/20 lines valid")
                
                if valid_count < 15:
                    print("[!] Address column validation failed, may be incorrect")
                    address_col = None
            
            has_header = False
            if lines:
                first_line = lines[0].lower()
                header_keywords = ['address', 'balance', 'wallet', 'amount', 'value', 'btc', 'satoshi']
                has_header = any(keyword in first_line for keyword in header_keywords)
            
            if has_header:
                print("[+] Detected header row in first line")
            
            if address_col is not None and balance_col is not None:
                print("\n" + "="*70)
                print("AUTO-DETECTED CONFIGURATION:")
                print("="*70)
                print(f"  Separator: {sep_name}")
                print(f"  Address column: {address_col}")
                print(f"  Balance column: {balance_col}")
                print(f"  Has header: {has_header}")
                print("="*70 + "\n")
                
                response = input("[?] Use auto-detected format? (y/n/m for manual): ").lower()
                
                if response == 'y':
                    return {
                        'separator': detected_sep,
                        'address_column': address_col,
                        'balance_column': balance_col,
                        'has_header': has_header
                    }
                elif response == 'm':
                    pass
                else:
                    print("[!] Conversion cancelled")
                    return None
            else:
                print("\n[!] Could not auto-detect address and balance columns")
                print("[*] Please specify manually")
            
            print("\n" + "="*70)
            print("MANUAL CONFIGURATION:")
            print("="*70)
            
            try:
                addr_col = input("Address column index (0-based): ").strip()
                bal_col = input("Balance column index (0-based, or 'none' if no balance): ").strip()
                has_header_input = input("First line is header? (y/n): ").strip().lower() == 'y'
                
                addr_col_int = int(addr_col)
                bal_col_int = int(bal_col) if bal_col.lower() != 'none' else None
                
                return {
                    'separator': detected_sep,
                    'address_column': addr_col_int,
                    'balance_column': bal_col_int,
                    'has_header': has_header_input
                }
            except Exception as e:
                print(f"[!] Invalid input: {e}")
                return None
        else:
            print("\n" + "="*70)
            print("SINGLE COLUMN DETECTED")
            print("="*70)
            
            address_count = 0
            for line in lines[:20]:
                if (line.startswith('1') or line.startswith('3') or 
                    line.startswith('bc1') or line.startswith('tb1')):
                    address_count += 1
            
            if address_count >= 15:
                print(f"[+] Detected {address_count}/20 lines are Bitcoin addresses")
                print("[*] Will import addresses with balance = 0")
                
                response = input("\n[?] Proceed with addresses-only mode? (y/n): ")
                
                if response.lower() == 'y':
                    return {
                        'separator': None,
                        'address_column': 0,
                        'balance_column': None,
                        'has_header': False
                    }
            else:
                print("[!] Could not identify column content")
                print("[!] Expected Bitcoin addresses starting with 1, 3, or bc1")
            
            return None
    
    except Exception as e:
        print(f"[!] Error analyzing file: {e}")
        import traceback
        traceback.print_exc()
        return None


def convert_txt_to_sqlite_with_validation(txt_file: str, db_file: str):
    """Convert TXT/TSV with validation and formatting"""
    format_config = detect_and_parse_txt_format(txt_file)
    
    if not format_config:
        print("\n[!] Could not detect file format")
        return False
    
    print(f"\n[+] Using configuration:")
    print(f"    Separator: {format_config['separator']}")
    print(f"    Address column: {format_config['address_column']}")
    print(f"    Balance column: {format_config['balance_column']}")
    print(f"    Has header: {format_config['has_header']}")
    
    response = input("\n[?] Proceed with conversion? (y/n): ")
    if response.lower() != 'y':
        print("[!] Conversion cancelled")
        return False
    
    return perform_conversion(txt_file, db_file, format_config)


def convert_txt_to_sqlite_direct(txt_file: str, db_file: str):
    """Direct conversion without validation - assumes TAB separated address<TAB>balance"""
    print("\n" + "="*70)
    print("DIRECT CONVERSION (NO VALIDATION)")
    print("="*70)
    print("[*] Assuming format: address<TAB>balance")
    print("[*] No validation or cleaning will be performed")
    print("="*70 + "\n")
    
    response = input("[?] Proceed with direct conversion? (y/n): ")
    if response.lower() != 'y':
        print("[!] Conversion cancelled")
        return False
    
    format_config = {
        'separator': '\t',
        'address_column': 0,
        'balance_column': 1,
        'has_header': False
    }
    
    return perform_conversion(txt_file, db_file, format_config, validate=False)


def perform_conversion(txt_file: str, db_file: str, format_config: dict, validate: bool = True):
    """Perform the actual conversion"""
    if os.path.exists(db_file):
        print(f"\n[*] Removing existing database '{db_file}'...")
        os.remove(db_file)
    
    print(f"[*] Creating new database '{db_file}'...")
    db = DatabaseManager(db_file)
    
    if not db.connect():
        return False
    
    if not db.create_table():
        db.close()
        return False
    
    print(f"[*] Reading and parsing '{txt_file}'...")
    
    try:
        total_addresses = 0
        total_balance = 0
        batch_size = 10000
        batch = []
        skipped = 0
        
        with open(txt_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                if not line:
                    continue
                
                if format_config['has_header'] and line_num == 1:
                    print(f"[*] Skipping header line")
                    continue
                
                try:
                    if format_config['separator']:
                        parts = line.split(format_config['separator'])
                    else:
                        parts = [line]
                    
                    if format_config['address_column'] < len(parts):
                        address = parts[format_config['address_column']].strip()
                    else:
                        skipped += 1
                        continue
                    
                    if validate:
                        if not (address.startswith('1') or address.startswith('3') or 
                               address.startswith('bc1') or address.startswith('tb1')):
                            skipped += 1
                            continue
                    
                    if format_config['balance_column'] is not None:
                        if format_config['balance_column'] < len(parts):
                            balance_str = parts[format_config['balance_column']].strip()
                            balance_str = ''.join(c for c in balance_str if c.isdigit())
                            try:
                                balance = int(balance_str) if balance_str else 0
                            except ValueError:
                                skipped += 1
                                continue
                        else:
                            skipped += 1
                            continue
                    else:
                        balance = 0
                    
                    batch.append((address, balance))
                    total_balance += balance
                    
                    if len(batch) >= batch_size:
                        db.cursor.executemany(
                            'INSERT OR REPLACE INTO btc_addresses (address, balance) VALUES (?, ?)',
                            batch
                        )
                        db.conn.commit()
                        total_addresses += len(batch)
                        batch = []
                        
                        if line_num % 100000 == 0:
                            print(f"[*] Processed {line_num:,} lines, {total_addresses:,} addresses inserted, {skipped:,} skipped...")
                
                except Exception as e:
                    skipped += 1
                    continue
            
            if batch:
                db.cursor.executemany(
                    'INSERT OR REPLACE INTO btc_addresses (address, balance) VALUES (?, ?)',
                    batch
                )
                db.conn.commit()
                total_addresses += len(batch)
        
        final_count = db.get_address_count()
        final_balance = db.get_total_balance()
        
        print(f"\n{'='*70}")
        print(f"âœ… CONVERSION COMPLETED!")
        print(f"{'='*70}")
        print(f"Total lines processed: {line_num:,}")
        print(f"Addresses inserted: {final_count:,}")
        print(f"Lines skipped: {skipped:,}")
        print(f"Total balance: {final_balance:,} satoshis ({final_balance/100000000:.8f} BTC)")
        print(f"Database file: {db_file}")
        print(f"Database size: {os.path.getsize(db_file) / (1024*1024):.2f} MB")
        print(f"{'='*70}\n")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"\n[!] Error during conversion: {e}")
        import traceback
        traceback.print_exc()
        db.close()
        return False


def convert_database_menu():
    """Menu for database conversion with scan/direct options"""
    source_file = find_database_source_file()
    
    if not source_file:
        print("\n[!] No database source file found!")
        print(f"[!] Please create one of these files:")
        print(f"    - {BTC_TXT_FILE} (priority)")
        print(f"    - {BTC_TSV_FILE}")
        print("[!] Format: address<TAB>balance_in_satoshis\n")
        return False
    
    print(f"\n[+] Found source file: {source_file}")
    
    file_size_mb = os.path.getsize(source_file) / (1024 * 1024)
    print(f"[+] File size: {file_size_mb:.2f} MB")
    
    if file_size_mb > 500:
        print("[!] WARNING: Large file detected!")
        print("[!] This may take several minutes...")
    
    print("\n" + "="*70)
    print("CONVERSION MODE:")
    print("="*70)
    print("[1] Scan and Validate (Recommended)")
    print("    - Analyzes file format")
    print("    - Validates addresses")
    print("    - Cleans data before conversion")
    print("    - Slower but safer")
    print()
    print("[2] Direct Conversion (Fast)")
    print("    - No validation")
    print("    - Assumes: address<TAB>balance")
    print("    - Much faster")
    print("    - May import invalid data")
    print("="*70)
    
    mode = input("\nChoose conversion mode (1/2): ").strip()
    
    if mode == '1':
        return convert_txt_to_sqlite_with_validation(source_file, BTC_DATABASE_FILE)
    elif mode == '2':
        return convert_txt_to_sqlite_direct(source_file, BTC_DATABASE_FILE)
    else:
        print("[!] Invalid choice")
        return False


def check_balance_online(address: str) -> Optional[float]:
    """Check Bitcoin address balance via multiple blockchain APIs with rate limiting"""
    global LAST_API_CALL
    
    if not HAS_REQUESTS:
        return None
    
    # Rate limiting: attendi tra chiamate per evitare ban
    current_time = time.time()
    time_since_last = current_time - LAST_API_CALL
    if time_since_last < API_CALL_DELAY:
        time.sleep(API_CALL_DELAY - time_since_last)
    
    LAST_API_CALL = time.time()
    
    # Lista di API da provare in ordine (le più affidabili prima)
    apis = [
        {
            'name': 'Blockstream',
            'url': f"https://blockstream.info/api/address/{address}",
            'parse': lambda r: (r.json().get('chain_stats', {}).get('funded_txo_sum', 0) - 
                               r.json().get('chain_stats', {}).get('spent_txo_sum', 0)) / 100000000
        },
        {
            'name': 'Mempool.space',
            'url': f"https://mempool.space/api/address/{address}",
            'parse': lambda r: (r.json().get('chain_stats', {}).get('funded_txo_sum', 0) - 
                               r.json().get('chain_stats', {}).get('spent_txo_sum', 0)) / 100000000
        },
        {
            'name': 'Blockchain.info',
            'url': f"https://blockchain.info/q/addressbalance/{address}",
            'parse': lambda r: int(r.text) / 100000000 if r.text.isdigit() else None
        },
        {
            'name': 'BlockCypher',
            'url': f"https://api.blockcypher.com/v1/btc/main/addrs/{address}/balance",
            'parse': lambda r: r.json().get('final_balance', 0) / 100000000
        }
    ]
    
    # Prova ogni API con retry automatico
    for api in apis:
        for retry in range(2):
            try:
                response = requests.get(api['url'], timeout=15)
                
                if response.status_code == 200:
                    balance = api['parse'](response)
                    if balance is not None:
                        return balance
                
                elif response.status_code == 429:
                    if retry == 0:
                        time.sleep(3)
                        continue
                    else:
                        break
                
                else:
                    break
                
            except requests.exceptions.Timeout:
                if retry == 0:
                    time.sleep(2)
                    continue
                break
            except requests.exceptions.RequestException:
                break
            except (ValueError, KeyError, TypeError):
                break

    return None


class BitcoinWalletGenerator:
    """Bitcoin Wallet Generator with Advanced Passphrase Support"""
    
    def __init__(self):
        self.db = None
        self.passphrase_gen = PassphraseGenerator()
        if HAS_MNEMONIC:
            self.mnemo = Mnemonic("english")
        
        self.load_database()
        
        self.stats = {
            'seeds_tested': 0,
            'passphrases_tested': 0,
            'total_addresses_checked': 0,
            'matches_found': 0
        }
    
    def load_database(self):
        """Load SQLite database"""
        if not os.path.exists(BTC_DATABASE_FILE):
            print(f"[!] Database '{BTC_DATABASE_FILE}' not found")
            
            source_file = find_database_source_file()
            if source_file:
                print(f"[+] Found source file: {source_file}")
                print(f"[!] Use option [6] to convert it to SQLite database")
            else:
                print(f"[!] No source file found. Create one of these:")
                print(f"    - {BTC_TXT_FILE} (priority)")
                print(f"    - {BTC_TSV_FILE}")
            print()
            return
        
        try:
            print(f"[+] Loading Bitcoin addresses database from {BTC_DATABASE_FILE}...")
            self.db = DatabaseManager(BTC_DATABASE_FILE)
            
            if self.db.connect():
                stats = self.db.get_statistics()
                print(f"[+] {stats['total_addresses']:,} Bitcoin addresses in database")
                print(f"[+] Total balance: {stats['total_balance_btc']:.8f} BTC\n")
            else:
                self.db = None
        except Exception as e:
            print(f"[!] Error loading database: {e}\n")
            self.db = None
    
    def generate_mnemonic(self) -> str:
        """Generate a random 12-word BIP39 seed phrase"""
        if HAS_MNEMONIC:
            return self.mnemo.generate(strength=128)
        else:
            return "abandon " * 11 + "about"
    
    def generate_btc_wallet(self, mnemonic: Optional[str] = None, passphrase: str = "") -> dict:
        """Generate a complete Bitcoin wallet with optional passphrase"""
        if not mnemonic:
            mnemonic = self.generate_mnemonic()
        
        if not HAS_BITCOINLIB:
            return self.generate_btc_wallet_simple(mnemonic, passphrase)
        
        try:
            hd_key = HDKey.from_passphrase(mnemonic, passphrase=passphrase)
            child_key = hd_key.subkey_for_path("m/44'/0'/0'/0/0")
            
            legacy_address = child_key.address()
            
            try:
                segwit_address = child_key.address(encoding='bech32')
            except:
                segwit_address = "N/A"
            
            try:
                p2sh_address = child_key.address(encoding='p2sh')
            except:
                p2sh_address = "N/A"
            
            return {
                'mnemonic': mnemonic,
                'passphrase': passphrase,
                'private_key': child_key.private_hex,
                'public_key': child_key.public_hex,
                'legacy_address': legacy_address,
                'segwit_address': segwit_address,
                'p2sh_address': p2sh_address,
                'wif': child_key.wif()
            }
        except Exception as e:
            return self.generate_btc_wallet_simple(mnemonic, passphrase)
    
    def generate_btc_wallet_simple(self, mnemonic: str, passphrase: str = "") -> dict:
        """Generate simplified Bitcoin wallet (fallback)"""
        combined = f"{mnemonic}:{passphrase}"
        private_key = hashlib.sha256(combined.encode()).digest()
        private_key_hex = private_key.hex()
        
        address_hash = hashlib.sha256(private_key).hexdigest()[:34]
        address = "1" + address_hash
        
        return {
            'mnemonic': mnemonic,
            'passphrase': passphrase,
            'private_key': private_key_hex,
            'legacy_address': address,
            'segwit_address': 'N/A (install bitcoinlib)',
            'p2sh_address': 'N/A (install bitcoinlib)',
            'note': 'Simplified mode'
        }
    
    def generate_and_check_balance(self):
        """Generate wallet and check balance with single/continuous mode"""
        print("\n" + "="*70)
        print("GENERATE WALLET & CHECK BALANCE")
        print("="*70)
        print("[1] Generate Single Wallet")
        print("    - Generate one wallet")
        print("    - Check balance online")
        print("    - Display results")
        print()
        print("[2] Continuous Generation")
        print("    - Generate wallets in loop")
        print("    - Check each balance online")
        print("    - Save wallets with balance > 0")
        print("    - Press CTRL+C to stop")
        print("="*70)
        
        mode = input("\nChoose mode (1/2): ").strip()
        
        if mode == '1':
            self.generate_single_wallet_with_balance()
        elif mode == '2':
            self.generate_continuous_with_balance()
        else:
            print("[!] Invalid choice\n")
    
    def generate_single_wallet_with_balance(self):
        """Generate a single wallet and check its balance"""
        print("\n[*] Generating wallet...")
        
        wallet = self.generate_btc_wallet()
        
        if not wallet:
            print("[!] Failed to generate wallet\n")
            return
        
        print("\n" + "="*70)
        print("WALLET GENERATED")
        print("="*70)
        print(f"Mnemonic: {wallet['mnemonic']}")
        print(f"Legacy Address: {wallet['legacy_address']}")
        if wallet.get('segwit_address') and wallet['segwit_address'] != "N/A":
            print(f"SegWit Address: {wallet['segwit_address']}")
        if wallet.get('p2sh_address') and wallet['p2sh_address'] != "N/A":
            print(f"P2SH Address: {wallet['p2sh_address']}")
        print("="*70)
        
        if not HAS_REQUESTS:
            print("\n[!] Module 'requests' not installed - cannot check balance online")
            print("[!] Install with: pip install requests")
            print("[*] Wallet generated successfully but balance check skipped\n")
            return
        
        print("\n[*] Checking balance online...")
        
        addresses_to_check = []
        if wallet['legacy_address']:
            addresses_to_check.append(('Legacy', wallet['legacy_address']))
        if wallet.get('segwit_address') and wallet['segwit_address'] != "N/A":
            addresses_to_check.append(('SegWit', wallet['segwit_address']))
        if wallet.get('p2sh_address') and wallet['p2sh_address'] != "N/A":
            addresses_to_check.append(('P2SH', wallet['p2sh_address']))
        
        total_balance = 0
        found_balance = False
        
        for addr_type, addr in addresses_to_check:
            balance = check_balance_online(addr)
            if balance is not None:
                print(f"  {addr_type}: {balance:.8f} BTC")
                total_balance += balance
                if balance > 0:
                    found_balance = True
            else:
                print(f"  {addr_type}: Unable to check (API error)")
            time.sleep(0.5)
        
        print(f"\nTotal Balance: {total_balance:.8f} BTC")
        
        if found_balance:
            print("\n" + "="*70)
            print("WALLET WITH BALANCE FOUND!")
            print("="*70)
            self.save_generated_wallet(wallet, total_balance)
        
        print()
    
    def generate_continuous_with_balance(self):
        """Generate wallets continuously until stopped"""
        if not HAS_REQUESTS:
            print("\n[!] Module 'requests' not installed - cannot check balance online")
            print("[!] Install with: pip install requests\n")
            return
        
        print("\n" + "="*70)
        print("CONTINUOUS WALLET GENERATION")
        print("="*70)
        print("[*] Generating wallets continuously...")
        print("[*] Checking balance for each wallet...")
        print("[*] Wallets with balance > 0 will be saved")
        print("[*] Press CTRL+C to stop")
        print("="*70 + "\n")
        
        attempts = 0
        found_count = 0
        start_time = time.time()
        last_update = start_time
        
        try:
            while True:
                attempts += 1
                
                wallet = self.generate_btc_wallet()
                
                if not wallet:
                    continue
                
                main_address = wallet['legacy_address']
                balance = check_balance_online(main_address)
                
                if balance is not None and balance > 0:
                    found_count += 1
                    
                    print(f"\n{'='*70}")
                    print(f"WALLET #{found_count} WITH BALANCE FOUND!")
                    print(f"{'='*70}")
                    print(f"Address: {main_address}")
                    print(f"Balance: {balance:.8f} BTC")
                    print(f"Attempts: {attempts:,}")
                    print(f"{'='*70}\n")
                    
                    self.save_generated_wallet(wallet, balance)
                
                current_time = time.time()
                if current_time - last_update >= 2.0:
                    elapsed = current_time - start_time
                    speed = attempts / elapsed if elapsed > 0 else 0
                    
                    print(f"\r[*] Attempts: {attempts:,} | Speed: {speed:.2f}/s | Found: {found_count} | Last: {main_address[:20]}...", 
                          end='', flush=True)
                    last_update = current_time
                
                time.sleep(0.5)
        
        except KeyboardInterrupt:
            elapsed = time.time() - start_time
            print(f"\n\n{'='*70}")
            print("[!] Generation stopped by user")
            print(f"{'='*70}")
            print(f"Total attempts: {attempts:,}")
            print(f"Wallets with balance found: {found_count}")
            print(f"Time elapsed: {elapsed:.2f} seconds")
            print(f"Average speed: {attempts/elapsed:.2f} wallets/s")
            print(f"{'='*70}\n")
    
    def save_generated_wallet(self, wallet: dict, balance: float):
        """Save generated wallet with balance to file"""
        try:
            with open(GEN_WALLETS_FILE, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*70}\n")
                f.write(f"GENERATED WALLET WITH BALANCE - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"{'='*70}\n")
                f.write(f"Balance: {balance:.8f} BTC\n")
                f.write(f"{'-'*70}\n")
                f.write(f"Seed Phrase (Mnemonic): {wallet['mnemonic']}\n")
                f.write(f"Private Key (Hex): {wallet['private_key']}\n")
                if 'wif' in wallet and wallet['wif']:
                    f.write(f"Private Key (WIF): {wallet['wif']}\n")
                f.write(f"\nAddresses:\n")
                f.write(f"  Legacy: {wallet['legacy_address']}\n")
                if wallet.get('segwit_address') and wallet['segwit_address'] != "N/A":
                    f.write(f"  SegWit: {wallet['segwit_address']}\n")
                if wallet.get('p2sh_address') and wallet['p2sh_address'] != "N/A":
                    f.write(f"  P2SH: {wallet['p2sh_address']}\n")
                f.write(f"{'='*70}\n")
            
            print(f"[+] Wallet saved to {GEN_WALLETS_FILE}")
        except Exception as e:
            print(f"[!] Error saving wallet: {e}")
    
    def check_wallet_addresses(self, wallet: dict) -> Dict:
        """Check if any wallet addresses are in database (optimized)"""
        if not self.db:
            return {}
        
        addresses = []
        addr_types = {}
        
        for addr_type in ['legacy_address', 'segwit_address', 'p2sh_address']:
            address = wallet.get(addr_type)
            if address and address != "N/A" and not address.startswith('N/A'):
                addresses.append(address)
                addr_types[address] = addr_type
        
        results = self.db.check_multiple_addresses(addresses)
        
        matches = {}
        for address, balance in results.items():
            if balance is not None:
                matches[addr_types[address]] = {
                    'address': address,
                    'balance_satoshis': balance,
                    'balance_btc': balance / 100000000
                }
        
        return matches
    
    def save_found_wallet(self, wallet_data: dict, matches: Dict):
        """Save a wallet found with matching addresses in database"""
        try:
            total_balance_satoshis = sum(m['balance_satoshis'] for m in matches.values())
            total_balance_btc = total_balance_satoshis / 100000000
            
            with open(FOUND_WALLETS_FILE, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*70}\n")
                f.write(f"WALLET FOUND IN DATABASE! - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"{'='*70}\n")
                f.write(f"Total Balance: {total_balance_btc:.8f} BTC ({total_balance_satoshis:,} satoshis)\n")
                f.write(f"{'-'*70}\n")
                
                f.write(f"Mnemonic: {wallet_data.get('mnemonic', 'N/A')}\n")
                passphrase = wallet_data.get('passphrase', '')
                if passphrase:
                    f.write(f"Passphrase: {passphrase}\n")
                f.write(f"Private Key: {wallet_data.get('private_key', 'N/A')}\n")
                if 'wif' in wallet_data:
                    f.write(f"WIF: {wallet_data.get('wif', 'N/A')}\n")
                
                f.write(f"\n{'-'*70}\n")
                f.write("Matching Addresses in Database:\n")
                f.write(f"{'-'*70}\n")
                
                for addr_type, data in matches.items():
                    f.write(f"\n{addr_type}:\n")
                    f.write(f"  Address: {data['address']}\n")
                    f.write(f"  Balance: {data['balance_btc']:.8f} BTC ({data['balance_satoshis']:,} satoshis)\n")
                
                f.write(f"\n{'='*70}\n")
            
            print("\n" + "="*70)
            print("WALLET FOUND IN DATABASE!")
            print("="*70)
            print(f"Total Balance: {total_balance_btc:.8f} BTC")
            if wallet_data.get('passphrase'):
                print(f"‘Passphrase: {wallet_data['passphrase']}")
            print(f"{'-'*70}")
            
            for addr_type, data in matches.items():
                print(f"\n{addr_type}:")
                print(f"  Address: {data['address']}")
                print(f"  Balance: {data['balance_btc']:.8f} BTC")
            
            print(f"\n{'='*70}")
            print(f"’Details saved in: {FOUND_WALLETS_FILE}")
            print("="*70 + "\n")
        except Exception as e:
            print(f"[!] Error saving wallet: {e}")
    
    def search_basic(self):
        """Basic search without passphrase variations"""
        if not self.db:
            print("[!] Database not loaded!\n")
            return
    
        stats = self.db.get_statistics()
    
        print("\n" + "="*70)
        print("BASIC SEARCH (No Passphrase)")
        print("="*70)
        print(f"Addresses in database: {stats['total_addresses']:,}")
        print(f"Total database balance: {stats['total_balance_btc']:.8f} BTC")
        print("[*] Testing only empty passphrase (most common)")
        print("[*] Use option [3] for advanced passphrase attack")
        print("[*] Press CTRL+C to stop")
        print("="*70 + "\n")
    
        attempts = 0
        start_time = time.time()
        last_update = start_time
        last_cache_clear = start_time
        found = 0
    
        try:
            while True:
                wallet = self.generate_btc_wallet()
                
                if not wallet:
                    continue
                
                attempts += 1
                
                matches = self.check_wallet_addresses(wallet)
                
                if matches:
                    found += 1
                    print(f"\nMATCH FOUND!")
                    self.save_found_wallet(wallet, matches)
                    
                    response = input("\n[?] Continue? (y/n): ")
                    if response.lower() != 'y':
                        return
                    
                    start_time = time.time()
                    last_update = start_time
                
                current_time = time.time()
                if current_time - last_cache_clear >= 300:
                    self.db.clear_cache()
                    last_cache_clear = current_time
                if current_time - last_update >= 1.0:
                    elapsed = current_time - start_time
                    speed = int(attempts / elapsed) if elapsed > 0 else 0
                    
                    print(f"\r[*] Attempts: {attempts:,} | Speed: ~{speed:,}/s | Found: {found}", 
                          end='', flush=True)
                    last_update = current_time
        
        except KeyboardInterrupt:
            elapsed = time.time() - start_time
            print(f"\n\n[!] Search stopped")
            print(f"[*] Attempts: {attempts:,}")
            print(f"[*] Found: {found}")
            print(f"[*] Time: {elapsed:.2f}s")
            print(f"[*] Speed: {int(attempts/elapsed) if elapsed > 0 else 0:,}/s\n")
    
    def search_with_passphrase_attack(self):
        """Advanced search with passphrase variations"""
        if not self.db:
            print("[!] Database not loaded!\n")
            return
        
        stats = self.db.get_statistics()
        
        print("\n" + "="*70)
        print("ADVANCED SEARCH WITH PASSPHRASE ATTACK")
        print("="*70)
        print(f"Addresses in database: {stats['total_addresses']:,}")
        print(f"Total database balance: {stats['total_balance_btc']:.8f} BTC")
        print(f"Passphrases per seed: {PASSPHRASE_CONFIG['max_per_seed']}")
        print(f"Strategies: {', '.join(PASSPHRASE_CONFIG['strategies'])}")
        print("\n[*] This will test MULTIPLE passphrases for each seed!")
        print("[*] Press CTRL+C to stop")
        print("="*70 + "\n")
        
        self.stats = {
            'seeds_tested': 0,
            'passphrases_tested': 0,
            'total_addresses_checked': 0,
            'matches_found': 0
        }
        
        start_time = time.time()
        last_update = start_time
        
        try:
            while True:
                mnemonic = self.generate_mnemonic()
                seed_words = mnemonic.split()
                
                self.stats['seeds_tested'] += 1
                
                passphrases = self.passphrase_gen.get_passphrases_for_seed(
                    seed_words,
                    strategy='all',
                    max_count=PASSPHRASE_CONFIG['max_per_seed']
                )
                
                for passphrase in passphrases:
                    wallet = self.generate_btc_wallet(mnemonic, passphrase)
                    
                    if not wallet:
                        continue
                    
                    self.stats['passphrases_tested'] += 1
                    
                    matches = self.check_wallet_addresses(wallet)
                    self.stats['total_addresses_checked'] += 3
                    
                    if matches:
                        self.stats['matches_found'] += 1
                        print(f"\n{'='*70}")
                        print(f"MATCH FOUND!")
                        print(f"{'='*70}")
                        print(f"Seeds tested: {self.stats['seeds_tested']:,}")
                        print(f"Passphrases tested: {self.stats['passphrases_tested']:,}")
                        if passphrase:
                            print(f"Passphrase used: '{passphrase}'")
                        
                        self.save_found_wallet(wallet, matches)
                        
                        response = input("\n[?] Continue searching? (y/n): ")
                        if response.lower() != 'y':
                            return
                        
                        start_time = time.time()
                        last_update = start_time
                
                current_time = time.time()
                if current_time - last_update >= 1.0:
                    elapsed = current_time - start_time
                    seed_speed = int(self.stats['seeds_tested'] / elapsed) if elapsed > 0 else 0
                    pass_speed = int(self.stats['passphrases_tested'] / elapsed) if elapsed > 0 else 0
                    
                    print(f"\r[*] Seeds: {self.stats['seeds_tested']:,} ({seed_speed}/s) | "
                          f"Passphrases: {self.stats['passphrases_tested']:,} ({pass_speed}/s) | "
                          f"Found: {self.stats['matches_found']}", end='', flush=True)
                    last_update = current_time
        
        except KeyboardInterrupt:
            elapsed = time.time() - start_time
            print(f"\n\n{'='*70}")
            print("[!] Search stopped by user")
            print(f"{'='*70}")
            print(f"Seeds tested: {self.stats['seeds_tested']:,}")
            print(f"Passphrases tested: {self.stats['passphrases_tested']:,}")
            print(f"Total addresses checked: {self.stats['total_addresses_checked']:,}")
            print(f"Matches found: {self.stats['matches_found']}")
            print(f"Time elapsed: {elapsed:.2f} seconds")
            print(f"Average seed speed: {int(self.stats['seeds_tested']/elapsed) if elapsed > 0 else 0:,}/s")
            print(f"Average passphrase speed: {int(self.stats['passphrases_tested']/elapsed) if elapsed > 0 else 0:,}/s")
            print(f"{'='*70}\n")
    
    def target_specific_address(self):
        """Target a specific Bitcoin address with seed and passphrase bruteforce"""
        print("\n" + "="*70)
        print("TARGET SPECIFIC ADDRESS ATTACK")
        print("="*70)
        print("This will bruteforce a specific Bitcoin address")
        print("Testing both seed phrases and passphrases")
        print("="*70 + "\n")
        
        target_address = input("Enter target Bitcoin address: ").strip()
        
        if not target_address:
            print("[!] No address provided\n")
            return
        
        addr_type = None
        if target_address.startswith('1'):
            addr_type = 'legacy'
        elif target_address.startswith('3'):
            addr_type = 'p2sh'
        elif target_address.startswith('bc1'):
            addr_type = 'segwit'
        else:
            print("[!] Invalid Bitcoin address format")
            return
        
        print(f"\n[*] Target address: {target_address}")
        print(f"[*] Detected type: {addr_type}")
        
        if self.db:
            balance = self.db.check_address(target_address)
            if balance is not None:
                balance_btc = balance / 100000000
                print(f"[+] Address found in database!")
                print(f"[+] Balance: {balance_btc:.8f} BTC ({balance:,} satoshis)")
            else:
                print("[*] Address not in database (will search anyway)")
        
        print("\n" + "="*70)
        print("ATTACK MODE:")
        print("[1] Seed only (no passphrase)")
        print("[2] Seed + Common passphrases")
        print("[3] Seed + Custom passphrase list")
        print("[4] Known seed + Passphrase bruteforce")
        print("="*70)
        
        mode = input("\nChoose mode: ").strip()
        
        if mode == '1':
            self.target_seed_only(target_address, addr_type)
        elif mode == '2':
            self.target_seed_with_passphrases(target_address, addr_type, use_common=True)
        elif mode == '3':
            self.target_seed_with_passphrases(target_address, addr_type, use_common=False)
        elif mode == '4':
            self.target_known_seed_passphrase_bruteforce(target_address, addr_type)
        else:
            print("[!] Invalid mode\n")
    
    def target_seed_only(self, target_address: str, addr_type: str):
        """Bruteforce target address with random seeds (no passphrase)"""
        print("\n" + "="*70)
        print("MODE 1: SEED ONLY BRUTEFORCE")
        print("="*70)
        print(f"Target: {target_address}")
        print(f"Type: {addr_type}")
        print("\n[*] Press CTRL+C to stop")
        print("="*70 + "\n")
        
        attempts = 0
        start_time = time.time()
        last_update = start_time
        
        addr_key_map = {
            'legacy': 'legacy_address',
            'p2sh': 'p2sh_address',
            'segwit': 'segwit_address'
        }
        
        try:
            while True:
                wallet = self.generate_btc_wallet()
                
                if not wallet:
                    continue
                
                attempts += 1
                
                generated_addr = wallet.get(addr_key_map.get(addr_type, 'legacy_address'))
                
                if generated_addr == target_address:
                    print(f"\n{'='*70}")
                    print("TARGET ADDRESS FOUND!")
                    print(f"{'='*70}")
                    print(f"Attempts needed: {attempts:,}")
                    print(f"Time taken: {time.time() - start_time:.2f} seconds")
                    print(f"\n{'='*70}")
                    print("WALLET DETAILS:")
                    print(f"{'='*70}")
                    print(f"Mnemonic: {wallet['mnemonic']}")
                    print(f"Private Key: {wallet['private_key']}")
                    if 'wif' in wallet:
                        print(f"WIF: {wallet['wif']}")
                    print(f"Target Address: {target_address}")
                    print(f"{'='*70}\n")
                    
                    with open(FOUND_WALLETS_FILE, 'a', encoding='utf-8') as f:
                        f.write(f"\n{'='*70}\n")
                        f.write(f"TARGET ADDRESS FOUND! - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                        f.write(f"{'='*70}\n")
                        f.write(f"Target Address: {target_address}\n")
                        f.write(f"Attempts: {attempts:,}\n")
                        f.write(f"Mnemonic: {wallet['mnemonic']}\n")
                        f.write(f"Private Key: {wallet['private_key']}\n")
                        if 'wif' in wallet:
                            f.write(f"WIF: {wallet['wif']}\n")
                        f.write(f"{'='*70}\n")
                    
                    print(f"[+] Details saved to {FOUND_WALLETS_FILE}\n")
                    return
                
                current_time = time.time()
                if current_time - last_update >= 1.0:
                    elapsed = current_time - start_time
                    speed = int(attempts / elapsed) if elapsed > 0 else 0
                    
                    print(f"\r[*] Attempts: {attempts:,} | Speed: ~{speed:,}/s | "
                          f"Last: {generated_addr[:20]}...", end='', flush=True)
                    last_update = current_time
        
        except KeyboardInterrupt:
            elapsed = time.time() - start_time
            print(f"\n\n[!] Search stopped")
            print(f"[*] Attempts: {attempts:,}")
            print(f"[*] Time: {elapsed:.2f}s")
            print(f"[*] Speed: {int(attempts/elapsed) if elapsed > 0 else 0:,}/s\n")
    
    def target_seed_with_passphrases(self, target_address: str, addr_type: str, 
                                 use_common: bool = True):
        """Bruteforce target address with seeds and passphrases"""
        print("\n" + "="*70)
        print(f"MODE {'2' if use_common else '3'}: SEED + PASSPHRASE BRUTEFORCE")
        print("="*70)
        print(f"Target: {target_address}")
        print(f"Type: {addr_type}")
        
        if use_common:
            print(f"Passphrases per seed: {PASSPHRASE_CONFIG['max_per_seed']}")
        else:
            if not os.path.exists(PASSPHRASE_FILE):
                print(f"[!] Passphrase file '{PASSPHRASE_FILE}' not found!")
                print("[!] Create it with one passphrase per line")
                return
            custom_passphrases = []
            with open(PASSPHRASE_FILE, 'r', encoding='utf-8') as f:
                custom_passphrases = [line.strip() for line in f if line.strip()]
            print(f"Loaded {len(custom_passphrases)} custom passphrases")
        
        print("\n[*] Press CTRL+C to stop")
        print("="*70 + "\n")
        
        attempts = 0
        passphrases_tested = 0
        start_time = time.time()
        last_update = start_time
        
        addr_key_map = {
            'legacy': 'legacy_address',
            'p2sh': 'p2sh_address',
            'segwit': 'segwit_address'
        }
        
        try:
            while True:
                mnemonic = self.generate_mnemonic()
                seed_words = mnemonic.split()
                attempts += 1
                
                if use_common:
                    passphrases = self.passphrase_gen.get_passphrases_for_seed(
                        seed_words,
                        strategy='all',
                        max_count=PASSPHRASE_CONFIG['max_per_seed']
                    )
                else:
                    passphrases = custom_passphrases
                
                for passphrase in passphrases:
                    wallet = self.generate_btc_wallet(mnemonic, passphrase)
                    
                    if not wallet:
                        continue
                    
                    passphrases_tested += 1
                    
                    generated_addr = wallet.get(addr_key_map.get(addr_type, 'legacy_address'))
                    
                    if generated_addr == target_address:
                        print(f"\n{'='*70}")
                        print("TARGET ADDRESS FOUND!")
                        print(f"{'='*70}")
                        print(f"Seeds tested: {attempts:,}")
                        print(f"Passphrases tested: {passphrases_tested:,}")
                        print(f"Passphrase: '{passphrase}'")
                        print(f"Time taken: {time.time() - start_time:.2f} seconds")
                        print(f"\n{'='*70}")
                        print("WALLET DETAILS:")
                        print(f"{'='*70}")
                        print(f"Mnemonic: {wallet['mnemonic']}")
                        print(f"Passphrase: {passphrase}")
                        print(f"Private Key: {wallet['private_key']}")
                        if 'wif' in wallet:
                            print(f"WIF: {wallet['wif']}")
                        print(f"Target Address: {target_address}")
                        print(f"{'='*70}\n")
                        
                        with open(FOUND_WALLETS_FILE, 'a', encoding='utf-8') as f:
                            f.write(f"\n{'='*70}\n")
                            f.write(f"TARGET ADDRESS FOUND! - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                            f.write(f"{'='*70}\n")
                            f.write(f"Target Address: {target_address}\n")
                            f.write(f"Seeds tested: {attempts:,}\n")
                            f.write(f"Passphrases tested: {passphrases_tested:,}\n")
                            f.write(f"Mnemonic: {wallet['mnemonic']}\n")
                            f.write(f"Passphrase: {passphrase}\n")
                            f.write(f"Private Key: {wallet['private_key']}\n")
                            if 'wif' in wallet:
                                f.write(f"WIF: {wallet['wif']}\n")
                            f.write(f"{'='*70}\n")
                        
                        print(f"[+] Details saved to {FOUND_WALLETS_FILE}\n")
                        return
                
                current_time = time.time()
                if current_time - last_update >= 1.0:
                    elapsed = current_time - start_time
                    seed_speed = int(attempts / elapsed) if elapsed > 0 else 0
                    pass_speed = int(passphrases_tested / elapsed) if elapsed > 0 else 0
                    
                    print(f"\r[*] Seeds: {attempts:,} ({seed_speed}/s) | "
                          f"Passphrases: {passphrases_tested:,} ({pass_speed}/s)", 
                          end='', flush=True)
                    last_update = current_time
        
        except KeyboardInterrupt:
            elapsed = time.time() - start_time
            print(f"\n\n[!] Search stopped")
            print(f"[*] Seeds tested: {attempts:,}")
            print(f"[*] Passphrases tested: {passphrases_tested:,}")
            print(f"[*] Time: {elapsed:.2f}s\n")
    
    def target_known_seed_passphrase_bruteforce(self, target_address: str, addr_type: str):
        """Bruteforce passphrase for a known seed phrase"""
        print("\n" + "="*70)
        print("MODE 4: KNOWN SEED + PASSPHRASE BRUTEFORCE")
        print("="*70)
        print(f"Target: {target_address}")
        print(f"Type: {addr_type}")
        print("="*70 + "\n")
        
        seed_input = input("Enter the seed phrase (12 or 24 words): ").strip()
        
        if not seed_input:
            print("[!] No seed provided\n")
            return
        
        words = seed_input.split()
        if len(words) not in [12, 24]:
            print(f"[!] Invalid seed length: {len(words)} words\n")
            return
        
        if HAS_MNEMONIC:
            if not self.mnemo.check(seed_input):
                print("[!] WARNING: Seed doesn't seem valid")
                response = input("[?] Continue anyway? (y/n): ")
                if response.lower() != 'y':
                    return
        
        print("\n" + "="*70)
        print("PASSPHRASE STRATEGY:")
        print("[1] Common passphrases (fast)")
        print("[2] Patterns + combinations (medium)")
        print("[3] All strategies (comprehensive)")
        print("[4] Custom wordlist file")
        print("="*70)
        
        strategy_choice = input("\nChoose strategy: ").strip()
        
        addr_key_map = {
            'legacy': 'legacy_address',
            'p2sh': 'p2sh_address',
            'segwit': 'segwit_address'
        }
        
        passphrases = []
        
        if strategy_choice == '1':
            passphrases = self.passphrase_gen.common_passphrases
        elif strategy_choice == '2':
            passphrases = self.passphrase_gen.patterns
        elif strategy_choice == '3':
            passphrases = self.passphrase_gen.get_passphrases_for_seed(
                words, strategy='all', max_count=10000
            )
        elif strategy_choice == '4':
            if os.path.exists(PASSPHRASE_FILE):
                with open(PASSPHRASE_FILE, 'r', encoding='utf-8') as f:
                    passphrases = [line.strip() for line in f if line.strip()]
            else:
                print(f"[!] File '{PASSPHRASE_FILE}' not found\n")
                return
        else:
            print("[!] Invalid choice\n")
            return
        
        print(f"\n[*] Testing {len(passphrases):,} passphrases...")
        print("[*] Press CTRL+C to stop\n")
        
        attempts = 0
        start_time = time.time()
        last_update = start_time
        
        try:
            for passphrase in passphrases:
                wallet = self.generate_btc_wallet(seed_input, passphrase)
                
                if not wallet:
                    continue
                
                attempts += 1
                
                generated_addr = wallet.get(addr_key_map.get(addr_type, 'legacy_address'))
                
                if generated_addr == target_address:
                    print(f"\n{'='*70}")
                    print("PASSPHRASE FOUND!")
                    print(f"{'='*70}")
                    print(f"Attempts: {attempts:,}")
                    print(f"Passphrase: '{passphrase}'")
                    print(f"Time: {time.time() - start_time:.2f}s")
                    print(f"\n{'='*70}")
                    print("WALLET DETAILS:")
                    print(f"{'='*70}")
                    print(f"Mnemonic: {seed_input}")
                    print(f"Passphrase: {passphrase}")
                    print(f"Private Key: {wallet['private_key']}")
                    if 'wif' in wallet:
                        print(f"WIF: {wallet['wif']}")
                    print(f"Address: {target_address}")
                    print(f"{'='*70}\n")
                    
                    with open(FOUND_WALLETS_FILE, 'a', encoding='utf-8') as f:
                        f.write(f"\n{'='*70}\n")
                        f.write(f"PASSPHRASE FOUND! - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                        f.write(f"{'='*70}\n")
                        f.write(f"Target Address: {target_address}\n")
                        f.write(f"Attempts: {attempts:,}\n")
                        f.write(f"Mnemonic: {seed_input}\n")
                        f.write(f"Passphrase: {passphrase}\n")
                        f.write(f"Private Key: {wallet['private_key']}\n")
                        if 'wif' in wallet:
                            f.write(f"WIF: {wallet['wif']}\n")
                        f.write(f"{'='*70}\n")
                    
                    print(f"[+] Saved to {FOUND_WALLETS_FILE}\n")
                    return
                
                current_time = time.time()
                if current_time - last_update >= 1.0:
                    elapsed = current_time - start_time
                    speed = int(attempts / elapsed) if elapsed > 0 else 0
                    progress = (attempts / len(passphrases)) * 100
                    
                    print(f"\r[*] Testing: {attempts:,}/{len(passphrases):,} ({progress:.2f}%) | "
                          f"Speed: {speed:,}/s | Last: '{passphrase[:20]}'", 
                          end='', flush=True)
                    last_update = current_time
            
            print(f"\n\n[!] Passphrase not found in {len(passphrases):,} attempts\n")
        
        except KeyboardInterrupt:
            elapsed = time.time() - start_time
            print(f"\n\n[!] Search stopped")
            print(f"[*] Attempts: {attempts:,}/{len(passphrases):,}")
            print(f"[*] Time: {elapsed:.2f}s\n")
    
    def recovery_wallet(self):
        """Recover a Bitcoin wallet from seed phrase with optional passphrase"""
        print("\n" + "="*70)
        print("BITCOIN WALLET RECOVERY")
        print("="*70)
        print("Enter the seed phrase (12 or 24 words separated by space)")
        print("="*70 + "\n")
        
        try:
            seed_input = input("Seed phrase: ").strip()
            
            if not seed_input:
                print("[!] Empty seed phrase\n")
                return
            
            words = seed_input.split()
            
            if len(words) not in [12, 24]:
                print(f"[!] Error: Must be 12 or 24 words (found: {len(words)})\n")
                return
            
            if HAS_MNEMONIC:
                if not self.mnemo.check(seed_input):
                    print("[!] WARNING: Seed phrase doesn't seem valid")
                    response = input("[?] Continue anyway? (y/n): ")
                    if response.lower() != 'y':
                        return
            
            print("\n[*] Optional: Enter passphrase (press Enter for none)")
            passphrase = input("Passphrase: ").strip()
            
            print("\n[*] Generating wallet...")
            wallet = self.generate_btc_wallet(mnemonic=seed_input, passphrase=passphrase)
            
            if wallet:
                print("\n" + "="*70)
                print("âœ… WALLET SUCCESSFULLY RECOVERED")
                print("="*70)
                
                for key, value in wallet.items():
                    if key != 'private_key' and key != 'passphrase':
                        print(f"{key}: {value}")
                
                if passphrase:
                    print(f"\nPassphrase used: {passphrase}")
                
                print("\n[?] Display private key? (y/n): ", end='')
                if input().strip().lower() == 'y':
                    print(f"\nPrivate Key: {wallet.get('private_key', 'N/A')}")
                    if 'wif' in wallet:
                        print(f"WIF: {wallet.get('wif')}")
                
                if self.db:
                    print("\n[*] Checking addresses in database...")
                    matches = self.check_wallet_addresses(wallet)
                    
                    if matches:
                        total_btc = sum(m['balance_btc'] for m in matches.values())
                        print(f"\n{'='*70}")
                        print("ADDRESSES FOUND IN DATABASE!")
                        print(f"{'='*70}")
                        
                        for addr_type, data in matches.items():
                            print(f"\n{addr_type}:")
                            print(f"  Address: {data['address']}")
                            print(f"  Balance: {data['balance_btc']:.8f} BTC")
                        
                        print(f"\n{'-'*70}")
                        print(f"Total Balance: {total_btc:.8f} BTC")
                        print(f"{'='*70}\n")
                    else:
                        print("\n[*] No addresses found in database")
                
                save = input("\n[?] Save this data? (y/n): ")
                if save.lower() == 'y':
                    with open('recovered_wallet.txt', 'w', encoding='utf-8') as f:
                        f.write(f"Wallet recovered: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                        f.write(f"{'='*70}\n")
                        for key, value in wallet.items():
                            f.write(f"{key}: {value}\n")
                    print(f"[+] Saved to 'recovered_wallet.txt'\n")
        
        except KeyboardInterrupt:
            print("\n[!] Cancelled\n")
        except Exception as e:
            print(f"[!] Error: {e}\n")
    
    def show_database_stats(self):
        """Show database statistics"""
        if not self.db:
            print("\n[!] Database not loaded!\n")
            return
        
        stats = self.db.get_statistics()
        
        print("\n" + "="*70)
        print("DATABASE STATISTICS")
        print("="*70)
        print(f"Total Addresses: {stats['total_addresses']:,}")
        print(f"Total Balance: {stats['total_balance_btc']:.8f} BTC")
        print(f"               ({stats['total_balance_satoshis']:,} satoshis)")
        print(f"Cache Size: {stats.get('cache_size', 0):,} entries")
        print(f"Database File: {BTC_DATABASE_FILE}")
        if os.path.exists(BTC_DATABASE_FILE):
            print(f"File Size: {os.path.getsize(BTC_DATABASE_FILE) / (1024*1024):.2f} MB")
        print("="*70 + "\n")
    
    def configure_passphrase_settings(self):
        """Configure passphrase attack settings"""
        print("\n" + "="*70)
        print("PASSPHRASE ATTACK SETTINGS")
        print("="*70)
        print(f"Current settings:")
        print(f"  Max passphrases per seed: {PASSPHRASE_CONFIG['max_per_seed']}")
        print(f"  Strategies: {', '.join(PASSPHRASE_CONFIG['strategies'])}")
        print(f"  Enabled: {PASSPHRASE_CONFIG['enabled']}")
        print("="*70 + "\n")
        
        print("[1] Change max passphrases per seed")
        print("[2] Toggle strategies")
        print("[3] View loaded passphrases")
        print("[4] Reload passphrase file")
        print("[5] Back to main menu")
        
        choice = input("\nChoice: ").strip()
        
        if choice == '1':
            try:
                new_max = int(input("Enter max passphrases per seed (1-1000): "))
                if 1 <= new_max <= 1000:
                    PASSPHRASE_CONFIG['max_per_seed'] = new_max
                    print(f"[+] Set to {new_max}")
                else:
                    print("[!] Invalid range")
            except:
                print("[!] Invalid number")
        
        elif choice == '2':
            print("\nAvailable strategies:")
            print("  [c] common - Common passwords")
            print("  [p] patterns - Numbers, years, combinations")
            print("  [h] hybrid - Words + numbers combinations")
            
            strategies = input("\nEnter letters (e.g., 'cph' for all): ").lower()
            new_strat = []
            if 'c' in strategies:
                new_strat.append('common')
            if 'p' in strategies:
                new_strat.append('patterns')
            if 'h' in strategies:
                new_strat.append('hybrid')
            
            if new_strat:
                PASSPHRASE_CONFIG['strategies'] = new_strat
                print(f"[+] Strategies: {', '.join(new_strat)}")
        
        elif choice == '3':
            print(f"\n[*] Loaded {len(self.passphrase_gen.common_passphrases)} common passphrases")
            show = input("Show first 20? (y/n): ")
            if show.lower() == 'y':
                for i, p in enumerate(self.passphrase_gen.common_passphrases[:20], 1):
                    print(f"  {i}. '{p}'")
        
        elif choice == '4':
            self.passphrase_gen = PassphraseGenerator()
            print("[+] Passphrase lists reloaded")
        
        print()
    
    def __del__(self):
        """Cleanup"""
        if self.db:
            self.db.close()


def main():
    """Main function"""
    os.system('clear' if os.name != 'nt' else 'cls')
    print(BANNER)
    
    if not HAS_MNEMONIC or not HAS_BITCOINLIB:
        print("\nRECOMMENDATION: For full functionality, install:")
        print("   pip install mnemonic bitcoinlib requests\n")
        time.sleep(2)
    
    generator = BitcoinWalletGenerator()
    
    while True:
        print(MENU)
        
        try:
            choice = input("Choose an option: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[!] Exiting...\n")
            sys.exit(0)
        
        if choice == '1':
            generator.generate_and_check_balance()
        
        elif choice == '2':
            generator.search_basic()
        
        elif choice == '3':
            generator.search_with_passphrase_attack()
        
        elif choice == '4':
            generator.target_specific_address()
        
        elif choice == '5':
            generator.recovery_wallet()
        
        elif choice == '6':
            success = convert_database_menu()
            if success:
                print("[*] Reloading database...")
                generator.load_database()
        
        elif choice == '7':
            generator.show_database_stats()
        
        elif choice == '8':
            generator.configure_passphrase_settings()
        
        elif choice == '9':
            print("\nGoodbye!\n")
            sys.exit(0)
        
        else:
            print("\n[!] Invalid option. Please try again.\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[!] Program interrupted by user\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n[!] Fatal error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)