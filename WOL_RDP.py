import tkinter as tk
from tkinter import ttk, messagebox
import socket
import subprocess
import threading
import time
import os

# Przykładowa lista komputerów z portami
computers = [
    {"name": "Nazwa1", "mac": "podajAdres1", "ip": "ipkomputera", "port": 9, "port_rdp": 999,"info":"Adres do połączenia z pulpitem zdalnym : \n\n Adres"},
    {"name": "Nazwa2", "mac3": "podajAdres2", "ip2": "ipkomputera2", "port": 9, "port_rdp": 999,"info":"Adres do połączenia z pulpitem zdalnym : \n\n Adres"},
    {"name": "Nazwa3", "mac3": "podajAdres3", "ip3": "ipkomputera3", "port": 9, "port_rdp": 999,"info":"Adres do połączenia z pulpitem zdalnym : \n\n Adres"}
]

def send_magic_packet(mac_address, broadcast_ip, port):
    # Sprawdzenie poprawności MAC adresu
    if len(mac_address) != 12:
        raise ValueError("Adres MAC musi zawierać 12 znaków")
    
    # Zamiana MAC adresu na bajty
    mac_bytes = bytes.fromhex(mac_address)
    
    # Budowanie Magic Packet: 6 bajtów 0xFF + 16 razy MAC adres
    magic_packet = b'\xFF' * 6 + mac_bytes * 16
    
    # Konfiguracja socketu
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    
    # Wysyłanie Magic Packet
    sock.sendto(magic_packet, (broadcast_ip, port))
    sock.close()

def send_wake_on_lan():
    selected_computer = combo.get()
    
    # Znajdź wybrany komputer w liście
    for computer in computers:
        if computer["name"] == selected_computer:
            mac_address = computer["mac"]
            public_ip = computer["ip"]
            port = computer["port"]
            port_rdp = computer["port_rdp"]
            break
    else:
        messagebox.showwarning("Uwaga!", "Proszę wybrać komputer.")
        return
    
    try:
        # Wysyłanie Magic Packetu
        send_magic_packet(mac_address, public_ip, port)
        # Wyświetlanie komunikatu o sukcesie oraz dodatkowych informacji
        messagebox.showinfo("Sukces!", f"Komputer został włączony.\n\nInformacje o komputerze:\nNazwa: {selected_computer}\nMAC Address: {mac_address}\nPublic IP: {public_ip}\nPort: {port}")
        
        # Uruchomienie paska postępu w osobnym wątku
        threading.Thread(target=start_progress, daemon=True).start()
    except Exception as e:
        messagebox.showerror("Błąd!", f"Wystąpił błąd: {str(e)}")

def create_and_open_rdp_file(ip_address, port_rdp):
    # Tworzenie pliku RDP
    rdp_content = f"full address:s:{ip_address}:{port_rdp}\n"
    rdp_file_path = "remote_connection.rdp"
    
    with open(rdp_file_path, "w") as rdp_file:
        rdp_file.write(rdp_content)
    
    # Otwieranie pliku RDP
    try:
        subprocess.run(["mstsc", rdp_file_path], check=True)
    except Exception as e:
        messagebox.showerror("Błąd!", f"Nie udało się połączyć z pulpitem zdalnym: {str(e)}")
    
    # Usunięcie pliku po otwarciu
    os.remove(rdp_file_path)

def start_progress():
    # Funkcja uruchamiająca pasek postępu
    for i in range(30):
        time.sleep(1)
        progress['value'] = (i + 1) * (100 / 30)
        root.update_idletasks()
    progress['value'] = 100
    
    # Wyświetlanie komunikatu po upływie 30 sekund
    result = messagebox.askyesno("Informacja\n\n", "Minęło 30 sekund.\nKomputer najprawdopodobniej został już włączony\n\nCzy chcesz odpalić zdalne połączenie?")
    if result:
        selected_computer = combo.get()
        for computer in computers:
            if computer["name"] == selected_computer:
                ip_address = computer["ip"]
                port_rdp = computer["port_rdp"]
                create_and_open_rdp_file(ip_address, port_rdp)
                break

def show_author_info():
    author_info = (
        "Autor programu: \n"
        "Marcin Tomaszewski\n"
        "Email: tomaszewsky.marcin@gmail.com\n"
        "GitHub: github.com/martom93\n"
        "\n"
        "Program do Zdalnego włączania komputerów.\n"
    )
    messagebox.showinfo("Informacje o autorze", author_info)

def open_remote_desktop():
    selected_computer = combo.get()
    if not selected_computer:
        messagebox.showwarning("Uwaga!", "Proszę najpierw wybrać komputer z listy.")
        return
    
    for computer in computers:
        if computer["name"] == selected_computer:
            ip_address = computer["ip"]
            port_rdp = computer["port_rdp"]
            create_and_open_rdp_file(ip_address, port_rdp)
            break

# Tworzenie głównego okna
root = tk.Tk()
root.title("Zdalne odpalanie kompika")

# Ustawienia okna
root.geometry("300x250")
root.resizable(False, False)

# Funkcja do wyśrodkowania okna
def center_window(window, width, height):
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    window.geometry(f'{width}x{height}+{x}+{y}')

# Wyśrodkowanie okna
center_window(root, 420, 180)

# Tworzenie rozwijanej listy
tk.Label(root, text="Wybierz kompika:").pack(pady=5)
combo = ttk.Combobox(root, values=[computer["name"] for computer in computers])
combo.pack(pady=5)

# Przyciski
button_frame = tk.Frame(root)
button_frame.pack(pady=10)

send_button = tk.Button(button_frame, text="Odpal", command=send_wake_on_lan)
send_button.pack(side=tk.LEFT, padx=10)

remote_desktop_button = tk.Button(button_frame, text="Otwórz Pulpit Zdalny", command=open_remote_desktop)
remote_desktop_button.pack(side=tk.LEFT, padx=10)

author_button = tk.Button(button_frame, text="Autor", command=show_author_info)
author_button.pack(side=tk.LEFT)

# Pasek postępu
progress = ttk.Progressbar(root, length=280, mode='determinate')
progress.pack(pady=10)
progress['value'] = 0

# Uruchamianie głównej pętli aplikacji
root.mainloop()
