import os
import shutil
from pathlib import Path

def get_target_dir():
    while True:
        target = input("Enter target directory path: ").strip()
        target_path = Path(target)
        
        if not target_path.exists():
            try:
                target_path.mkdir(parents=True)
                return target_path
            except Exception as e:
                print(f"Error creating directory: {e}")
                continue
                
        if not target_path.is_dir():
            print("Path exists but is not a directory. Please enter a valid directory path.")
            continue
            
        return target_path

def copy_markdown_files():
    source = Path('/home/daniel/Git/my-llm-assistants/finished/by-category')
    target = get_target_dir()
    
    for md_file in source.rglob('*.md'):
        dest_file = target / md_file.name
        shutil.copy2(md_file, dest_file)
        print(f"Copied {md_file.name}")

if __name__ == '__main__':
    copy_markdown_files()
 