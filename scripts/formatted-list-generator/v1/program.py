import os
import re
from datetime import datetime
from pathlib import Path
from openai import OpenAI
import git

# Initialize OpenAI client
client = OpenAI()

# Path to assistant configurations
ASSISTANTS_PATH = Path('/home/daniel/Git/my-llm-assistants/finished/by-category')

def find_repo_root():
    try:
        repo = git.Repo(Path.cwd(), search_parent_directories=True)
        return Path(repo.working_dir)
    except git.InvalidGitRepositoryError:
        raise Exception("Not in a git repository")

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

def get_summary(content, filename):
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

    for filepath, file_content in files:
        try:
            title = clean_title(filepath)
            description = get_summary(file_content, filepath.name)
            hf_url = extract_huggingface_url(file_content)
            relative_path = filepath.relative_to(REPO_ROOT)
            
            entries.append({
                'title': title,
                'description': description,
                'repo_link': str(relative_path),
                'hf_link': hf_url
            })
            
        except Exception as e:
            print(f"Error processing {filepath}: {str(e)}")
            continue
    
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

def create_formatted_list():
    try:
        print("\n=== Starting Formatted List Generation ===")
        
        # Find repository root and set up paths
        global REPO_ROOT
        REPO_ROOT = find_repo_root()
        OUTPUT_DIR = REPO_ROOT / 'formatted-lists'
        
        # Create output directory if it doesn't exist
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        # Generate timestamp for filename
        timestamp = datetime.now().strftime('%d%m%y')
        output_file = OUTPUT_DIR / f"{timestamp}.md"
        
        files = get_markdown_files()
        print(f"\nGenerating list for {len(files)} files...")
        formatted_content = generate_formatted_list(files)
        
        print(f"Writing formatted list to {output_file}...")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(formatted_content)
            
        print(f"\n=== Formatted list generated successfully at {output_file}! ===")
        
    except Exception as e:
        print(f"\nERROR: Failed to generate formatted list: {str(e)}")
        raise

if __name__ == "__main__":
    create_formatted_list()