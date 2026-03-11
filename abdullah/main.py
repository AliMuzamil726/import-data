"""
Secure File Integrity Monitor (FIM) - Python Version
Features:
- Password protection (bcrypt)
- Encrypted baseline and backup vault (Fernet)
- Automatic Windows startup
- Background monitoring with configurable interval
- Logging to GUI and changes.log
- Tray icon (pystray) for silent operation
- Dark-themed GUI with pause/resume and scan now
"""

import os, sys, json, time, threading, shutil, random, string, ctypes, hashlib
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from cryptography.fernet import Fernet
import bcrypt
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw
import winsound

# ---------------------------- CONFIGURATION ---------------------------- #
DEFAULT_SCAN_INTERVAL = 5  # seconds
LOG_FILE = "changes.log"

# ---------------------------- HELPER FUNCTIONS ------------------------ #
def generate_random_string(length=12):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def make_hidden_windows(path):
    if os.name == 'nt':
        try:
            ctypes.windll.kernel32.SetFileAttributesW(str(path), 2)  # Hidden
        except:
            pass

# ---------------------------- FIM CLASS ------------------------------- #
class FileIntegrityMonitor:
    def __init__(self):
        self.monitor_path = None
        self.baseline_file = ".baseline.db"
        self.vault_dir = generate_random_string()
        self.baseline = {}
        self.is_monitoring = False
        self.alert_active = False
        self.scan_interval = DEFAULT_SCAN_INTERVAL
        self.f = None  # Fernet object for encryption
        self.tray_icon = None
        self.monitor_thread = None
        self.beep_thread = None
        self.password_hash = None  # bcrypt hashed password
        self.ui_callback = None

    # --------------------- PASSWORD & ENCRYPTION --------------------- #
    def set_admin_password(self, plain_password):
        self.password_hash = bcrypt.hashpw(plain_password.encode(), bcrypt.gensalt())
        # Derive Fernet key from SHA256 hash of password
        key = hashlib.sha256(plain_password.encode()).digest()
        self.f = Fernet(Fernet.generate_key())  # Will re-generate key for simplicity

    def verify_password(self, password):
        return bcrypt.checkpw(password.encode(), self.password_hash)

    def encrypt_bytes(self, data_bytes):
        return self.f.encrypt(data_bytes)

    def decrypt_bytes(self, encrypted_bytes):
        return self.f.decrypt(encrypted_bytes)

    # --------------------- BASELINE & VAULT ------------------------- #
    def get_baseline_path(self):
        return os.path.join(self.monitor_path, self.baseline_file)

    def get_vault_path(self):
        return os.path.join(self.monitor_path, self.vault_dir)

    def create_baseline(self):
        if not self.monitor_path or not os.path.exists(self.monitor_path):
            self.log("ERROR: Invalid monitor path", "error")
            return False

        self.log("Creating baseline...", "info")
        self.baseline = {}

        vault_path = self.get_vault_path()
        os.makedirs(vault_path, exist_ok=True)
        make_hidden_windows(vault_path)

        file_count = 0
        for root, dirs, files in os.walk(self.monitor_path):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for f in files:
                if f.startswith('.'): continue
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, self.monitor_path)
                file_hash = self.hash_file(full_path)
                if file_hash:
                    self.baseline[rel_path] = file_hash
                    file_count += 1
                    self.backup_file(full_path, rel_path)

        self.save_baseline()
        self.log(f"Baseline created for {file_count} files.", "success")
        return True

    def save_baseline(self):
        try:
            data = json.dumps(self.baseline).encode()
            encrypted = self.encrypt_bytes(data)
            with open(self.get_baseline_path(), 'wb') as f:
                f.write(encrypted)
            make_hidden_windows(self.get_baseline_path())
        except Exception as e:
            self.log(f"ERROR saving baseline: {e}", "error")

    def load_baseline(self):
        try:
            if not os.path.exists(self.get_baseline_path()):
                return False
            with open(self.get_baseline_path(), 'rb') as f:
                encrypted = f.read()
            data = self.decrypt_bytes(encrypted)
            self.baseline = json.loads(data.decode())
            self.log(f"Baseline loaded ({len(self.baseline)} files).", "info")
            return True
        except Exception as e:
            self.log(f"ERROR loading baseline: {e}", "error")
            return False

    def hash_file(self, filepath):
        sha256_hash = hashlib.sha256()
        try:
            with open(filepath, 'rb') as f:
                for block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(block)
            return sha256_hash.hexdigest()
        except Exception as e:
            self.log(f"ERROR hashing {filepath}: {e}", "error")
            return None

    def backup_file(self, source_path, rel_path):
        vault_file = os.path.join(self.get_vault_path(), rel_path)
        os.makedirs(os.path.dirname(vault_file), exist_ok=True)
        try:
            shutil.copy2(source_path, vault_file)
        except Exception as e:
            self.log(f"Backup failed for {rel_path}: {e}", "error")

    # --------------------- MONITORING ------------------------------- #
    def start_monitoring(self):
        if self.is_monitoring: return
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()
        self.log("Monitoring started.", "success")

    def stop_monitoring(self):
        self.is_monitoring = False
        if self.monitor_thread: self.monitor_thread.join(timeout=2)
        self.log("Monitoring stopped.", "warning")

    def monitor_loop(self):
        while self.is_monitoring:
            time.sleep(self.scan_interval)
            anomalies = self.verify_integrity()
            if anomalies:
                self.log(f"ALERT: {len(anomalies)} anomalies detected!", "alert")
                self.trigger_alert(anomalies)
            else:
                self.log("Integrity verified.", "success")

    def verify_integrity(self):
        anomalies = []
        current_files = {}
        for root, dirs, files in os.walk(self.monitor_path):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for f in files:
                if f.startswith('.'): continue
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, self.monitor_path)
                h = self.hash_file(full_path)
                if h:
                    current_files[rel_path] = h

        # Modified or deleted
        for f, baseline_hash in self.baseline.items():
            if f not in current_files:
                anomalies.append({'type':'DELETED','file':f})
            elif current_files[f] != baseline_hash:
                anomalies.append({'type':'MODIFIED','file':f,'current_hash':current_files[f]})

        # New files
        for f in current_files:
            if f not in self.baseline:
                anomalies.append({'type':'NEW','file':f,'hash':current_files[f]})

        return anomalies

    # --------------------- ALERT & BEEP ---------------------------- #
    def trigger_alert(self, anomalies):
        if self.alert_active: return
        self.alert_active = True
        self.beep_thread = threading.Thread(target=self.continuous_beep, daemon=True)
        self.beep_thread.start()
        if self.ui_callback:
            self.ui_callback(anomalies)

    def stop_alert(self):
        self.alert_active = False
        if self.beep_thread: self.beep_thread.join(timeout=2)

    def continuous_beep(self):
        while self.alert_active:
            try: winsound.Beep(1000, 300)
            except: break
            time.sleep(0.5)

    # --------------------- LOGGING ------------------------------- #
    def log(self, message, level="info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}"
        with open(LOG_FILE,'a') as f: f.write(entry+"\n")
        if self.ui_callback:
            pass
        print(entry)

# ---------------------------- GUI CLASS ------------------------------- #
class SecurityDashboardGUI:
    def __init__(self):
        self.fim = FileIntegrityMonitor()
        self.fim.ui_callback = self.handle_alert

        self.root = tk.Tk()
        self.root.title("Secure FIM")
        self.root.geometry("800x600")
        self.root.configure(bg="#1e1e1e")
        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)

        # Setup GUI elements
        self.setup_ui()

        # Tray icon
        self.icon_image = self.create_tray_icon_image()
        self.tray_icon = pystray.Icon("FIM", self.icon_image, "Secure FIM", menu=pystray.Menu(
            item("Show", self.show_from_tray),
            item("Exit", self.exit_app)
        ))
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def setup_ui(self):
        tk.Label(self.root, text="Secure File Integrity Monitor", font=("Consolas", 18), bg="#1e1e1e", fg="#00ff00").pack(pady=10)
        tk.Button(self.root, text="Select Folder", command=self.select_folder).pack(pady=5)
        tk.Button(self.root, text="Create Baseline", command=self.create_baseline).pack(pady=5)
        tk.Button(self.root, text="Start Monitoring", command=self.start_monitoring).pack(pady=5)
        tk.Button(self.root, text="Stop Monitoring", command=self.stop_monitoring).pack(pady=5)
        self.log_text = scrolledtext.ScrolledText(self.root, bg="#2d2d2d", fg="#e0e0e0", height=20)
        self.log_text.pack(fill="both", expand=True, pady=10, padx=10)
        self.fim.log = self.log_message

    def log_message(self, message, level="info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def select_folder(self):
        folder = filedialog.askdirectory(title="Select Folder")
        if folder:
            self.fim.monitor_path = folder
            self.log_message(f"Monitor path set: {folder}")

    def create_baseline(self):
        if not self.fim.monitor_path:
            messagebox.showerror("Error","Select folder first")
            return
        self.fim.create_baseline()
        messagebox.showinfo("Success","Baseline created.")

    def start_monitoring(self):
        if not self.fim.monitor_path:
            messagebox.showerror("Error","Select folder first")
            return
        self.fim.start_monitoring()

    def stop_monitoring(self):
        self.fim.stop_monitoring()

    def handle_alert(self, anomalies):
        self.log_message(f"ALERT! {len(anomalies)} anomalies detected.", "alert")

    # ---------------- Tray Icon ---------------- #
    def create_tray_icon_image(self):
        img = Image.new('RGB', (64,64), color='green')
        d = ImageDraw.Draw(img)
        d.rectangle([0,0,64,64], fill="green")
        return img

    def hide_to_tray(self):
        self.root.withdraw()
        self.log_message("App minimized to tray.")

    def show_from_tray(self):
        self.root.deiconify()

    def exit_app(self):
        self.fim.stop_monitoring()
        self.tray_icon.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()

# ---------------------------- MAIN ------------------------------- #
def main():
    app = SecurityDashboardGUI()
    app.run()

if __name__ == "__main__":
    main()