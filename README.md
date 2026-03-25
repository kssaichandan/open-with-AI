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
- local history of recent launches
- safer local config storage in `LocalAppData`

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

## Download / Clone

```powershell
git clone https://github.com/kssaichandan/open-with-AI.git
cd open-with-AI
```

## Setup

Create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r OpenWithAI\requirements.txt
```

If PowerShell blocks activation, run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.venv\Scripts\Activate.ps1
```

## Run the App

Start the tray application:

```powershell
python OpenWithAI\main.py
```

Once running:

- look for the tray icon
- set your default browser
- set your default AI
- use `Ctrl+Shift+A` to open your default AI quickly

## Install File Explorer Integration

To add the right-click **Open with AI** option:

```powershell
python OpenWithAI\install.py
```

After installing:

1. open File Explorer
2. select one or more files
3. right-click
4. click **Open with AI**
5. choose browser and AI target
6. click **Confirm and Open in Browser**
7. inside the AI page, click the chat/upload area and press `Ctrl+V`

If the menu does not appear immediately, restart Explorer or sign out/in once.

## Uninstall Explorer Integration

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

## Configuration

The app stores local settings in:

```text
%LOCALAPPDATA%\OpenWithAI\
```

This includes:

- config
- logs
- runtime queue/lock files
- recent history

These local files are intentionally not committed to git.

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
- local history may contain file paths, so avoid sharing your local app-data folder

## GitHub Remote

Repository:

```text
https://github.com/kssaichandan/open-with-AI.git
```
