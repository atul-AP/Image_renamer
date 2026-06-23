# -*- coding: utf-8 -*-
"""
Batch Image Renaming Utility
============================
A complete, production-ready Python script to batch-rename image files based on
a structured folder path, using a modern Tkinter GUI interface.

Usage:
------
1. Run the script using Python:
   python image_renamer.py

2. In the GUI:
   - Click "Browse" or type the base path of the folder to rename.
   - Click "Preview (Dry Run)" to scan the directory and preview target filenames.
   - Review any warnings (e.g., read-only files, collisions resolved).
   - Click "Rename" to execute the operation. This will rename the files in-place
     and save a mapping record CSV in the selected folder.
   - Click "Undo / Rollback" and select a mapping CSV file to restore original names.

Author: Antigravity AI
Date: June 2026
"""

import os
import re
import csv
import stat
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Support DPI scaling on Windows for crisp fonts
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass


# =====================================================================
# Core Logic Functions
# =====================================================================

import ctypes

def sanitize_filename_segment(segment):
    r"""
    Sanitizes a string to be a safe folder/filename segment.
    Removes invalid characters: / \ : * ? " < > |
    """
    if not segment:
        return "unknown"
    sanitized = re.sub(r'[\/\\\:\*\?\"\<\>\|]', '', segment)
    sanitized = re.sub(r'\s+', '_', sanitized.strip())
    return sanitized or "unknown"


def is_hidden_or_system(file_path):
    """
    Checks if a file or folder is hidden or a system file/folder.
    Works for Unix (leading dot) and Windows (using kernel32 file attributes).
    """
    basename = os.path.basename(file_path)
    if basename.startswith('.'):
        return True
    try:
        if os.name == 'nt':
            attrs = ctypes.windll.kernel32.GetFileAttributesW(file_path)
            if attrs != -1:
                # 2 is FILE_ATTRIBUTE_HIDDEN, 4 is FILE_ATTRIBUTE_SYSTEM
                return bool(attrs & (2 | 4))
    except Exception:
        pass
    return False


def parse_path_metadata(base_path):
    """
    Parses the folder path to extract metadata fields: date, app, region, device.
    Returns:
        metadata (dict): Contains 'date', 'app', 'region', 'device' (defaulting to 'unknown')
        pattern_parts (list): Segments to use for building the filename prefix.
    """
    if not base_path:
        return {
            'date': 'unknown',
            'app': 'unknown',
            'region': 'unknown',
            'device': 'unknown'
        }, []

    # Normalize path and split into individual directory parts
    norm_path = os.path.normpath(os.path.abspath(base_path))
    parts = []
    
    # Split path without using os.sep directly to handle potential mixed slashes
    temp_path = norm_path
    while True:
        parts_head, parts_tail = os.path.split(temp_path)
        if parts_tail:
            parts.insert(0, parts_tail)
            temp_path = parts_head
        else:
            if parts_head:
                parts.insert(0, parts_head)
            break
            
    # Filter out Windows drive letters or root paths (e.g. 'D:', '\\')
    clean_parts = []
    for part in parts:
        part_clean = part.strip()
        if not part_clean:
            continue
        # Skip drive letters like C: or D:
        if re.match(r'^[a-zA-Z]:\\?$', part_clean):
            continue
        # Skip pure slash characters
        if part_clean in ('/', '\\'):
            continue
        clean_parts.append(part_clean)

    # Search for a date segment matching YYYY-MM-DD
    date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
    date_idx = -1
    for idx, part in enumerate(clean_parts):
        if date_pattern.match(part):
            date_idx = idx
            break

    date, app, region, device = None, None, None, None
    present_fields = []

    if date_idx != -1:
        # Date found: extract subsequent elements in hierarchical order
        date = clean_parts[date_idx]
        present_fields.append(date)
        
        if date_idx + 1 < len(clean_parts):
            app = clean_parts[date_idx + 1]
            present_fields.append(app)
        if date_idx + 2 < len(clean_parts):
            region = clean_parts[date_idx + 2]
            present_fields.append(region)
        if date_idx + 3 < len(clean_parts):
            device = clean_parts[date_idx + 3]
            present_fields.append(device)
    else:
        # Fallback: parse last segments of the path
        n = len(clean_parts)
        if n >= 4:
            date, app, region, device = clean_parts[-4], clean_parts[-3], clean_parts[-2], clean_parts[-1]
            present_fields = [date, app, region, device]
        elif n == 3:
            date, app, region = clean_parts[-3], clean_parts[-2], clean_parts[-1]
            present_fields = [date, app, region]
        elif n == 2:
            date, app = clean_parts[-2], clean_parts[-1]
            present_fields = [date, app]
        elif n == 1:
            date = clean_parts[-1]
            present_fields = [date]

    # Sanitize parsed fields to prevent illegal filename characters
    date = sanitize_filename_segment(date)
    app = sanitize_filename_segment(app)
    region = sanitize_filename_segment(region)
    device = sanitize_filename_segment(device)

    metadata = {
        'date': date,
        'app': app,
        'region': region,
        'device': device
    }
    
    # The filename pattern uses segments present in the path starting from date
    pattern_parts = [sanitize_filename_segment(p) for p in present_fields if p]
    if not pattern_parts:
        pattern_parts = ['unknown']

    return metadata, pattern_parts


