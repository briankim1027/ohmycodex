import json
import re
from datetime import datetime

def find_posts(data, results):
    if isinstance(data, dict):
        if 'code' in data and 'user' in data and ('caption' in data or 'text_post_app_info' in data):
            results.append(data)
        elif 'thread_items' in data:
            for item in data['thread_items']:
                if 'post' in item:
                    results.append(item['post'])
        else:
            for k, v in data.items():
                find_posts(v, results)
    elif isinstance(data, list):
        for item in data:
            find_posts(item, results)

def extract_post_data(post):
    code = post.get('code')
    user = post.get('user', {})
    username = user.get('username')
    
    # Extract text from caption or text_fragments
    text = ""
    caption = post.get('caption')
    if caption and isinstance(caption, dict) and 'text' in caption:
        text = caption['text']
    else:
        text_info = post.get('text_post_app_info', {})
        fragments = text_info.get('text_fragments', {}).get('fragments', [])
        for f in fragments:
            if 'plaintext' in f and f['plaintext']:
                text += f['plaintext']
                
    # Extract timestamp
    taken_at = post.get('taken_at')
    date_str = ""
    if taken_at:
        try:
            date_str = datetime.fromtimestamp(taken_at).strftime('%Y-%m-%d %H:%M:%S')
        except:
            pass
            
    return {
        'id': code,
        'username': username,
        'url': f"https://www.threads.net/@{username}/post/{code}" if username and code else "",
        'text': text.strip(),
        'date': date_str
    }

def main():
    try:
        with open('threads_debug_json.txt', 'r', encoding='utf-8') as f:
            content = f.read()
            
        posts = []
        for line in content.split('\n'):
            line = line.strip()
            if not line: continue
            
            if line.startswith('{') and line.endswith('}'):
                try:
                    data = json.loads(line)
                    find_posts(data, posts)
                except json.JSONDecodeError:
                    pass
            
            matches = re.findall(r'<script.*?>(\{.*?\})</script>', line)
            for m in matches:
                try:
                    data = json.loads(m)
                    find_posts(data, posts)
                except json.JSONDecodeError:
                    pass
                    
        print(f"Found {len(posts)} potential post objects.")
        
        # Deduplicate posts by code
        unique_posts = {}
        for p in posts:
            code = p.get('code')
            if code and code not in unique_posts:
                unique_posts[code] = p
                
        print(f"Found {len(unique_posts)} UNIQUE post objects.")
        
        for code, p in unique_posts.items():
            extracted = extract_post_data(p)
            print("-" * 40)
            print(f"ID: {extracted['id']}")
            print(f"User: {extracted['username']}")
            print(f"Date: {extracted['date']}")
            print(f"URL: {extracted['url']}")
            print(f"Text Snippet: {extracted['text'][:100].replace(chr(10), ' ')}...")
            

    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()
