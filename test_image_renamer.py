import os
import csv
import pytest
from image_renamer import (
    parse_path_metadata,
    scan_images,
    generate_mappings,
    save_mapping_to_csv,
    load_mapping_from_csv
)

# =====================================================================
# Unit Tests for Path Metadata Parser
# =====================================================================

def test_parse_path_metadata_with_date():
    # Test case: Standard structured path with a date matching YYYY-MM-DD
    path = r"C:\User\images\2026-07-01\Instacart\NewYork\iPhone"
    meta, pattern = parse_path_metadata(path)
    
    assert meta == {
        'date': '2026-07-01',
        'app': 'Instacart',
        'region': 'NewYork',
        'device': 'iPhone'
    }
    assert pattern == ['2026-07-01', 'Instacart', 'NewYork', 'iPhone']


def test_parse_path_metadata_short_with_date():
    # Test case: Shorter structured path with date, missing region/device
    path = r"/user/images/2026-07-01/Instacart"
    meta, pattern = parse_path_metadata(path)
    
    assert meta == {
        'date': '2026-07-01',
        'app': 'Instacart',
        'region': 'unknown',
        'device': 'unknown'
    }
    assert pattern == ['2026-07-01', 'Instacart']


def test_parse_path_metadata_no_date_fallback():
    # Test case: Path without any date pattern. Should fall back to last 4 components.
    path = r"/user/images/Instacart/NewYork/iPhone"
    meta, pattern = parse_path_metadata(path)
    
    assert meta == {
        'date': 'images',
        'app': 'Instacart',
        'region': 'NewYork',
        'device': 'iPhone'
    }
    assert pattern == ['images', 'Instacart', 'NewYork', 'iPhone']


def test_parse_path_metadata_no_date_fallback_short():
    # Test case: Very short path without date pattern.
    path = r"C:\OnlyApp\OnlyRegion"
    meta, pattern = parse_path_metadata(path)
    
    assert meta == {
        'date': 'OnlyApp',
        'app': 'OnlyRegion',
        'region': 'unknown',
        'device': 'unknown'
    }
    assert pattern == ['OnlyApp', 'OnlyRegion']


# =====================================================================
# Unit Tests for Sort Logic and Filename Generation
# =====================================================================

def test_generate_mappings_sorting(monkeypatch):
    # Mock os.access to return True so missing files are not flagged as read-only
    monkeypatch.setattr(os, "access", lambda path, mode: True)
    
    # Files should be sorted alphabetically by original basename (case-insensitive)
    discovered_files = [
        r"/base/date/app/photo3.png",
        r"/base/date/app/Photo1.png",
        r"/base/date/app/photo2.jpg",
    ]
    pattern_parts = ["2026-07-01", "Instacart"]
    
    mappings = generate_mappings(discovered_files, pattern_parts)
    
    # Basenames sorted alphabetically: Photo1.png, photo2.jpg, photo3.png
    sorted_orig_names = [m['original_name'] for m in mappings]
    assert sorted_orig_names == ["Photo1.png", "photo2.jpg", "photo3.png"]
    
    # Check sequences and extension preservation
    assert mappings[0]['sequence'] == "001"
    assert mappings[0]['new_name'] == "2026-07-01_Instacart_001.png"
    
    assert mappings[1]['sequence'] == "002"
    assert mappings[1]['new_name'] == "2026-07-01_Instacart_002.jpg"
    
    assert mappings[2]['sequence'] == "003"
    assert mappings[2]['new_name'] == "2026-07-01_Instacart_003.png"


# =====================================================================
# Unit Tests for Naming Collision Resolution
# =====================================================================