def scan_images(base_path):
    """
    Recursively scans the base folder for image files.
    Supported extensions: .jpg, .jpeg, .png, .gif, .webp, .bmp, .tiff
    Filters out symlinks, hidden files/directories, and system directories.
    """
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff'}
    discovered_files = []
    
    if not os.path.exists(base_path):
        return []

    for root, dirs, files in os.walk(base_path, followlinks=False):
        # Prune hidden or system directories, and directory symlinks in-place
        dirs[:] = [d for d in dirs if not is_hidden_or_system(os.path.join(root, d)) and not os.path.islink(os.path.join(root, d))]
        
        for file in files:
            full_path = os.path.join(root, file)
            if os.path.islink(full_path):
                continue
            if is_hidden_or_system(full_path):
                continue
                
            ext = os.path.splitext(file)[1].lower()
            if ext in image_extensions:
                discovered_files.append(full_path)
                
    return discovered_files


def generate_mappings(discovered_files, pattern_parts):
    """
    Sorts files alphabetically by original filename, then constructs mappings
    including collision resolution (with safety limits), case-only renaming check,
    and read-only warnings.
    """
    # Sort files alphabetically by original filename (case-insensitive)
    # Sub-sort by full path to ensure deterministic order if basenames match
    sorted_files = sorted(discovered_files, key=lambda p: (os.path.basename(p).lower(), p.lower()))
    
    prefix = "_".join(pattern_parts)
    mappings = []
    target_paths_in_batch = set()

    for idx, file_path in enumerate(sorted_files, start=1):
        seq_str = f"{idx:03d}"
        ext = os.path.splitext(file_path)[1]
        
        # Build proposed base filename
        new_base = f"{prefix}_{seq_str}"
        new_name = f"{new_base}{ext}"
        
        dir_name = os.path.dirname(file_path)
        proposed_target = os.path.join(dir_name, new_name)
        
        # Collision resolution (append suffix if name is already taken)
        suffix_counter = 0
        final_new_name = new_name
        final_target = proposed_target
        
        # Collision check loop with a safety limit to prevent infinite loops
        max_loops = 1000
        loops = 0
        while final_target in target_paths_in_batch or (
            os.path.exists(final_target) and 
            os.path.abspath(final_target) != os.path.abspath(file_path)
        ):
            loops += 1
            if loops > max_loops:
                # Break loop and use unique tag to resolve collision
                import time
                unique_tag = f"_{int(time.time())}_{idx}"
                final_new_name = f"{new_base}{unique_tag}{ext}"
                final_target = os.path.join(dir_name, final_new_name)
                break
                
            suffix_counter += 1
            final_new_name = f"{new_base}_{suffix_counter}{ext}"
            final_target = os.path.join(dir_name, final_new_name)
            
        target_paths_in_batch.add(final_target)
        
        # Determine status & check if file is read-only
        is_readonly = False
        status = 'Pending'
        
        try:
            # On Windows, os.access(..., os.W_OK) returns False if the read-only attribute is set
            if not os.access(file_path, os.W_OK):
                is_readonly = True
                status = 'Warning: Read-Only'
        except Exception:
            pass
            
        if not is_readonly and suffix_counter > 0:
            status = 'Collision Resolved'
            
        # Case-only rename flag (e.g. image.png -> IMAGE.png on Windows)
        needs_temp_rename = False
        if os.path.abspath(file_path).lower() == os.path.abspath(final_target).lower() and file_path != final_target:
            needs_temp_rename = True
            
        mappings.append({
            'original_path': file_path,
            'original_name': os.path.basename(file_path),
            'new_name': final_new_name,
            'new_path': final_target,
            'sequence': seq_str,
            'is_readonly': is_readonly,
            'status': status,
            'needs_temp_rename': needs_temp_rename
        })
        
    return mappings


