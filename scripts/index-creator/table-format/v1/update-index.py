import os
import re
import json
import hashlib
from openai import OpenAI
from pathlib import Path
from dotenv import load_dotenv
import time

# Load environment variables
print("Loading environment variables...")
load_dotenv()

# Configure OpenAI
if not os.getenv('OPENAI_API_KEY'):
    raise Exception("OPENAI_API_KEY not found in environment variables")
print("OpenAI API key found")

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def find_repo_root():
    print("Searching for repository root...")
    current = Path.cwd()
    while current != current.parent:
        if (current / '.git').exists():
            print(f"Repository root found at: {current}")
            return current
        current = current.parent
    raise Exception("Not in a git repository")

# Constants
START_MARKER = "<!-- index-start -->"
END_MARKER = "<!-- index-end -->"
REPO_ROOT = find_repo_root()
BASE_PATH = REPO_ROOT / 'finished' / 'by-category'
README_PATH = REPO_ROOT / 'README.md'
CACHE_PATH = REPO_ROOT / '.index_cache.json'

def initialize_cache_from_readme():
    print("Checking for existing table in README.md...")
    try:
        with open(README_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract existing table content
        pattern = f"{START_MARKER}(.*?){END_MARKER}"
        match = re.search(pattern, content, re.DOTALL)
        
        if not match:
            print("No existing table found in README.md")
            return {}
            
        print("Found existing table, extracting data...")
        table_content = match.group(1).strip()
        
        # Skip header rows
        rows = table_content.split('\n')[2:]  # Skip header and separator rows
        
        cache = {}
        for row in rows:
            if not row.strip():
                continue
                
            # Parse the row using regex to handle pipes within cell content
            parts = re.findall(r'\|(.*?)\|', row)
            if len(parts) != 4:
                continue
                
            title, description, repo_link, hf_link = [p.strip() for p in parts]
            
            # Extract filepath from repo link
            repo_match = re.search(r'\[GitHub\]\((.*?)\)', repo_link)
            if not repo_match:
                continue
                
            filepath = repo_match.group(1)
            
            if os.path.exists(REPO_ROOT / filepath):
                file_hash = get_file_hash(REPO_ROOT / filepath)
                
                cache[filepath] = {
                    'hash': file_hash,
                    'title': title,
                    'description': description,
                    'repo_link': repo_link,
                    'hf_link': hf_link
                }
                print(f"Cached existing entry for: {filepath}")
        
        print(f"Initialized cache with {len(cache)} existing entries")
        return cache
    except Exception as e:
        print(f"Error initializing cache from README: {str(e)}")
        return {}

def load_cache():
    print("Loading cache...")
    if CACHE_PATH.exists():
        with open(CACHE_PATH, 'r') as f:
            cache = json.load(f)
        print(f"Loaded {len(cache)} cached entries")
        return cache
    
    print("No cache file found, initializing from existing README...")
    cache = initialize_cache_from_readme()
    save_cache(cache)
    return cache
def save_cache(cache):
    print(f"Saving {len(cache)} entries to cache...")
    with open(CACHE_PATH, 'w') as f:
        json.dump(cache, f, indent=2)
    print("Cache saved")

def get_file_hash(filepath):
    with open(filepath, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

def get_markdown_files():
    print(f"Scanning for markdown files in: {BASE_PATH}")
    files = []
    for filepath in BASE_PATH.rglob('*.md'):
        rel_path = str(filepath.relative_to(REPO_ROOT))
        files.append(rel_path)
    print(f"Found {len(files)} markdown files")
    return sorted(files)

def get_summary(content, filename):
    print(f"Generating summary for: {filename}")
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Summarize the following text in exactly two lines."},
                {"role": "user", "content": content}
            ]
        )
        summary = response.choices[0].message.content
        print(f"Summary generated: {summary[:50]}...")
        return summary
    except Exception as e:
        print(f"Error generating summary for {filename}: {str(e)}")
        return "Error generating summary"

