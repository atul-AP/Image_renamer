# Batch Image Renamer Utility

A complete, production-ready desktop tool to batch-rename images in-place based on structured directory paths. It parses folder hierarchy metadata (Date, App, Region, Device), previews changes (Dry-Run), handles name collisions and read-only attributes safely, maintains a CSV mapping record (UTF-8-SIG for Excel compatibility), and supports one-click rollbacks.

The application is built using standard Python libraries and features a modern, clean, flat-style Tkinter GUI with full high-DPI scaling support.

---

## 🚀 Key Features

* **Folder Metadata Parsing**: Auto-detects folders matching a `YYYY-MM-DD` date pattern and parses downstream folders as `App`, `Region`, and `Device`. If no date pattern is found, falls back to parsing the last 4 path components.
* **Smart Filename Generation**: Automatically builds clean names using the pattern: `<date>_<app>_<region>_<seq>.<ext>` or `<date>_<app>_<seq>.<ext>` depending on the folder depth. Strips out invalid filesystem characters and replaces whitespace with underscores.
* **Deterministic Alphabetical Sorting**: Gathers images recursively and sorts them alphabetically by original filename before sequence numbers (e.g. `001`, `002`) are assigned.
* **Robust Collision Resolution**: Automatically resolves duplicate names in the batch or pre-existing files on disk by appending incremental suffixes (`_1`, `_2`), avoiding overwrite data loss.
* **Case-Change Safety**: Executes a safe two-step rename (source -> temporary -> target) on case-insensitive systems (Windows/macOS) when renaming files where only the case changes (e.g., `image.png` to `IMAGE.png`).
* **Protected File Skipping**: Skips directory symlinks, skips hidden/system files (using `ctypes` bindings on Windows and leading-dot filtering on Unix), and flags read-only files in the preview table.
* **Mapping CSV & Rollback**: Logs the complete renaming transaction into a `rename_mapping_YYYYMMDD_HHMMSS.csv` file inside the target directory. Provides a one-click rollback feature that reads this CSV and safely reverts files back to their exact original names, checking for target occupancy before renaming.
* **Standalone Executable**: PyInstaller specifications are provided to build a single, lightweight, double-clickable `.exe` that runs on Windows without requiring a Python installation.

---

## 🛠️ Project Structure

* **`image_renamer.py`**: The core source file containing the GUI class (`ImageRenamerApp`) and the backend module-level logic.
* **`test_image_renamer.py`**: A robust test suite containing 10 tests (8 unit tests and 2 integration tests) covering parser actions, sort sequences, collision resolution, CSV logs, flat folders, nested directories, and rollback state validation.
* **`ImageRenamer.spec`**: Configuration settings for PyInstaller packaging.
* **`.gitignore`**: Excludes virtual environments, Python bytecode, temporary testing folders (`test_dirs/`), and large PyInstaller build artifacts (`build/`, `dist/`).

---

## 💻 How to Run the Tool

### Option A: Running from Source (Python 3)
Ensure you have Python 3 installed. No external libraries are required (only standard library modules are used).

```bash
python image_renamer.py
```

### Option B: Running the Standalone Executable (Windows)
Go to the `dist` folder and double-click the pre-built application:
* [dist/ImageRenamer.exe](file:///d:/My%20projects/Imagerenamer/dist/ImageRenamer.exe)

---

## 📖 Step-by-Step Workflow Guide

### 1. Select the Base Folder
* Click **Browse...** or type a path into the **Base Folder Path** field.
* *Example Path*: `C:\User\Photos\2026-07-01\Instacart\NewYork`
* As soon as you enter a path, the **Parsed Metadata Fields** card updates to show what was extracted:
  * **Date**: `2026-07-01`
  * **App**: `Instacart`
  * **Region**: `NewYork`
  * **Device**: `unknown` (since the path was 3 levels deep from the date)

### 2. Run Preview (Dry-Run Mode)
* Click **Preview (Dry Run)**.
* The tool recursively scans the selected directory and its subfolders for image formats (`.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`, `.bmp`, `.tiff`). Non-images are ignored.
* The table lists all images sorted alphabetically by original filename:
  * **Original Filename** $\rightarrow$ **Proposed New Filename** $\rightarrow$ **Status** $\rightarrow$ **Relative Path**
* Review statuses:
  * **Pending**: Good to go.
  * **Collision Resolved**: A suffix like `_1` was appended because the name was already taken.
  * **Warning: Read-Only**: The file is write-protected. It will be skipped during execution to prevent crashes.

### 3. Execute Renaming
* Click **Rename**.
* Confirm the prompt. The utility will rename the files in-place and save a UTF-8-BOM CSV mapping log in the base folder (e.g. `rename_mapping_20260623_180000.csv`).
* The table columns update to show **Success**, **Skipped (Read-Only)**, or **Failed** (with error details).
* The CSV file can be opened directly in Microsoft Excel without text corruption because it includes a BOM.

### 4. Rollback (Undo Changes)
* If you need to revert the renaming operation:
  1. Click **Undo / Rollback...**.
  2. Select the CSV mapping file generated during the renaming step.
  3. Confirm the prompt.
  4. The tool will rename files back to their original names, update the preview table, and skip rollback if a target path is occupied (preventing overwrites).

---

## 🧪 Testing

The project uses `pytest` for unit and integration testing.

To run the complete test suite:
1. Install pytest:
   ```bash
   pip install pytest
   ```
2. Run pytest:
   ```bash
   pytest test_image_renamer.py
   ```

---

## 📦 Building the Standalone EXE

If you modify the source code and want to compile a new executable:
1. Install PyInstaller:
   ```bash
   pip install pyinstaller
   ```
2. Build the app:
   ```bash
   pyinstaller --onefile --windowed --name ImageRenamer image_renamer.py
   ```
This will rebuild `dist/ImageRenamer.exe`.