def test_generate_mappings_collision_handling(monkeypatch):
    # Mock os.access to return True so missing files are not flagged as read-only
    monkeypatch.setattr(os, "access", lambda path, mode: True)
    
    # Mock os.path.exists to simulate that target file '2026-07-01_Instacart_001.png'
    # already exists on disk, forcing a suffix to resolve collision.
    def mock_exists(path):
        # Only simulate collision for the specific first target name
        if os.path.basename(path) == "2026-07-01_Instacart_001.png":
            return True
        return False
        
    monkeypatch.setattr(os.path, "exists", mock_exists)
    
    discovered_files = [
        r"/base/date/app/photo1.png",
    ]
    pattern_parts = ["2026-07-01", "Instacart"]
    
    mappings = generate_mappings(discovered_files, pattern_parts)
    
    # Target name should have suffix '_1' appended to base before extension
    assert mappings[0]['new_name'] == "2026-07-01_Instacart_001_1.png"
    assert mappings[0]['status'] == "Collision Resolved"


# =====================================================================
# Unit Tests for CSV Mapping Reader/Writer
# =====================================================================

def test_csv_read_write(tmp_path):
    csv_file = tmp_path / "test_mapping.csv"
    csv_rows = [
        {
            'original_name': 'photo1.png',
            'new_name': '2026-07-01_Instacart_001.png',
            'full_path': r'/base/date/app/2026-07-01_Instacart_001.png',
            'date': '2026-07-01',
            'app': 'Instacart',
            'region': 'NewYork',
            'device': 'iPhone',
            'sequence': '001',
            'rename_status': 'success'
        },
        {
            'original_name': 'photo2.jpg',
            'new_name': 'N/A (Skipped)',
            'full_path': r'/base/date/app/photo2.jpg',
            'date': '2026-07-01',
            'app': 'Instacart',
            'region': 'NewYork',
            'device': 'iPhone',
            'sequence': '002',
            'rename_status': 'skipped_readonly'
        }
    ]
    
    # 1. Test Writing CSV
    save_mapping_to_csv(str(csv_file), csv_rows)
    assert csv_file.exists()
    
    # Verify contents written using dict reader
    with open(csv_file, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        written_rows = list(reader)
        
    assert len(written_rows) == 2
    assert written_rows[0]['original_name'] == 'photo1.png'
    assert written_rows[0]['rename_status'] == 'success'
    assert written_rows[1]['original_name'] == 'photo2.jpg'
    assert written_rows[1]['rename_status'] == 'skipped_readonly'
    
    # 2. Test Reading CSV
    loaded_rows = load_mapping_from_csv(str(csv_file))
    assert loaded_rows == written_rows


def test_csv_reader_invalid_format(tmp_path):
    invalid_csv = tmp_path / "invalid.csv"
    
    # Write a CSV missing 'full_path' column
    with open(invalid_csv, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['original_name', 'new_name'])  # Missing full_path
        writer.writerow(['photo1.png', 'photo_new.png'])
        
    with pytest.raises(ValueError) as excinfo:
        load_mapping_from_csv(str(invalid_csv))
        
    assert "CSV structure is invalid" in str(excinfo.value)


# =====================================================================
# Phase 2: Integration Tests on Real Temp Folder
# =====================================================================

def test_integration_flat_folder_rename_and_rollback(tmp_path):
    # Setup flat folder with structure matching date pattern
    base_dir = tmp_path / "2026-07-01" / "Instacart" / "NewYork"
    base_dir.mkdir(parents=True)
    
    # Create image files
    img1 = base_dir / "photo2.png"
    img2 = base_dir / "photo1.jpg"
    non_img = base_dir / "readme.txt"
    
    img1.write_text("png content")
    img2.write_text("jpg content")
    non_img.write_text("text content")
    
    base_dir_str = str(base_dir)
    
    # 1. Parse metadata
    meta, pattern = parse_path_metadata(base_dir_str)
    assert meta['date'] == "2026-07-01"
    assert meta['app'] == "Instacart"
    assert meta['region'] == "NewYork"
    
    # 2. Scan images (should filter out non_img)
    scanned = scan_images(base_dir_str)
    assert len(scanned) == 2
    # Verify non_img is not in scanned
    assert str(non_img) not in scanned
    
    # 3. Generate mappings (should sort alphabetically: photo1.jpg, photo2.png)
    mappings = generate_mappings(scanned, pattern)
    assert len(mappings) == 2
    assert mappings[0]['original_name'] == "photo1.jpg"
    assert mappings[1]['original_name'] == "photo2.png"
    
    assert mappings[0]['new_name'] == "2026-07-01_Instacart_NewYork_001.jpg"
    assert mappings[1]['new_name'] == "2026-07-01_Instacart_NewYork_002.png"
    
    # Dry-run check: verify files still have original names
    assert img1.exists()
    assert img2.exists()
    assert not os.path.exists(mappings[0]['new_path'])
    
    # 4. Execute Rename
    csv_rows = []
    for item in mappings:
        os.rename(item['original_path'], item['new_path'])
        csv_rows.append({
            'original_name': item['original_name'],
            'new_name': item['new_name'],
            'full_path': item['new_path'],
            'date': meta['date'],
            'app': meta['app'],
            'region': meta['region'],
            'device': meta['device'],
            'sequence': item['sequence'],
            'rename_status': 'success'
        })
        
    csv_file = base_dir / "mapping_log.csv"
    save_mapping_to_csv(str(csv_file), csv_rows)
    
    # Verify files renamed
    assert not img1.exists()
    assert not img2.exists()
    assert os.path.exists(mappings[0]['new_path'])
    assert os.path.exists(mappings[1]['new_path'])
    assert csv_file.exists()
    
    # 5. Execute Undo/Rollback from CSV
    loaded_rows = load_mapping_from_csv(str(csv_file))
    for row in loaded_rows:
        orig_name = row['original_name']
        curr_path = row['full_path']
        original_path = os.path.join(os.path.dirname(curr_path), orig_name)
        os.rename(curr_path, original_path)
        
    # Verify restored to original names
    assert img1.exists()
    assert img2.exists()
    assert not os.path.exists(mappings[0]['new_path'])
    assert not os.path.exists(mappings[1]['new_path'])


def test_integration_nested_subfolders_rename(tmp_path):
    # Setup nested folder tree
    base_dir = tmp_path / "2026-07-01" / "Instacart" / "NewYork"
    sub_dir = base_dir / "subfolder"
    sub_dir.mkdir(parents=True)
    
    # Create image in base dir and in sub dir
    img_base = base_dir / "b_photo.png"
    img_sub = sub_dir / "a_photo.jpg"
    non_img = sub_dir / "notes.txt"
    
    img_base.write_text("base img")
    img_sub.write_text("sub img")
    non_img.write_text("text content")
    
    base_dir_str = str(base_dir)
    
    meta, pattern = parse_path_metadata(base_dir_str)
    
    # 1. Scan recursively
    scanned = scan_images(base_dir_str)
    assert len(scanned) == 2
    assert str(img_base) in scanned
    assert str(img_sub) in scanned
    assert str(non_img) not in scanned
    
    # 2. Sort & Generate Mappings
    # sorted: a_photo.jpg (subfolder), b_photo.png (base folder)
    mappings = generate_mappings(scanned, pattern)
    assert len(mappings) == 2
    assert mappings[0]['original_name'] == "a_photo.jpg"
    assert mappings[1]['original_name'] == "b_photo.png"
    
    # Verify they rename in place (retaining respective folders)
    assert os.path.dirname(mappings[0]['new_path']) == str(sub_dir)
    assert os.path.dirname(mappings[1]['new_path']) == str(base_dir)
    
    assert mappings[0]['new_name'] == "2026-07-01_Instacart_NewYork_001.jpg"
    assert mappings[1]['new_name'] == "2026-07-01_Instacart_NewYork_002.png"
    
    # 3. Perform rename
    for item in mappings:
        os.rename(item['original_path'], item['new_path'])
        
    assert os.path.exists(mappings[0]['new_path'])
    assert os.path.exists(mappings[1]['new_path'])
    assert not img_base.exists()
    assert not img_sub.exists()
    # verify non-image was untouched
    assert non_img.exists()