def extract_huggingface_url(content, filename):
    print(f"Looking for HuggingFace URL in: {filename}")
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
            print(f"Found HuggingFace URL: {url}")
            return url
    print("No HuggingFace URL found")
    return None

def clean_title(filename):
    title = os.path.splitext(os.path.basename(filename))[0]
    cleaned = title.replace('-', ' ').title()
    print(f"Cleaned title: {filename} -> {cleaned}")
    return cleaned

def generate_table(files):
    print("\nGenerating table...")
    table = "| Model | Description | Repository | HuggingFace |\n"
    table += "|--------|-------------|------------|-------------|\n"
    
    cache = load_cache()
    total_files = len(files)
    processed_count = 0
    cached_count = 0
    
    for index, rel_file in enumerate(files, 1):
        print(f"\nProcessing file {index}/{total_files}: {rel_file}")
        abs_file = REPO_ROOT / rel_file
        
        try:
            file_hash = get_file_hash(abs_file)
            
            # Check if file is in cache and unchanged
            if rel_file in cache and cache[rel_file]['hash'] == file_hash:
                print(f"Using cached data for {rel_file}")
                cached_data = cache[rel_file]
                table += f"| {cached_data['title']} | {cached_data['description']} | {cached_data['repo_link']} | {cached_data['hf_link']} |\n"
                cached_count += 1
                continue
                
            with open(abs_file, 'r', encoding='utf-8') as f:
                content = f.read()
                print(f"Read {len(content)} characters from file")
            
            title = clean_title(rel_file)
            description = get_summary(content, rel_file)
            repo_link = f"[GitHub]({rel_file})"
            hf_url = extract_huggingface_url(content, rel_file)
            hf_link = f"[HuggingFace]({hf_url})" if hf_url else "N/A"
            
            description = description.replace('\n', '<br>')
            
            # Update cache
            cache[rel_file] = {
                'hash': file_hash,
                'title': title,
                'description': description,
                'repo_link': repo_link,
                'hf_link': hf_link
            }
            
            table += f"| {title} | {description} | {repo_link} | {hf_link} |\n"
            processed_count += 1
            
            # Add a small delay to avoid rate limiting
            time.sleep(0.5)
            
        except Exception as e:
            print(f"Error processing file {rel_file}: {str(e)}")
    
    save_cache(cache)
    print(f"\nTable generation completed:")
    print(f"- Files processed: {processed_count}")
    print(f"- Files from cache: {cached_count}")
    print(f"- Total files: {total_files}")
    return table

def update_readme():
    try:
        print("\n=== Starting README Update Process ===")
        print(f"Repository root: {REPO_ROOT}")
        print(f"Looking for README at: {README_PATH}")
        
        with open(README_PATH, 'r', encoding='utf-8') as f:
            readme = f.read()
            print(f"Read {len(readme)} characters from README.md")
        
        files = get_markdown_files()
        print(f"\nGenerating table for {len(files)} files...")
        new_table = generate_table(files)
        
        if START_MARKER in readme and END_MARKER in readme:
            print("Found existing markers in README.md, updating content...")
            pattern = f"{START_MARKER}.*?{END_MARKER}"
            new_content = f"{START_MARKER}\n{new_table}\n{END_MARKER}"
            readme = re.sub(pattern, new_content, readme, flags=re.DOTALL)
        else:
            print("No existing markers found, appending new content...")
            readme += f"\n\n{START_MARKER}\n{new_table}\n{END_MARKER}"
        
        print("Writing updated content to README.md...")
        with open(README_PATH, 'w', encoding='utf-8') as f:
            f.write(readme)
            
        print("\n=== README.md updated successfully! ===")
        
    except Exception as e:
        print(f"\nERROR: Failed to update README: {str(e)}")
        raise

if __name__ == "__main__":
    update_readme()    