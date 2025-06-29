from aiohttp import (
    ClientResponseError,
    ClientSession,
    ClientTimeout
)
# from aiohttp_socks import ProxyConnector # TIDAK DIGUNAKAN LAGI
from fake_useragent import FakeUserAgent
from base58 import b58decode, b58encode
from nacl.signing import SigningKey
from datetime import datetime, timezone
from colorama import *
import asyncio, random, json, os, pytz

# --- IMPORT UNTUK ANTI-CAPTCHA ---
from anticaptchaofficial.turnstileproxyless import *

# Inisialisasi colorama agar warna otomatis di-reset
init(autoreset=True)

wib = pytz.timezone('Asia/Jakarta')

class BitQuant:
    def __init__(self) -> None:
        self.HEADERS = {
            "Accept": "*/*",
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            "Origin": "https://www.bitquant.io",
            "Referer": "https://www.bitquant.io/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
            "User-Agent": FakeUserAgent().random
        }
        self.BASE_API = "https://quant-api.opengradient.ai/api"
        self.PAGE_URL = "https://www.bitquant.io/"
        self.SITE_KEY = "0x4AAAAAABRnkPBT6yl0YKs1"
        self.CAPTCHA_KEY = None # Ini akan dimuat dari file
        # self.proxies = [] # TIDAK DIGUNAKAN LAGI
        # self.proxy_index = 0 # TIDAK DIGUNAKAN LAGI
        # self.account_proxies = {} # TIDAK DIGUNAKAN LAGI
        self.tokens = {}
        self.id_tokens = {}
        self.min_delay = 0
        self.max_delay = 0

    def clear_terminal(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def log(self, message):
        print(
            f"{Fore.CYAN + Style.BRIGHT}[ {datetime.now().astimezone(wib).strftime('%x %X %Z')} ]{Style.RESET_ALL}"
            f"{Fore.WHITE + Style.BRIGHT} | {Style.RESET_ALL}{message}",
            flush=True
        )

    def welcome(self):
        print(
            f"""
        {Fore.GREEN + Style.BRIGHT}Auto Chat {Fore.BLUE + Style.BRIGHT}BitQuant - BOT
            """
            f"""
        {Fore.GREEN + Style.BRIGHT}Rey? {Fore.YELLOW + Style.BRIGHT}<INI WATERMARK>
            """
        )

    def format_seconds(self, seconds):
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"
    
    def load_anticaptcha_key(self):
        try:
            with open("anticaptcha_key.txt", 'r') as file:
                captcha_key = file.read().strip()
            if not captcha_key:
                self.log(f"{Fore.RED}Kunci API Anti-Captcha kosong di anticaptcha_key.txt.{Style.RESET_ALL}")
                return None
            return captcha_key
        except FileNotFoundError:
            self.log(f"{Fore.RED}File 'anticaptcha_key.txt' tidak ditemukan. Harap buat dan masukkan kunci API Anti-Captcha Anda di sana.{Style.RESET_ALL}")
            return None
        except Exception as e:
            self.log(f"{Fore.RED}Error memuat kunci Anti-Captcha: {e}{Style.RESET_ALL}")
            return None
    
    def load_question_lists(self):
        filename = "question_lists.json"
        try:
            if not os.path.exists(filename):
                self.log(f"{Fore.RED}File {filename} Tidak Ditemukan.{Style.RESET_ALL}")
                return [] # Mengembalikan list kosong agar kode tidak crash

            with open(filename, 'r') as file:
                data = json.load(file)
                if isinstance(data, list):
                    return data
                self.log(f"{Fore.RED}Format tidak valid di {filename}. Diharapkan berupa daftar pertanyaan (list of strings).{Style.RESET_ALL}")
                return []
        except json.JSONDecodeError:
            self.log(f"{Fore.RED}Error saat mendekode {filename}. Pastikan itu adalah JSON yang valid.{Style.RESET_ALL}")
            return []
        except Exception as e:
            self.log(f"{Fore.RED}Error memuat daftar pertanyaan: {e}{Style.RESET_ALL}")
            return []
    
    # --- load_proxies Dihapus karena tidak lagi digunakan ---
    # def load_proxies(...):
    #     pass 

    # --- check_proxy_schemes Dihapus karena tidak lagi digunakan ---
    # def check_proxy_schemes(...):
    #     pass

    # --- get_next_proxy_for_account Dihapus karena tidak lagi digunakan ---
    # def get_next_proxy_for_account(...):
    #     pass

    # --- rotate_proxy_for_account Dihapus karena tidak lagi digunakan ---
    # def rotate_proxy_for_account(...):
    #     pass

    def hex_to_bytes(self, hex_string: str) -> bytes:
        """Mengubah string heksadesimal menjadi bytes."""
        return bytes.fromhex(hex_string)

    def bytes_to_base58(self, byte_data: bytes) -> str:
        """Mengubah bytes menjadi string Base58."""
        return b58encode(byte_data).decode()

    def generate_address(self, private_key_input: str):
        """
        Menghasilkan alamat Solana (public key) dari private key.
        Mendukung input heksadesimal 64 karakter atau Base58.
        """
        private_key_seed_bytes = None
        
        # Coba sebagai Base58 terlebih dahulu (umum dari Phantom)
        try:
            decoded_base58 = b58decode(private_key_input)
            if len(decoded_base58) == 64: # Private key Solana dari dompet (seed + public key)
                private_key_seed_bytes = decoded_base58[:32]
                self.log(f"{Fore.GREEN}Dideteksi sebagai Base58 (64 byte) -> mengambil 32 byte seed.{Style.RESET_ALL}")
            elif len(decoded_base58) == 32: # Sudah berupa 32 byte seed Base58
                private_key_seed_bytes = decoded_base58
                self.log(f"{Fore.GREEN}Dideteksi sebagai Base58 (32 byte seed).{Style.RESET_ALL}")
            else:
                raise ValueError(f"Panjang byte Base58 tidak sesuai (ditemukan {len(decoded_base58)} byte, diharapkan 32 atau 64).")
        except ValueError as e_b58:
            # Jika gagal sebagai Base58, coba sebagai heksadesimal
            try:
                if len(private_key_input) == 64:
                    private_key_seed_bytes = self.hex_to_bytes(private_key_input)
                    if len(private_key_seed_bytes) != 32:
                         raise ValueError("Panjang heksadesimal 64 karakter tetapi setelah dikonversi bukan 32 byte.")
                    self.log(f"{Fore.GREEN}Dideteksi sebagai Heksadesimal (64 karakter).{Style.RESET_ALL}")
                else:
                    raise ValueError(f"Input bukan heksadesimal 64 karakter dan bukan Base58 yang valid. Error Base58: {e_b58}")
            except ValueError as e_hex:
                self.log(f"{Fore.RED}Error memproses private key: {e_hex}{Style.RESET_ALL}")
                return None
        except Exception as e:
            self.log(f"{Fore.RED}Terjadi kesalahan tak terduga saat memproses private key: {e}{Style.RESET_ALL}")
            return None

        if private_key_seed_bytes:
            try:
                signing_key = SigningKey(private_key_seed_bytes)
                verify_key = signing_key.verify_key
                address = self.bytes_to_base58(verify_key.encode())
                return address
            except Exception as e:
                self.log(f"{Fore.RED}Error saat membuat signing key atau menghasilkan alamat: {e}{Style.RESET_ALL}")
                return None
        return None

    def generate_payload(self, private_key_hex_seed: str, address: str):
        """
        Menghasilkan payload autentikasi dari private key heksadesimal 32-byte seed dan alamat.
        """
        try:
            now = datetime.now(timezone.utc)
            nonce = int(now.timestamp() * 1000)
            issued_at = now.isoformat(timespec='milliseconds').replace('+00:00', 'Z')
            message = f"bitquant.io wants you to sign in with your **blockchain** account:\n{address}\n\nURI: https://bitquant.io\nVersion: 1\nChain ID: solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp\nNonce: {nonce}\nIssued At: {issued_at}"
            
            private_key_bytes = self.hex_to_bytes(private_key_hex_seed)
            signing_key = SigningKey(private_key_bytes)
            encode_message = message.encode('utf-8')
            signature = signing_key.sign(encode_message)
            signature_base58 = self.bytes_to_base58(signature.signature)

            payload = {
                "address": address,
                "message": message,
                "signature": signature_base58
            }
            
            return payload
        except Exception as e:
            raise Exception(f"Gagal Membuat Payload Permintaan: {str(e)}")
    
    def mask_account(self, account):
        try:
            # Masking private key heksadesimal (64 karakter) atau Base58 panjang
            if len(account) >= 10: # Cukup panjang untuk di-masking
                return account[:6] + '*' * (len(account) - 12) + account[-6:]
            return account # Fallback jika terlalu pendek
        except Exception as e:
            self.log(f"{Fore.RED}Error masking account: {e}{Style.RESET_ALL}")
            return account

    def generate_agent_payload(self, address: str, turnstile_token: str, question: str):
        try:
            payload = {
                "context":{
                    "conversationHistory": [
                        { "type":"user", "message":question },
                        { "type":"user", "message":question } # Ini sepertinya duplikasi, pastikan ini yang Anda inginkan
                    ],
                    "address":address,
                    "poolPositions":[],
                    "availablePools":[]
                },
                "message":{ "type":"user", "message":question },
                "captchaToken":turnstile_token
            }
            return payload
        except Exception as e:
            self.log(f"{Fore.RED}Error membuat payload agen: {e}{Style.RESET_ALL}")
            return None
        
    async def print_timer(self):
        for remaining in range(random.randint(self.min_delay, self.max_delay), 0, -1):
            print(
                f"{Fore.CYAN + Style.BRIGHT}[ {datetime.now().astimezone(wib).strftime('%x %X %Z')} ]{Style.RESET_ALL}"
                f"{Fore.WHITE + Style.BRIGHT} | {Style.RESET_ALL}"
                f"{Fore.BLUE + Style.BRIGHT}Menunggu{Style.RESET_ALL}"
                f"{Fore.WHITE + Style.BRIGHT} {remaining} {Style.RESET_ALL}"
                f"{Fore.BLUE + Style.BRIGHT}Detik Untuk Interaksi Berikutnya...{Style.RESET_ALL}",
                end="\r",
                flush=True
            )
            await asyncio.sleep(1)
            print(" " * 100, end="\r") # Membersihkan baris setelah timer selesai
            
    def print_question(self):
        # Karena tidak pakai proxy lokal lagi, pilihan proxy dihapus dari sini.
        # Hanya menanyakan delay saja.
        while True:
            try:
                min_delay = int(input(f"{Fore.YELLOW + Style.BRIGHT}Penundaan Minimum Setiap Interaksi (detik) -> {Style.RESET_ALL}").strip())

                if min_delay >= 0:
                    self.min_delay = min_delay
                    break
                else:
                    print(f"{Fore.RED + Style.BRIGHT}Input tidak valid. Penundaan Minimum Harus >= 0.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED + Style.BRIGHT}Input tidak valid. Masukkan angka.{Style.RESET_ALL}")

        while True:
            try:
                max_delay = int(input(f"{Fore.YELLOW + Style.BRIGHT}Penundaan Maksimum Setiap Interaksi (detik) -> {Style.RESET_ALL}").strip())

                if max_delay >= self.min_delay:
                    self.max_delay = max_delay
                    break
                else:
                    print(f"{Fore.RED + Style.BRIGHT}Input tidak valid. Penundaan Maksimum Harus >= Penundaan Minimum.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED + Style.BRIGHT}Input tidak valid. Masukkan angka.{Style.RESET_ALL}")

        # Mengembalikan nilai default karena pilihan proxy sudah tidak ada
        return 3, False # 3 untuk "Run Without Proxy", False untuk "Rotate Invalid Proxy"
    
    # --- solve_cf_turnstile_anticaptcha TANPA ARGUMEN PROXY ---
    async def solve_cf_turnstile_anticaptcha(self, retries=5):
        for attempt in range(retries):
            try:
                if self.CAPTCHA_KEY is None:
                    self.log(f"{Fore.RED}Kunci API Anti-Captcha belum diatur. Harap berikan di anticaptcha_key.txt.{Style.RESET_ALL}")
                    return None
                
                solver = turnstileProxyless()
                solver.set_verbose(0) 
                solver.set_key(self.CAPTCHA_KEY)
                solver.set_website_url(self.PAGE_URL)
                solver.set_website_key(self.SITE_KEY)
                
                self.log(f"{Fore.MAGENTA+Style.BRIGHT}  ● {Style.RESET_ALL}{Fore.YELLOW + Style.BRIGHT}Mengirim Captcha ke Anti-Captcha...{Style.RESET_ALL}")
                token = solver.solve_and_return_solution()

                if token != 0:
                    self.log(f"{Fore.MAGENTA+Style.BRIGHT}  ● {Style.RESET_ALL}{Fore.GREEN + Style.BRIGHT}Captcha Berhasil Diselesaikan oleh Anti-Captcha!{Style.RESET_ALL}")
                    return token
                else:
                    self.log(f"{Fore.MAGENTA+Style.BRIGHT}  ● {Style.RESET_ALL}{Fore.RED + Style.BRIGHT}Anti-Captcha Error: {solver.error_code}{Style.RESET_ALL}")
                    await asyncio.sleep(5) 
                    continue

            except Exception as e:
                self.log(f"{Fore.RED}Error selama penyelesaian Anti-Captcha (Percobaan {attempt + 1}/{retries}): {e}{Style.RESET_ALL}")
                if attempt < retries - 1:
                    await asyncio.sleep(5)
                    continue
                return None
        return None
            
    # --- user_login TANPA ARGUMEN PROXY (dan connector dihapus) ---
    async def user_login(self, account_original_input: str, address: str, retries=5): # Hapus proxy=None
        private_key_seed_hex_for_payload = None
        try:
            decoded_base58 = b58decode(account_original_input)
            if len(decoded_base58) == 64:
                private_key_seed_hex_for_payload = decoded_base58[:32].hex()
            elif len(decoded_base58) == 32:
                private_key_seed_hex_for_payload = decoded_base58.hex()
            else:
                private_key_seed_hex_for_payload = account_original_input 
        except ValueError:
            private_key_seed_hex_for_payload = account_original_input 
            
        if not private_key_seed_hex_for_payload or len(private_key_seed_hex_for_payload) != 64:
            self.log(f"{Fore.RED}Error: Gagal mendapatkan private key seed heksadesimal untuk payload. Format kunci tidak didukung.{Style.RESET_ALL}")
            return None

        url = f"{self.BASE_API}/verify/solana"
        data = json.dumps(self.generate_payload(private_key_seed_hex_for_payload, address))
        headers = {
            **self.HEADERS,
            "Content-Length": str(len(data)),
            "Content-Type": "application/json"
        }
        await asyncio.sleep(3)
        for attempt in range(retries):
            # connector = ProxyConnector.from_url(proxy) if proxy else None # DIHAPUS
            try:
                async with ClientSession(timeout=ClientTimeout(total=60)) as session: # Hapus connector=connector
                    async with session.post(url=url, headers=headers, data=data, ssl=False) as response:
                        response.raise_for_status()
                        return await response.json()
            except (Exception, ClientResponseError) as e:
                if attempt < retries - 1:
                    self.log(
                        f"{Fore.CYAN+Style.BRIGHT}Error  :{Style.RESET_ALL}"
                        f"{Fore.RED+Style.BRIGHT} Login Gagal {Style.RESET_ALL}"
                        f"{Fore.MAGENTA+Style.BRIGHT}-{Style.RESET_ALL}"
                        f"{Fore.YELLOW+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
                        f"{Fore.BLUE} (Mencoba lagi dalam 5s){Style.RESET_ALL}"
                    )
                    await asyncio.sleep(5)
                    continue
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}Error  :{Style.RESET_ALL}"
                    f"{Fore.RED+Style.BRIGHT} Login Gagal {Style.RESET_ALL}"
                    f"{Fore.MAGENTA+Style.BRIGHT}-{Style.RESET_ALL}"
                    f"{Fore.YELLOW+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
                )
        return None
        
    # --- secure_token TANPA ARGUMEN PROXY (dan connector dihapus) ---
    async def secure_token(self, address: str, retries=5): # Hapus proxy=None
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key=AIzaSyBDdwO2O_Ose7LICa-A78qKJUCEE3nAwsM"
        data = json.dumps({"token":self.tokens[address], "returnSecureToken":True})
        headers = {
            **self.HEADERS,
            "Content-Length": str(len(data)),
            "Content-Type": "application/json"
        }
        await asyncio.sleep(3)
        for attempt in range(retries):
            # connector = ProxyConnector.from_url(proxy) if proxy else None # DIHAPUS
            try:
                async with ClientSession(timeout=ClientTimeout(total=60)) as session: # Hapus connector=connector
                    async with session.post(url=url, headers=headers, data=data, ssl=False) as response:
                        response.raise_for_status()
                        return await response.json()
            except (Exception, ClientResponseError) as e:
                if attempt < retries - 1:
                    self.log(
                        f"{Fore.CYAN+Style.BRIGHT}Error  :{Style.RESET_ALL}"
                        f"{Fore.RED+Style.BRIGHT} Gagal Mendapatkan Id Token {Style.RESET_ALL}"
                        f"{Fore.MAGENTA+Style.BRIGHT}-{Style.RESET_ALL}"
                        f"{Fore.YELLOW+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
                        f"{Fore.BLUE} (Mencoba lagi dalam 5s){Style.RESET_ALL}"
                    )
                    await asyncio.sleep(5)
                    continue
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}Error  :{Style.RESET_ALL}"
                    f"{Fore.RED+Style.BRIGHT} Gagal Mendapatkan Id Token {Style.RESET_ALL}"
                    f"{Fore.MAGENTA+Style.BRIGHT}-{Style.RESET_ALL}"
                    f"{Fore.YELLOW+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
                )
        return None
            
    # --- user_stats TANPA ARGUMEN PROXY (dan connector dihapus) ---
    async def user_stats(self, address: str, retries=5): # Hapus proxy=None
        url = f"{self.BASE_API}/activity/stats?address={address}"
        headers = {
            **self.HEADERS,
            "Authorization": f"Bearer {self.id_tokens[address]}"
        }
        await asyncio.sleep(3)
        for attempt in range(retries):
            # connector = ProxyConnector.from_url(proxy) if proxy else None # DIHAPUS
            try:
                async with ClientSession(timeout=ClientTimeout(total=60)) as session: # Hapus connector=connector
                    async with session.get(url=url, headers=headers, ssl=False) as response:
                        response.raise_for_status()
                        return await response.json()
            except (Exception, ClientResponseError) as e:
                if attempt < retries - 1:
                    self.log(
                        f"{Fore.CYAN+Style.BRIGHT}Error  :{Style.RESET_ALL}"
                        f"{Fore.RED+Style.BRIGHT} Gagal Mendapatkan Statistik Aktivitas {Style.RESET_ALL}"
                        f"{Fore.MAGENTA+Style.BRIGHT}-{Style.RESET_ALL}"
                        f"{Fore.YELLOW+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
                        f"{Fore.BLUE} (Mencoba lagi dalam 5s){Style.RESET_ALL}"
                    )
                    await asyncio.sleep(5)
                    continue
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}Error  :{Style.RESET_ALL}"
                    f"{Fore.RED+Style.BRIGHT} Gagal Mendapatkan Statistik Aktivitas {Style.RESET_ALL}"
                    f"{Fore.MAGENTA+Style.BRIGHT}-{Style.RESET_ALL}"
                    f"{Fore.YELLOW+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
                )
        return None
            
    # --- run_agent TANPA ARGUMEN PROXY (dan connector dihapus) ---
    async def run_agent(self, address: str, turnstile_token: str, question: str, retries=5): # Hapus proxy=None
        url = f"{self.BASE_API}/v2/agent/run"
        data = json.dumps(self.generate_agent_payload(address, turnstile_token, question))
        headers = {
            **self.HEADERS,
            "Authorization": f"Bearer {self.id_tokens[address]}",
            "Content-Length": str(len(data)),
            "Content-Type": "application/json"
        }
        await asyncio.sleep(3)
        for attempt in range(retries):
            # connector = ProxyConnector.from_url(proxy) if proxy else None # DIHAPUS
            try:
                async with ClientSession(timeout=ClientTimeout(total=60)) as session: # Hapus connector=connector
                    async with session.post(url=url, headers=headers, data=data, ssl=False) as response:
                        response.raise_for_status()
                        return await response.json()
            except (Exception, ClientResponseError) as e:
                if attempt < retries - 1:
                    self.log(
                        f"{Fore.CYAN + Style.BRIGHT}    Status    :{Style.RESET_ALL}"
                        f"{Fore.RED + Style.BRIGHT} Interaksi Gagal {Style.RESET_ALL}"
                        f"{Fore.MAGENTA+Style.BRIGHT}-{Style.RESET_ALL}"
                        f"{Fore.YELLOW+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
                        f"{Fore.BLUE} (Mencoba lagi dalam 5s){Style.RESET_ALL}"
                    )
                    await asyncio.sleep(5)
                    continue
                self.log(
                    f"{Fore.CYAN + Style.BRIGHT}    Status    :{Style.RESET_ALL}"
                    f"{Fore.RED + Style.BRIGHT} Interaksi Gagal {Style.RESET_ALL}"
                    f"{Fore.MAGENTA+Style.BRIGHT}-{Style.RESET_ALL}"
                    f"{Fore.YELLOW+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
                )
        return None 
            
    # --- process_user_login TANPA ARGUMEN PROXY (dan logika rotasi proxy dihapus) ---
    async def process_user_login(self, account: str, address: str): # Hapus use_proxy, rotate_proxy
        while True: # Loop ini sekarang hanya untuk retry login tanpa proxy
            # proxy = self.get_next_proxy_for_account(address) if use_proxy else None # DIHAPUS
            # if proxy: # DIHAPUS
            #    self.log(...) # DIHAPUS

            login = await self.user_login(account, address) # Hapus proxy
            if login:
                self.tokens[address] = login["token"]
                return True

            # if rotate_proxy: # DIHAPUS
            #    self.log(...) # DIHAPUS
            #    self.rotate_proxy_for_account(address) # DIHAPUS
            #    await asyncio.sleep(5) # DIHAPUS
            #    continue # DIHAPUS

            # Karena tidak ada proxy lagi, jika login gagal, kita tidak bisa merotasi.
            # Mungkin ada baiknya menambahkan delay atau limit retry di sini jika ini loop while True
            self.log(f"{Fore.RED}Login gagal untuk {self.mask_account(address)}. Mencoba lagi...{Style.RESET_ALL}")
            await asyncio.sleep(10) # Beri jeda sebelum mencoba login lagi
            # Jika Anda ingin membatasi jumlah percobaan di sini, tambahkan counter.
            # Untuk saat ini, asumsikan akan terus mencoba.
            
            # return False # Ini tidak pernah tercapai karena loop while True

    # --- process_secure_token TANPA ARGUMEN PROXY ---
    async def process_secure_token(self, account: str, address: str): # Hapus use_proxy, rotate_proxy
        logined = await self.process_user_login(account, address) # Hapus use_proxy, rotate_proxy
        if logined:
            # proxy = self.get_next_proxy_for_account(address) if use_proxy else None # DIHAPUS

            id_token = await self.secure_token(address) # Hapus proxy
            if id_token:
                self.id_tokens[address] = id_token["idToken"]

                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}Status :{Style.RESET_ALL}"
                    f"{Fore.GREEN+Style.BRIGHT} Login Berhasil {Style.RESET_ALL}"
                )
                return True
            else: 
                self.log(f"{Fore.RED}Gagal mengamankan ID token untuk {self.mask_account(address)}.{Style.RESET_ALL}")
        
        return False # Mengembalikan False jika login atau secure token gagal

    # --- process_accounts TANPA ARGUMEN PROXY ---
    async def process_accounts(self, account_input: str, address: str, questions: list): # Hapus use_proxy, rotate_proxy
        secured = await self.process_secure_token(account_input, address) # Hapus use_proxy, rotate_proxy
        if secured: 
            # proxy = self.get_next_proxy_for_account(address) if use_proxy else None # DIHAPUS

            stats = await self.user_stats(address) # Hapus proxy
            if not stats:
                self.log(f"{Fore.RED}Tidak dapat mengambil statistik pengguna untuk {self.mask_account(address)}{Style.RESET_ALL}")
                return 

            points = stats.get("points", 0)
            message_count = stats.get("message_count", 0)
            
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}Saldo:{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {points} PTS {Style.RESET_ALL}"
            )
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}Pesan:{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {message_count} {Style.RESET_ALL}"
            )

            daily_message_count = stats.get("daily_message_count", 0)
            daily_message_limit = stats.get("daily_message_limit", 0)

            if daily_message_limit > 0 and daily_message_count >= daily_message_limit:
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}Agen :{Style.RESET_ALL}"
                    f"{Fore.YELLOW+Style.BRIGHT} Interaksi Harian Telah Tercapai ({daily_message_count}/{daily_message_limit}){Style.RESET_ALL}"
                )
                return
            elif daily_message_limit == 0: 
                 self.log(f"{Fore.YELLOW}Batas pesan harian adalah 0 atau tidak tersedia. Melewati interaksi.{Style.RESET_ALL}")
                 return
            
            self.log(f"{Fore.CYAN+Style.BRIGHT}Captcha:{Style.RESET_ALL}")
            self.log(
                f"{Fore.MAGENTA+Style.BRIGHT}  ● {Style.RESET_ALL}"
                f"{Fore.YELLOW + Style.BRIGHT}Memulai Pemecahan Captcha Turnstile dengan Anti-Captcha...{Style.RESET_ALL}"
            )
            
            turnstile_token = await self.solve_cf_turnstile_anticaptcha() # Hapus argumen proxy
            if not turnstile_token:
                self.log(
                    f"{Fore.MAGENTA+Style.BRIGHT}  ● {Style.RESET_ALL}"
                    f"{Fore.BLUE+Style.BRIGHT}Status  :{Style.RESET_ALL}"
                    f"{Fore.RED + Style.BRIGHT} Captcha Turnstile Gagal Terpecahkan {Style.RESET_ALL}"
                )
                return
            
            self.log(
                f"{Fore.MAGENTA+Style.BRIGHT}  ● {Style.RESET_ALL}"
                f"{Fore.BLUE+Style.BRIGHT}Status  :{Style.RESET_ALL}"
                f"{Fore.GREEN + Style.BRIGHT} Captcha Turnstile Berhasil Terpecahkan!{Style.RESET_ALL}"
            )

            available_questions_copy = list(questions)
            random.shuffle(available_questions_copy) 

            while daily_message_count < daily_message_limit and available_questions_copy:
                self.log(
                    f"{Fore.MAGENTA + Style.BRIGHT}  ● {Style.RESET_ALL}"
                    f"{Fore.BLUE + Style.BRIGHT}Interaksi{Style.RESET_ALL}"
                    f"{Fore.WHITE + Style.BRIGHT} {daily_message_count + 1} dari {daily_message_limit} {Style.RESET_ALL}"
                )

                question = available_questions_copy.pop(0) 

                self.log(
                    f"{Fore.CYAN + Style.BRIGHT}    Pertanyaan  : {Style.RESET_ALL}"
                    f"{Fore.WHITE + Style.BRIGHT}{question}{Style.RESET_ALL}"
                )

                run = await self.run_agent(address, turnstile_token, question) # Hapus argumen proxy
                if run:
                    answer = run.get("message", "Unknown")

                    self.log(
                        f"{Fore.CYAN + Style.BRIGHT}    Status    :{Style.RESET_ALL}"
                        f"{Fore.GREEN + Style.BRIGHT} Interaksi Berhasil {Style.RESET_ALL}"
                    )
                    self.log(
                        f"{Fore.CYAN + Style.BRIGHT}    Jawaban    : {Style.RESET_ALL}"
                        f"{Fore.WHITE + Style.BRIGHT}{answer}{Style.RESET_ALL}"
                    )

                    daily_message_count += 1
                    if daily_message_count < daily_message_limit and available_questions_copy:
                        await self.print_timer() 
                else:
                    self.log(f"{Fore.RED}Gagal menjalankan agen untuk pertanyaan: {question}. Mencoba ulang captcha atau melewati...{Style.RESET_ALL}")
                    turnstile_token = await self.solve_cf_turnstile_anticaptcha()
                    if not turnstile_token:
                        self.log(f"{Fore.RED}Tidak dapat menyelesaikan ulang captcha. Melewati interaksi selanjutnya untuk akun ini.{Style.RESET_ALL}")
                        break 

            if not available_questions_copy and daily_message_count < daily_message_limit:
                 self.log(f"{Fore.YELLOW}Semua pertanyaan yang tersedia dari daftar telah digunakan untuk akun ini. Melewati interaksi selanjutnya.{Style.RESET_ALL}")
        
    async def main(self):
        try:
            with open('accounts.txt', 'r') as file:
                accounts = [line.strip() for line in file if line.strip()]

            captcha_key = self.load_anticaptcha_key()
            if captcha_key:
                self.CAPTCHA_KEY = captcha_key
            else:
                self.log(f"{Fore.RED}Kunci API Anti-Captcha tidak ditemukan atau kosong. Harap periksa 'anticaptcha_key.txt'.{Style.RESET_ALL}")
                print(f"{Fore.RED}Keluar...{Style.RESET_ALL}")
                return

            # --- print_question sekarang hanya menanyakan delay, tidak ada pilihan proxy ---
            self.print_question() # Tidak perlu mengembalikan use_proxy_choice, rotate_proxy
            # Variabel use_proxy_choice dan rotate_proxy tidak lagi relevan
            # karena proxy lokal sudah dihapus.

            questions = self.load_question_lists()
            if not questions:
                self.log(f"{Fore.RED + Style.BRIGHT}Tidak ada Pertanyaan yang Dimuat. Harap periksa 'question_lists.json'.{Style.RESET_ALL}")
                print(f"{Fore.RED}Keluar...{Style.RESET_ALL}")
                return

            while True: # Loop utama untuk menjalankan bot secara terus-menerus (24 jam)
                # use_proxy = False # Tidak perlu lagi karena selalu tanpa proxy lokal
                # if use_proxy_choice in [1, 2]: # Tidak perlu lagi
                #     use_proxy = True # Tidak perlu lagi

                self.clear_terminal()
                self.welcome()
                self.log(
                    f"{Fore.GREEN + Style.BRIGHT}Total Akun: {Style.RESET_ALL}"
                    f"{Fore.WHITE + Style.BRIGHT}{len(accounts)}{Style.RESET_ALL}"
                )

                # --- load_proxies Dihapus dari sini ---
                # if use_proxy:
                #    await self.load_proxies(use_proxy_choice)
                #    if not self.proxies and use_proxy_choice in [1, 2]:
                #        self.log(f"{Fore.YELLOW}Tidak ada proxy yang tersedia setelah pemuatan, beralih ke koneksi langsung (tanpa proxy).{Style.RESET_ALL}")
                #        use_proxy = False
                
                separator = "=" * 23
                for account_input in accounts:
                    if account_input:
                        address = self.generate_address(account_input)
                        self.log(
                            f"{Fore.CYAN + Style.BRIGHT}{separator}[{Style.RESET_ALL}"
                            f"{Fore.WHITE + Style.BRIGHT} {self.mask_account(account_input)} {Style.RESET_ALL}"
                            f"{Fore.CYAN + Style.BRIGHT}]{separator}{Style.RESET_ALL}"
                        )

                        if not address:
                            self.log(
                                f"{Fore.CYAN + Style.BRIGHT}Status  :{Style.RESET_ALL}"
                                f"{Fore.RED + Style.BRIGHT} Kunci Pribadi Tidak Valid (Periksa format Base58/Heksadesimal 64 karakter) {Style.RESET_ALL}"
                            )
                            continue

                        # Hapus argumen proxy dari panggilan ini
                        await self.process_accounts(account_input, address, questions) # Hapus use_proxy, rotate_proxy
                        await asyncio.sleep(3) # Jeda antar akun (opsional, bisa disesuaikan)

                self.log(f"{Fore.CYAN + Style.BRIGHT}={Style.RESET_ALL}"*68)
                seconds = 24 * 60 * 60 # 24 jam
                while seconds > 0:
                    formatted_time = self.format_seconds(seconds)
                    print(
                        f"{Fore.CYAN+Style.BRIGHT}[ Menunggu{Style.RESET_ALL}"
                        f"{Fore.WHITE+Style.BRIGHT} {formatted_time} {Style.RESET_ALL}"
                        f"{Fore.CYAN+Style.BRIGHT}... ]{Style.RESET_ALL}"
                        f"{Fore.WHITE+Style.BRIGHT} | {Style.RESET_ALL}"
                        f"{Fore.BLUE+Style.BRIGHT}Semua Akun Telah Diproses. Akan memulai siklus baru segera.{Style.RESET_ALL}",
                        end="\r"
                    )
                    await asyncio.sleep(1)
                    seconds -= 1
                print("\n")

        except FileNotFoundError:
            self.log(f"{Fore.RED}File 'accounts.txt' Tidak Ditemukan. Harap buat 'accounts.txt' dan masukkan private key Anda di sana.{Style.RESET_ALL}")
            print(f"{Fore.RED}Keluar...{Style.RESET_ALL}")
            return
        except Exception as e:
            self.log(f"{Fore.RED+Style.BRIGHT}Terjadi kesalahan tak terduga di fungsi utama (main): {e}{Style.RESET_ALL}")

if __name__ == "__main__":
    try:
        bot = BitQuant()
        asyncio.run(bot.main())
    except KeyboardInterrupt:
        print(
            f"\n{Fore.CYAN + Style.BRIGHT}[ {datetime.now().astimezone(wib).strftime('%x %X %Z')} ]{Style.RESET_ALL}"
            f"{Fore.WHITE + Style.BRIGHT} | {Style.RESET_ALL}"
            f"{Fore.RED + Style.BRIGHT}[ KELUAR ] BitQuant - BOT                                    "
        )
    except Exception as e:
        print(
            f"\n{Fore.CYAN + Style.BRIGHT}[ {datetime.now().astimezone(wib).strftime('%x %X %Z')} ]{Style.RESET_ALL}"
            f"{Fore.WHITE + Style.BRIGHT} | {Style.RESET_ALL}"
            f"{Fore.RED + Style.BRIGHT}[ ERROR ] Kesalahan tak terduga: {e}{Style.RESET_ALL}"
        )
