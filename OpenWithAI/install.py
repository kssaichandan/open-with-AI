import os
import subprocess
import sys

from registry import add_context_menu, add_startup


def install():
    print("Installing Open with AI...")

    print("Checking dependencies...")
    req = os.path.join(os.path.dirname(__file__), "requirements.txt")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", req], check=False)

    context_ok = add_context_menu()
    startup_ok = add_startup()

    if context_ok and startup_ok:
        print("Installation complete. Restart Explorer if the context-menu entry does not appear immediately.")
    else:
        print("Installation finished with warnings. Run this installer as a normal desktop user with permission to update HKCU registry keys.")


if __name__ == "__main__":
    install()

