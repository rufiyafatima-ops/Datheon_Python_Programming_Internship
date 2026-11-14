# Task 3: Automated File Organizer & Cleanup Utility

Sorts a cluttered folder (such as Downloads) into category sub-folders based on file extension.

## Features
- Categories: **Documents, Images, Videos, Audio, Archives, Code, Others** (extension map in `organizer.py`, easy to edit)
- Uses `os.scandir()`, `shutil.move()` and `pathlib`
- **Naming collisions** handled safely: `report.pdf` becomes `report (1).pdf` instead of being overwritten
- Handles `PermissionError`, `FileExistsError` and other OS errors per file, so one bad file never stops the run
- Skips sub-folders, hidden files, unfinished downloads and its own files
- `--dry-run` preview mode and a confirmation prompt before moving
- Refuses to run on a drive root or the home folder
- Logs to the console and to `organizer.log`, then prints an execution summary

## Run
```bash
python organizer.py                      # Downloads folder (asks first)
python organizer.py ~/Downloads --dry-run
python organizer.py "C:\Users\me\Desktop" --yes
```

## Example summary
```
====================================================
  EXECUTION SUMMARY
====================================================
  Folder             : /home/me/Downloads
  Items scanned      : 14
  Files relocated    : 10
  Renamed (collision): 2
  Skipped            : 4
  Failed             : 0
====================================================
```
> Tip: try `--dry-run` on a test folder first.
