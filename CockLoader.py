import os
import re
import shutil
import subprocess
import sys
import time
import traceback

boot_start_time = time.time()

BASE = os.path.dirname(os.path.abspath(__file__))     # sve putanje su od ovdje, ne od trenutnog foldera
LOG_DIR = os.path.join(BASE, "COCKBOOT_LOG")
LOG_FILE_PATH = os.path.join(LOG_DIR, "cockload_log.txt")
COCKYOS_DIR = os.path.join(BASE, "COCKYOS")            # particije: COCKYOS/1, COCKYOS/2, ...
RECOVERY_DIR = os.path.join(BASE, "COCKRECOVERY")
BACKUP_DIR = os.path.join(BASE, "COCKBACKUP")
CACHE_DIR = os.path.join(BASE, "COCKYCACHE")           # zasebna particija za cache
CACHE_MARKER = ".cockycache"

_NAME_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*")


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def term_width():
    try:
        return shutil.get_terminal_size().columns
    except Exception:
        return 80


def center_print(text=""):
    w = term_width()
    print(text if len(text) > w else text.center(w))


def center_input(prompt):
    return input(" " * max((term_width() - len(prompt)) // 2, 0) + prompt).strip()


def header(title):
    clear_screen()
    for _ in range(3):
        print()
    center_print("==========================================")
    center_print(title)
    center_print("==========================================")
    print("\n")


def kernel_log(level, message):
    uptime = time.time() - boot_start_time
    py_version = sys.version.split()[0]
    log_line = f"[ {uptime:08.5f} ] [CockyOS/Kernel] [Py {py_version}] [{level}] {message}"
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as log_file:
            log_file.write(log_line + "\n")
    except Exception:
        pass
    return log_line


def safe_name(name, what):
    """Ime particije/backupa smije biti samo jedno ime foldera (bez / \\ ..)."""
    if not _NAME_RE.fullmatch(name):
        raise ValueError(f"Invalid {what} name '{name}' (use letters, numbers, _ . -).")
    return name


def first_existing(*candidates):
    for c in candidates:
        if os.path.exists(c):
            return c
    return candidates[0]


def ensure_cache():
    """COCKYCACHE particija: napravi je i označi markerom (kernel briše samo foldere s markerom)."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    marker = os.path.join(CACHE_DIR, CACHE_MARKER)
    if not os.path.exists(marker):
        if os.listdir(CACHE_DIR):
            raise RuntimeError(f"'{CACHE_DIR}' exists, is not empty and is not a COCKYCACHE.")
        with open(marker, "w") as f:
            f.write("COCKYCACHE - safe to delete everything in here except this file.\n")


def menu_clear_cache():
    header("     CockLoader - Clear COCKYCACHE        ")
    ensure_cache()
    count = 0
    for name in os.listdir(CACHE_DIR):
        if name == CACHE_MARKER:
            continue
        full = os.path.join(CACHE_DIR, name)
        count += 1
        if os.path.isdir(full):
            shutil.rmtree(full, ignore_errors=True)
        else:
            os.remove(full)
    kernel_log("SUCCESS", f"COCKYCACHE cleared ({count} top-level entries removed).")
    print(f"SUCCESS: COCKYCACHE cleared ({count} entries removed).")
    input("\nPress Enter to exit...")


def menu_restore_backup():
    header("     CockLoader - Backup Utility (RESTORE) ")
    src_name = safe_name(center_input("Enter backup folder name inside COCKBACKUP/ (e.g. backup_v1): "), "backup")
    src_path = os.path.join(BACKUP_DIR, src_name)
    if not os.path.isdir(src_path):
        raise FileNotFoundError(f"Backup folder '{src_name}' not found in 'COCKBACKUP/'.")

    dest_name = safe_name(center_input("Enter NEW target version/partition name in CockyOS (e.g. 2, custom_v1): "), "partition")
    dest_path = os.path.join(COCKYOS_DIR, dest_name)
    if os.path.exists(dest_path):
        if input(f"Partition '{dest_name}' already exists and will be REPLACED. Continue? [y/N] ").strip().lower() != "y":
            print("Cancelled.")
            input("\nPress Enter to exit...")
            return
        shutil.rmtree(dest_path)

    kernel_log("INFO", f"Restoring backup '{src_name}' from COCKBACKUP/ to CockyOS partition '{dest_name}'...")
    print(f"\nINFO: Copying backup '{src_name}' to CockyOS partition '{dest_name}'...")
    shutil.copytree(src_path, dest_path)
    kernel_log("SUCCESS", f"Successfully deployed backup '{src_name}' as CockyOS partition '{dest_name}'.")
    print(f"SUCCESS: Backup restored and deployed as CockyOS partition '{dest_name}'!")
    input("\nPress Enter to exit...")


def menu_recovery():
    header("         CockLoader - Recovery            ")
    rec_ver = safe_name(center_input("Enter Recovery version/ID (e.g. 1, 98): "), "recovery")
    recovery_file = first_existing(os.path.join(RECOVERY_DIR, f"Recovery{rec_ver}.py"),
                                   os.path.join(RECOVERY_DIR, "Recovery.py"))
    if not os.path.exists(recovery_file):
        raise FileNotFoundError(f"Recovery script 'Recovery{rec_ver}.py' or 'Recovery.py' not found in 'COCKRECOVERY/'.")

    kernel_log("RECOVERY", f"Booting into Recovery environment [{rec_ver}] using '{recovery_file}'")
    print(f"SUCCESS: Found Recovery [{rec_ver}]. Initializing recovery console...")
    time.sleep(0.6)
    subprocess.run([sys.executable, recovery_file], cwd=BASE, check=True)


def menu_boot():
    header("         CockLoader - CockyOS Boot        ")
    version = safe_name(center_input("Enter CockyOS version/partition to boot (e.g. 1, 2): "), "partition")
    version_dir = os.path.join(COCKYOS_DIR, version)

    clear_screen()
    kernel_log("INFO", f"Initializing boot sequence for partition '{version}' from '{version_dir}'")
    print(f"INFO: Mounting partition {version}...")
    time.sleep(0.3)

    if not os.path.isdir(version_dir):
        raise FileNotFoundError(f"CockyOS partition '{version}' does not exist in COCKYOS/.")

    config_file = first_existing(os.path.join(version_dir, "boot", "config.prop"),
                                 os.path.join(version_dir, "config.prop"),
                                 os.path.join(version_dir, f"config{version}.prop"))
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file missing in partition '{version}'.")

    config_data = {}
    with open(config_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                config_data[key.strip()] = value.strip()
    kernel_log("INFO", f"Successfully parsed configuration from {os.path.basename(config_file)}")

    print(f"INFO: Locating boot binary in partition {version}...")
    time.sleep(0.3)
    target_file = first_existing(os.path.join(version_dir, "boot", "CockBoot.py"),
                                 os.path.join(version_dir, "CockBoot.py"),
                                 os.path.join(version_dir, f"CockBoot_v{version}.py"))
    if not os.path.exists(target_file):
        raise FileNotFoundError(f"Boot script missing in partition '{version}'.")

    ensure_cache()
    b_build_ver = config_data.get("cockboot.build.ver", "Release")
    b_date = config_data.get("cockboot.build.date", "Unknown")
    b_time = config_data.get("cockboot.build.time", "Unknown")
    b_arch = config_data.get("cockboot.arch", "x86_64")
    verbose_flag = config_data.get("cockboot.verbose.boot", "false").lower() == "true"

    kernel_log("SUCCESS", f"Found target binary {os.path.basename(target_file)} | Build: {b_build_ver} | Arch: {b_arch}")
    print(f"SUCCESS: Mounted Partition [{version}] ({b_build_ver}) | Arch: {b_arch} | Build: {b_date} {b_time}")
    print(f"SUCCESS: COCKYCACHE ready at {CACHE_DIR}")
    print(f"INFO: Python {sys.version.split()[0]} ({sys.executable})")
    time.sleep(0.4)

    kernel_log("INFO", f"Runtime: Python {sys.version.split()[0]} at {sys.executable}")
    kernel_log("BOOT", f"Handing over execution to {os.path.basename(target_file)} (verbose={verbose_flag})")
    print("CockBoot starting!")
    time.sleep(0.6)

    boot_args = [sys.executable, target_file]
    if verbose_flag:
        boot_args.append("--verbose")
    env = dict(os.environ, COCKYCACHE=CACHE_DIR)
    subprocess.run(boot_args, cwd=BASE, env=env, check=True)


def main():
    header("           CockLoader v3.1                ")
    center_print("--- CHOOSE WHAT TO BOOT ---")
    center_print("[1] Normal Boot (CockyOS Partition)")
    center_print("[2] Recovery Mode")
    center_print("[3] Backup & Partition Management (COCKBACKUP)")
    center_print("[4] Clear COCKYCACHE")
    print("\n")

    while True:
        choice = center_input("Select boot option [1-4]: ")
        if choice in ("", "1"):
            return menu_boot()
        if choice == "2":
            return menu_recovery()
        if choice == "3":
            return menu_restore_backup()
        if choice == "4":
            return menu_clear_cache()
        center_print("Invalid option.")


try:
    main()
except (KeyboardInterrupt, EOFError):
    print()
    sys.exit(0)
except Exception as e:
    err_type = type(e).__name__
    kernel_log("PANIC_EXCEPTION", f"[{err_type}] {e}")
    kernel_log("TRACEBACK", traceback.format_exc().replace("\n", " | "))

    print("\nKERNEL PANIC: Unhandled Python Exception!")
    print(f"Type : {err_type}")
    print(f"Error: {e}")
    print(f"\nDetailed stack trace logged to '{LOG_FILE_PATH}'.")
    input("\nSystem Halted. Press Enter to exit...")
    sys.exit(1)
