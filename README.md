# Open with AI

Open with AI is a Windows desktop helper that adds an **Open with AI** option to File Explorer.

It lets you:

- right-click one or many files
- choose which AI site to open
- choose which browser to use
- copy the selected files to the Windows clipboard as real files
- press `Ctrl+V` inside the AI chat/upload box to attach them quickly

The app is built with Python and Tkinter and is designed for local desktop use on Windows.

## What It Does

When you select files in File Explorer and click **Open with AI**:

1. the app gathers all selected files
2. it opens a desktop popup
3. you choose the browser and AI target
4. it opens the AI website in your browser
5. it copies the selected files to the Windows clipboard
6. you can paste the files into supported AI chat/upload areas with `Ctrl+V`

It currently supports these built-in AI targets:

- Claude
- ChatGPT
- DeepSeek
- Gemini

You can also add custom AI URLs and custom browser executables from the popup.

## Features

- Windows File Explorer context-menu integration
- multi-file selection support
- folder selection support from Explorer context menu
- tray app with default browser / default AI settings
- clipboard-based file handoff for fast uploads
- custom AI and custom browser support
- local desktop settings support

## Project Structure

```text
OpenWithAI/
  main.py          # tray app entry point and Explorer context-menu flow
  popup.py         # desktop UI and clipboard/file launch workflow
  browser.py       # browser detection and AI URL launch logic
  registry.py      # Windows registry integration for context menu/startup
  install.py       # installation helper
  uninstall.py     # uninstallation helper
  settings.py      # local config and runtime path handling
  history.py       # recent launch history
  ipc.py           # multi-process queue/lock handling for Explorer selections
  requirements.txt # Python dependencies
```

## Requirements

- Windows 10 or Windows 11
- Python 3.11+ recommended
- PowerShell

## Quick Start

If you want to download, install, and run the app using a single PowerShell command, use this:

```powershell
git clone https://github.com/kssaichandan/open-with-AI.git; Set-Location open-with-AI; python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r OpenWithAI\requirements.txt; .\.venv\Scripts\python.exe OpenWithAI\install.py; .\.venv\Scripts\python.exe OpenWithAI\main.py
```

After that:

1. look for the tray icon
2. open File Explorer
3. right-click one or more files
4. click **Open with AI**
5. choose the browser and AI
6. click **Confirm and Open in Browser**
7. click the AI chat/upload area and press `Ctrl+V`

If you want the manual setup steps instead, use the installation section below.

## Installation

### 1. Create a virtual environment

```powershell
python -m venv .venv
```

### 2. Activate the virtual environment

```powershell
.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.venv\Scripts\Activate.ps1
```

### 3. Install Python dependencies

```powershell
pip install -r OpenWithAI\requirements.txt
```

### 4. Install the Windows Explorer integration

```powershell
python OpenWithAI\install.py
```

This adds:

- the **Open with AI** right-click menu in File Explorer
- the startup entry for the tray app

### 5. Start the tray application

```powershell
python OpenWithAI\main.py
```

When it is running, you should see the tray icon.

## How to Use

### Use from File Explorer

This is the main way to use the app.

1. Open File Explorer.
2. Select one file or multiple files.
3. Right-click the selection.
4. Click **Open with AI**.
5. The popup window will open.
6. Choose:
   - the browser
   - the AI destination
7. Click **Confirm and Open in Browser**.
8. The chosen AI page opens in your browser.
9. Click inside the chat box or upload area.
10. Press `Ctrl+V`.

The selected files are copied to the Windows clipboard, so supported AI sites can receive them as pasted files.

### Use from the tray icon

When the tray app is running, you can:

- set the default browser
- set the default AI
- uninstall the Explorer menu/startup entry

### Use the keyboard shortcut

Press:

```text
Ctrl + Shift + A
```

This opens your default AI using your default browser.

### Add custom AI sites

Inside the popup:

1. click **Add Custom AI**
2. enter the AI name
3. enter the AI URL

This is useful for services like Perplexity or any custom web-based AI tool.

### Add a custom browser

Inside the popup:

1. click **Add Custom Browser**
2. choose the browser executable (`.exe`)

This lets you launch the AI page in browsers beyond the built-in list.

## Uninstall Explorer Integration

If you want to remove the right-click menu and startup entry:

```powershell
python OpenWithAI\uninstall.py
```

## How Uploading Works

This app does **not** directly automate every AI website upload UI.

Instead, it uses the most reliable generic desktop flow:

- open the AI site in your browser
- place the selected files on the Windows clipboard
- let you paste the files with `Ctrl+V`

Why this approach:

- it works across multiple AI sites
- it avoids fragile browser DOM automation
- it keeps the app simpler and safer

Important note:

- whether the site accepts pasted files depends on that specific AI website
- if a site does not accept pasted files, use its attach button or drag-and-drop

## Supported Browser Behavior

Built-in browser detection includes:

- Chrome
- Firefox
- Edge
- Brave

You can also register a custom browser executable from the popup UI.

## Development Notes

Useful checks:

```powershell
python -m compileall OpenWithAI
```

Run the popup directly with test files:

```powershell
python OpenWithAI\main.py "C:\path\to\file1.pdf" "C:\path\to\file2.png"
```

## Security / Privacy Notes

- the app runs locally on your machine
- selected file contents are not uploaded by the app itself
- files are copied to the Windows clipboard for you to paste into AI sites
- some local app settings are stored on your device for normal desktop operation

## GitHub Remote

Repository:

```text
https://github.com/kssaichandan/open-with-AI.git
```