def save_mapping_to_csv(csv_path, csv_rows):
    """
    Saves renaming metadata records to a CSV file.
    Uses UTF-8 Sig (with BOM) for Excel compatibility.
    """
    fieldnames = ['original_name', 'new_name', 'full_path', 'date', 'app', 'region', 'device', 'sequence', 'rename_status']
    with open(csv_path, mode='w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in csv_rows:
            writer.writerow(row)


def load_mapping_from_csv(csv_path):
    """
    Loads renaming metadata records from a CSV file.
    Supports UTF-8 Sig (with BOM).
    """
    rows = []
    with open(csv_path, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        required_cols = {'original_name', 'new_name', 'full_path'}
        if not required_cols.issubset(set(reader.fieldnames or [])):
            raise ValueError("CSV structure is invalid. Missing required columns (original_name, new_name, full_path).")
        for row in reader:
            rows.append(row)
    return rows


# =====================================================================
# GUI Application Class
# =====================================================================

class ImageRenamerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Batch Image Renaming Utility")
        self.root.geometry("900x650")
        self.root.minsize(800, 500)
        
        self.mappings = []
        self.parsed_metadata = {}
        self.pattern_parts = []
        
        self._setup_styles()
        self._build_ui()

    def _setup_styles(self):
        """Configure modern styles for Tkinter widgets."""
        self.style = ttk.Style()
        self.style.theme_use("clam")
        
        # Colors
        self.bg_color = "#f8f9fa"
        self.card_bg = "#ffffff"
        self.primary_color = "#3a86c8"
        self.accent_color = "#2a6eb0"
        self.text_color = "#212529"
        self.border_color = "#dee2e6"
        self.success_color = "#28a745"
        self.warning_color = "#ffc107"
        
        self.root.configure(bg=self.bg_color)
        
        # Styles
        self.style.configure(".", background=self.bg_color, foreground=self.text_color, font=("Segoe UI", 10))
        self.style.configure("TFrame", background=self.bg_color)
        self.style.configure("Card.TFrame", background=self.card_bg, borderwidth=1, relief="solid")
        
        # Buttons
        self.style.configure("TButton", 
                             font=("Segoe UI Semibold", 10), 
                             padding=(12, 6), 
                             background=self.primary_color, 
                             foreground="#ffffff",
                             borderwidth=0)
        self.style.map("TButton",
                       background=[("active", self.accent_color), ("disabled", "#adb5bd")],
                       foreground=[("disabled", "#6c757d")])
                       
        self.style.configure("Secondary.TButton", 
                             background="#e2e6ea", 
                             foreground="#495057")
        self.style.map("Secondary.TButton",
                       background=[("active", "#dae0e5")])
                       
        self.style.configure("Danger.TButton", 
                             background="#dc3545", 
                             foreground="#ffffff")
        self.style.map("Danger.TButton",
                       background=[("active", "#bd2130")])

        # Entry
        self.style.configure("TEntry", fieldbackground="#ffffff", bordercolor=self.border_color, padding=5)
        
        # Treeview
        self.style.configure("Treeview", 
                             background="#ffffff", 
                             fieldbackground="#ffffff", 
                             foreground=self.text_color,
                             rowheight=25,
                             bordercolor=self.border_color,
                             borderwidth=1)
        self.style.configure("Treeview.Heading", 
                             font=("Segoe UI Semibold", 10), 
                             background="#e9ecef", 
                             foreground="#495057",
                             padding=5)
        self.style.map("Treeview", 
                       background=[("selected", "#007bff")],
                       foreground=[("selected", "#ffffff")])

    def _build_ui(self):
        # Header Banner
        header_frame = ttk.Frame(self.root, style="TFrame")
        header_frame.pack(fill="x", padx=20, pady=15)
        
        title_label = ttk.Label(header_frame, text="Batch Image Renamer", font=("Segoe UI Semibold", 16, "bold"), foreground="#1a3a5f")
        title_label.pack(anchor="w")
        
        subtitle_label = ttk.Label(header_frame, text="Rename images in-place based on folder hierarchy metadata structure.", font=("Segoe UI", 9), foreground="#6c757d")
        subtitle_label.pack(anchor="w")

        # Top Control Card (Folder Path input & Metadata)
        top_card = ttk.Frame(self.root, style="Card.TFrame")
        top_card.pack(fill="x", padx=20, pady=5)
        
        # Border emulation for Card
        top_card_inner = ttk.Frame(top_card, padding=15)
        top_card_inner.pack(fill="both", expand=True)
        top_card_inner.configure(style="TFrame")
        
        # Base Path Row
        path_label = ttk.Label(top_card_inner, text="Base Folder Path:", font=("Segoe UI Semibold", 10))
        path_label.grid(row=0, column=0, sticky="w", pady=(0, 5))
        
        self.path_var = tk.StringVar()
        self.path_var.trace_add("write", self._on_path_changed)
        self.path_entry = ttk.Entry(top_card_inner, textvariable=self.path_var)
        self.path_entry.grid(row=1, column=0, sticky="ew", padx=(0, 10))
        
        browse_btn = ttk.Button(top_card_inner, text="Browse...", command=self._browse_folder, style="Secondary.TButton")
        browse_btn.grid(row=1, column=1, sticky="w")
        
        top_card_inner.columnconfigure(0, weight=1)
        
        # Metadata Parser Preview Row
        meta_label = ttk.Label(top_card_inner, text="Parsed Metadata Fields:", font=("Segoe UI Semibold", 10))
        meta_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(15, 5))
        
        meta_subframe = ttk.Frame(top_card_inner)
        meta_subframe.grid(row=3, column=0, columnspan=2, sticky="ew")
        
        # Add labels for metadata columns
        self.meta_labels = {}
        meta_fields = [
            ("Date (Folder)", 'date'),
            ("App (Folder +1)", 'app'),
            ("Region (Folder +2)", 'region'),
            ("Device (Folder +3)", 'device')
        ]
        
        for idx, (label_text, key) in enumerate(meta_fields):
            cell_frame = ttk.Frame(meta_subframe, padding=(0, 0, 15, 0))
            cell_frame.pack(side="left", fill="both", expand=True)
            
            lbl_title = ttk.Label(cell_frame, text=label_text, font=("Segoe UI", 9), foreground="#6c757d")
            lbl_title.pack(anchor="w")
            
            lbl_val = ttk.Label(cell_frame, text="-", font=("Segoe UI Semibold", 10), background="#e9ecef", padding=(8, 4), anchor="w")
            lbl_val.pack(fill="x", pady=(2, 0))
            self.meta_labels[key] = lbl_val

        # Middle Table Card (File List)
        table_card = ttk.Frame(self.root, style="Card.TFrame")
        table_card.pack(fill="both", expand=True, padx=20, pady=10)
        
        table_inner = ttk.Frame(table_card, padding=10)
        table_inner.pack(fill="both", expand=True)
        table_inner.configure(style="TFrame")
        
        table_title = ttk.Label(table_inner, text="Images Rename Preview", font=("Segoe UI Semibold", 10))
        table_title.pack(anchor="w", pady=(0, 5))
        
        # Create Treeview and scrollbars
        tree_frame = ttk.Frame(table_inner)
        tree_frame.pack(fill="both", expand=True)
        
        scroll_y = ttk.Scrollbar(tree_frame, orient="vertical")
        scroll_y.pack(side="right", fill="y")
        
        scroll_x = ttk.Scrollbar(tree_frame, orient="horizontal")
        scroll_x.pack(side="bottom", fill="x")
        
        columns = ("orig_name", "new_name", "status", "rel_path")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                 yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        
        self.tree.heading("orig_name", text="Original Filename")
        self.tree.heading("new_name", text="Proposed New Filename")
        self.tree.heading("status", text="Status")
        self.tree.heading("rel_path", text="Relative Directory Path")
        
        self.tree.column("orig_name", width=200, anchor="w")
        self.tree.column("new_name", width=220, anchor="w")
        self.tree.column("status", width=150, anchor="center")
        self.tree.column("rel_path", width=200, anchor="w")
        
        self.tree.pack(fill="both", expand=True)
        
        scroll_y.config(command=self.tree.yview)
        scroll_x.config(command=self.tree.xview)
        
        # Tags for styling different statuses
        self.tree.tag_configure("readonly", foreground="#d9534f", background="#fdf7f7")
        self.tree.tag_configure("collision", foreground="#f0ad4e", background="#fefbf5")
        self.tree.tag_configure("success", foreground="#5cb85c", background="#f7fdf7")
        self.tree.tag_configure("reverted", foreground="#0275d8", background="#f7fbfd")

        # Bottom Actions Panel
        bottom_frame = ttk.Frame(self.root, padding=(20, 5, 20, 20))
        bottom_frame.pack(fill="x")
        
        # Status Label
        self.status_var = tk.StringVar(value="Ready. Select a base folder to begin.")
        self.status_lbl = ttk.Label(bottom_frame, textvariable=self.status_var, font=("Segoe UI Semibold", 10), foreground="#495057")
        self.status_lbl.pack(side="left", pady=10)
        
        # Buttons frame (right-aligned)
        btn_frame = ttk.Frame(bottom_frame)
        btn_frame.pack(side="right")
        
        self.undo_btn = ttk.Button(btn_frame, text="Undo / Rollback...", command=self._on_rollback, style="Secondary.TButton")
        self.undo_btn.pack(side="left", padx=5)
        
        self.preview_btn = ttk.Button(btn_frame, text="Preview (Dry Run)", command=self._on_preview, style="Secondary.TButton")
        self.preview_btn.pack(side="left", padx=5)
        
        self.rename_btn = ttk.Button(btn_frame, text="Rename", command=self._on_rename)
        self.rename_btn.pack(side="left", padx=5)

    # =====================================================================
    # UI Event Handlers
    # =====================================================================

    def _browse_folder(self):
        selected_dir = filedialog.askdirectory(title="Select Base Images Folder")
        if selected_dir:
            self.path_var.set(selected_dir)
            self._on_preview()

    def _on_path_changed(self, *args):
        # Update metadata display dynamically as path is typed or selected
        path = self.path_var.get()
        self.parsed_metadata, self.pattern_parts = parse_path_metadata(path)
        
        # Display parsed values or default empty marker
        for key, val in self.parsed_metadata.items():
            lbl = self.meta_labels.get(key)
            if lbl:
                if path.strip() and val != "unknown":
                    lbl.config(text=val, background="#e8f4fd", foreground="#0b5ed7")
                else:
                    lbl.config(text=val if path.strip() else "-", background="#e9ecef", foreground="#6c757d")

    def _on_preview(self):
        """Scans folder, runs logic in dry-run/preview mode, and populates the table."""
        path = self.path_var.get().strip()
        if not path:
            self.status_var.set("Error: Base folder path is empty.")
            messagebox.showwarning("Empty Path", "Please enter or browse to a valid base folder path.")
            return

        if not os.path.exists(path):
            self.status_var.set(f"Error: Path '{path}' does not exist.")
            messagebox.showerror("Invalid Path", f"The directory '{path}' does not exist.")
            return

        # Clear existing table
        self.tree.delete(*self.tree.get_children())
        self.status_var.set("Scanning directory for images...")
        self.root.update_idletasks()

        # Update metadata from parsed path
        self.parsed_metadata, self.pattern_parts = parse_path_metadata(path)
        self._on_path_changed() # Force refresh display styling

        # Scan for files
        discovered = scan_images(path)
        if not discovered:
            self.status_var.set("No image files found in the directory.")
            self.mappings = []
            messagebox.showinfo("No Images Found", "No supported image files (.jpg, .jpeg, .png, .gif, .webp, .bmp, .tiff) were found in the selected folder.")
            return

        # Generate proposed mapping
        self.mappings = generate_mappings(discovered, self.pattern_parts)
        
        # Populate table
        readonly_count = 0
        collision_count = 0
        
        for item in self.mappings:
            rel_dir = os.path.relpath(os.path.dirname(item['original_path']), path)
            if rel_dir == ".":
                rel_dir = "(base folder)"
                
            tags = ()
            if item['is_readonly']:
                tags = ("readonly",)
                readonly_count += 1
            elif "Collision" in item['status']:
                tags = ("collision",)
                collision_count += 1

            self.tree.insert("", "end", values=(
                item['original_name'],
                item['new_name'],
                item['status'],
                rel_dir
            ), tags=tags)
            
        status_msg = f"Preview: Found {len(self.mappings)} files."
        if readonly_count > 0:
            status_msg += f" {readonly_count} file(s) are read-only (will be skipped)."
        if collision_count > 0:
            status_msg += f" {collision_count} name collisions resolved with suffixes."
            
        self.status_var.set(status_msg)

    def _on_rename(self):
        """Executes the in-place renaming of files and saves the CSV mapping record."""
        if not self.mappings:
            messagebox.showwarning("No Files", "Please select a directory and click Preview first.")
            return

        # Double check if any files are pending rename
        writable_files = [m for m in self.mappings if not m['is_readonly']]
        if not writable_files:
            messagebox.showwarning("No Renamable Files", "All files in the preview are read-only or no files are queued.")
            return

        confirm = messagebox.askyesno("Confirm Rename", 
                                      f"Are you sure you want to rename {len(writable_files)} files in-place?\n"
                                      f"A CSV mapping report will be generated.")
        if not confirm:
            return

        self.status_var.set("Renaming files in progress...")
        self.root.update_idletasks()

        base_dir = os.path.abspath(self.path_var.get().strip())
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = f"rename_mapping_{timestamp}.csv"
        csv_path = os.path.join(base_dir, csv_filename)

        successful_renames = 0
        errors_count = 0
        
        # Prepare log entries for CSV
        csv_rows = []

        for idx, item in enumerate(self.mappings):
            orig_path = item['original_path']
            new_path = item['new_path']
            
            # Skip read-only files
            if item['is_readonly']:
                item['status'] = "Skipped (Read-Only)"
                csv_rows.append({
                    'original_name': item['original_name'],
                    'new_name': 'N/A (Skipped)',
                    'full_path': orig_path,
                    'date': self.parsed_metadata['date'],
                    'app': self.parsed_metadata['app'],
                    'region': self.parsed_metadata['region'],
                    'device': self.parsed_metadata['device'],
                    'sequence': item['sequence'],
                    'rename_status': 'skipped_readonly'
                })
                continue

            try:
                # Perform the in-place rename
                # If target differs only in case, use a temporary file to force update on case-insensitive filesystems
                if item.get('needs_temp_rename') or (orig_path.lower() == new_path.lower() and orig_path != new_path):
                    temp_path = orig_path + ".case_temp"
                    os.rename(orig_path, temp_path)
                    os.rename(temp_path, new_path)
                else:
                    os.rename(orig_path, new_path)
                item['status'] = "Success"
                successful_renames += 1
                
                # Add to CSV list
                csv_rows.append({
                    'original_name': item['original_name'],
                    'new_name': item['new_name'],
                    'full_path': new_path,
                    'date': self.parsed_metadata['date'],
                    'app': self.parsed_metadata['app'],
                    'region': self.parsed_metadata['region'],
                    'device': self.parsed_metadata['device'],
                    'sequence': item['sequence'],
                    'rename_status': 'success'
                })
            except Exception as e:
                item['status'] = f"Failed: {str(e)}"
                errors_count += 1
                csv_rows.append({
                    'original_name': item['original_name'],
                    'new_name': 'N/A (Error)',
                    'full_path': orig_path,
                    'date': self.parsed_metadata['date'],
                    'app': self.parsed_metadata['app'],
                    'region': self.parsed_metadata['region'],
                    'device': self.parsed_metadata['device'],
                    'sequence': item['sequence'],
                    'rename_status': f"error: {str(e)}"
                })

        # Save mapping to CSV
        try:
            save_mapping_to_csv(csv_path, csv_rows)
            save_csv_msg = f"Mapping CSV saved as: {csv_filename}"
        except Exception as csv_err:
            save_csv_msg = f"Error saving CSV: {str(csv_err)}"
            messagebox.showerror("CSV Error", f"Could not save mapping CSV:\n{str(csv_err)}")

        # Refresh preview table with updated statuses
        self.tree.delete(*self.tree.get_children())
        for item in self.mappings:
            rel_dir = os.path.relpath(os.path.dirname(item['original_path']), base_dir)
            if rel_dir == ".":
                rel_dir = "(base folder)"
                
            tags = ()
            if item['status'] == "Success":
                tags = ("success",)
            elif "Failed" in item['status'] or "Skipped" in item['status']:
                tags = ("readonly",)

            self.tree.insert("", "end", values=(
                item['original_name'],
                item['new_name'],
                item['status'],
                rel_dir
            ), tags=tags)

        # Show final report message
        result_msg = f"Rename Completed: {successful_renames} successful, {errors_count} failed."
        self.status_var.set(f"{result_msg} | {save_csv_msg}")
        
        # Inform user
        info_text = f"Successfully renamed {successful_renames} image files.\n"
        if errors_count > 0:
            info_text += f"Failed to rename {errors_count} files (see list for details).\n"
        info_text += f"\nMapping log file saved to folder:\n{csv_path}"
        
        messagebox.showinfo("Renaming Completed", info_text)

    def _on_rollback(self):
        """Loads a CSV mapping file and rolls back files to their original names."""
        csv_file = filedialog.askopenfilename(
            title="Select Rename Mapping CSV for Rollback",
            filetypes=[("CSV Files", "*.csv")]
        )
        if not csv_file:
            return

        confirm = messagebox.askyesno("Confirm Undo", 
                                      "Are you sure you want to rollback renaming based on this CSV file?\n"
                                      "This will attempt to restore original file names.")
        if not confirm:
            return

        self.status_var.set("Rollback operation in progress...")
        self.root.update_idletasks()

        revert_success = 0
        revert_fail = 0
        revert_skipped = 0
        
        self.tree.delete(*self.tree.get_children())
        rolled_back_mappings = []

        try:
            rows = load_mapping_from_csv(csv_file)
            for row in rows:
                original_name = row['original_name']
                new_name = row['new_name']
                full_path = row['full_path']
                rename_status = row.get('rename_status', '')

                # Skip rows that were originally skipped or failed
                if rename_status in ('skipped_readonly', 'skipped') or 'error' in rename_status or new_name == 'N/A (Skipped)':
                    revert_skipped += 1
                    rolled_back_mappings.append({
                        'original_name': original_name,
                        'new_name': new_name,
                        'status': 'Skipped Rollback (Not Renamed)',
                        'rel_dir': os.path.dirname(full_path)
                    })
                    continue

                if not os.path.exists(full_path):
                    # File is missing at its renamed full_path
                    revert_fail += 1
                    rolled_back_mappings.append({
                        'original_name': original_name,
                        'new_name': new_name,
                        'status': 'Error: Renamed file not found',
                        'rel_dir': os.path.dirname(full_path)
                    })
                    continue

                # Construct original file path (renamed file's directory + original filename)
                original_path = os.path.join(os.path.dirname(full_path), original_name)

                # Check if original path already has a file (to avoid overwriting)
                if os.path.exists(original_path) and os.path.abspath(original_path) != os.path.abspath(full_path):
                    revert_fail += 1
                    rolled_back_mappings.append({
                        'original_name': original_name,
                        'new_name': new_name,
                        'status': 'Error: Original target name already occupied',
                        'rel_dir': os.path.dirname(full_path)
                    })
                    continue

                try:
                    # Revert rename
                    os.rename(full_path, original_path)
                    revert_success += 1
                    rolled_back_mappings.append({
                        'original_name': original_name,
                        'new_name': new_name,
                        'status': 'Reverted',
                        'rel_dir': os.path.dirname(full_path)
                    })
                except Exception as e:
                    revert_fail += 1
                    rolled_back_mappings.append({
                        'original_name': original_name,
                        'new_name': new_name,
                        'status': f"Revert Failed: {str(e)}",
                        'rel_dir': os.path.dirname(full_path)
                    })

            # Populate preview table with rollback results
            for r_item in rolled_back_mappings:
                tags = ()
                if r_item['status'] == "Reverted":
                    tags = ("reverted",)
                elif "Error" in r_item['status'] or "Failed" in r_item['status']:
                    tags = ("readonly",)

                self.tree.insert("", "end", values=(
                    r_item['original_name'],
                    r_item['new_name'],
                    r_item['status'],
                    r_item['rel_dir']
                ), tags=tags)

            status_msg = f"Rollback finished. Restored: {revert_success}. Failed: {revert_fail}. Skipped: {revert_skipped}."
            self.status_var.set(status_msg)
            
            info_text = f"Rollback Complete:\n- {revert_success} file(s) successfully reverted.\n- {revert_fail} file(s) failed."
            if revert_skipped > 0:
                info_text += f"\n- {revert_skipped} row(s) skipped (were not renamed initially)."
                
            messagebox.showinfo("Rollback Completed", info_text)

        except Exception as csv_err:
            self.status_var.set("Error performing rollback.")
            messagebox.showerror("Rollback Error", f"Could not read mapping CSV or execute rollback:\n{str(csv_err)}")


# =====================================================================
# Main Execution Entrypoint
# =====================================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = ImageRenamerApp(root)
    root.mainloop()
