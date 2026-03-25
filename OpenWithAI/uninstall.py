from registry import remove_context_menu, remove_startup


def uninstall():
    print("Uninstalling Open with AI...")
    remove_context_menu()
    remove_startup()
    print("Uninstalled successfully.")


if __name__ == "__main__":
    uninstall()

