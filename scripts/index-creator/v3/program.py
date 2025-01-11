import os
import re
import json
from datetime import datetime
from pathlib import Path
from openai import OpenAI
import git
import hashlib

# Initialize OpenAI client
client = OpenAI()

# Constants
ASSISTANTS_PATH = Path('/home/daniel/Git/my-llm-assistants/finished/by-category')
START_MARKER = "<!-- index-start -->"
END_MARKER = "<!-- index-end -->"
CACHE_FILE = ".index_cache.json"

def find_repo_root():
    try:
        repo = git.Repo(Path.cwd(), search_parent_directories=True)
        return Path(repo.working_dir)
    except git.InvalidGitRepositoryError:
        raise Exception("Not in a git repository")

def get_file_hash(filepath):
    with open(filepath, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

def load_cache():
    cache_path = REPO_ROOT / CACHE_FILE
    if cache_path.exists():
        with open(cache_path, 'r') as f:
            return json.load(f)
    return {}

def save_cache(cache):
    cache_path = REPO_ROOT / CACHE_FILE
    with open(cache_path, 'w') as f:
        json.dump(cache, f, indent=2)

def get_markdown_files():
    print(f"Scanning for markdown files in: {ASSISTANTS_PATH}")
    files = []
    for filepath in ASSISTANTS_PATH.rglob('*.md'):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        files.append((filepath, content))
    return files

def extract_huggingface_url(content):
    patterns = [
        r'huggingface\.co/[^\s\)]+',
        r'hf\.co/[^\s\)]+',
        r'huggingface:[^\s\)]+',
    ]
    for pattern in patterns:
        match = re.search(pattern, content)
        if match:
            url = match.group(0)
            if not url.startswith('http'):
                url = 'https://' + url
            return url
    return None

def clean_title(filepath):
    return filepath.stem.replace('-', ' ').title()

def get_summary(content, filename, cache_entry=None):
    if cache_entry and 'description' in cache_entry:
        print(f"Using cached summary for: {filename}")
        return cache_entry['description']
    
    print(f"Generating summary for: {filename}")
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Provide a very concise summary in 1-2 short sentences only."},
                {"role": "user", "content": content}
            ]
        )
        summary = response.choices[0].message.content
        print(f"Summary generated: {summary[:50]}...")
        return summary
    except Exception as e:
        print(f"Error generating summary for {filename}: {str(e)}")
        return "Error generating summary"

def generate_formatted_list(files):
    print("\nGenerating formatted list...")
    content = "# LLM Assistants Index\n\n"
    entries = []
    cache = load_cache()

    for filepath, file_content in files:
        try:
            file_hash = get_file_hash(filepath)
            cache_key = str(filepath.relative_to(ASSISTANTS_PATH))
            cache_entry = cache.get(cache_key, {})

            # Check if file has changed
            if cache_entry.get('hash') == file_hash:
                print(f"Using cached data for {filepath.name}")
                entries.append({
                    'title': cache_entry['title'],
                    'description': cache_entry['description'],
                    'repo_link': cache_entry['repo_link'],
                    'hf_link': cache_entry['hf_link']
                })
                continue

            title = clean_title(filepath)
            description = get_summary(file_content, filepath.name, cache_entry)
            hf_url = extract_huggingface_url(file_content)
            relative_path = filepath.relative_to(REPO_ROOT)
            
            # Update cache
            cache[cache_key] = {
                'hash': file_hash,
                'title': title,
                'description': description,
                'repo_link': str(relative_path),
                'hf_link': hf_url
            }
            
            entries.append({
                'title': title,
                'description': description,
                'repo_link': str(relative_path),
                'hf_link': hf_url
            })
            
        except Exception as e:
            print(f"Error processing {filepath}: {str(e)}")
            continue
    
    # Save updated cache
    save_cache(cache)
    
    # Sort entries alphabetically by title
    entries.sort(key=lambda x: x['title'].lower())
    
    # Generate formatted content
    for entry in entries:
        content += f"## {entry['title']}\n\n"
        content += f"[![GitHub](https://img.shields.io/badge/GitHub-Source-black?style=flat-square&logo=github)]({entry['repo_link']}) "
        if entry['hf_link']:
            content += f"[![HuggingFace](https://img.shields.io/badge/🤗-Model-yellow?style=flat-square)]({entry['hf_link']})"
        content += f"\n\n{entry['description']}\n\n"
    
    return content

def update_readme():
    try:
        print("\n=== Starting README Update Process ===")
        
        # Find repository root
        global REPO_ROOT
        REPO_ROOT = find_repo_root()
        README_PATH = REPO_ROOT / 'README.md'
        
        print(f"Reading README from: {README_PATH}")
        with open(README_PATH, 'r', encoding='utf-8') as f:
            readme = f.read()

        files = get_markdown_files()
        print(f"\nGenerating index for {len(files)} files...")
        new_content = generate_formatted_list(files)
        
        # Update README content between markers
        if START_MARKER in readme and END_MARKER in readme:
            pattern = f"{START_MARKER}.*?{END_MARKER}"
            updated_content = f"{START_MARKER}\n{new_content}\n{END_MARKER}"
            readme = re.sub(pattern, updated_content, readme, flags=re.DOTALL)
        else:
            print("Markers not found in README")
            return
        
        print("Writing updated content to README.md...")
        with open(README_PATH, 'w', encoding='utf-8') as f:
            f.write(readme)
            
        print("\n=== README.md updated successfully! ===")
        
    except Exception as e:
        print(f"\nERROR: Failed to update README: {str(e)}")
        raise

if __name__ == "__main__":
    update_readme()