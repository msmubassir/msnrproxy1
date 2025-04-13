from flask import Flask, request, make_response
import requests
from urllib.parse import urljoin, urlparse, quote, unquote, urlencode, parse_qs
import re
import json

app = Flask(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

def get_base_url(referer):
    if '/proxy-frame?url=' in referer:
        base_url = unquote(referer.split('proxy-frame?url=')[1].split('&')[0])
        parsed = urlparse(base_url)
        return f"{parsed.scheme}://{parsed.netloc}"
    return None

def process_content(content, base_url):
    # Fix relative URLs in content
    content = re.sub(r'(href|src|action)=["\'](?!https?://|/|data:|javascript:)(.*?)["\']', 
                     lambda m: f'{m.group(1)}="{urljoin(base_url, m.group(2))}"', 
                     content, flags=re.IGNORECASE)

    # Fix relative URLs starting with /
    content = re.sub(r'(href|src|action)=["\']/(.*?)["\']', 
                     lambda m: f'{m.group(1)}="{urljoin(base_url, "/" + m.group(2))}"', 
                     content, flags=re.IGNORECASE)

    return content

@app.route('/')
def home():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>MSNR Proxy Site</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
            .container { max-width: 1000px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { color: #333; text-align: center; }
            #url-form { display: flex; margin: 20px 0; }
            #url-input { flex: 1; padding: 12px; font-size: 16px; border: 1px solid #ddd; border-radius: 4px 0 0 4px; }
            #submit-btn { padding: 12px 20px; font-size: 16px; background: #4285f4; color: white; border: none; border-radius: 0 4px 4px 0; cursor: pointer; }
            .nav-buttons { display: flex; gap: 10px; margin-bottom: 10px; }
            .nav-btn { padding: 10px 15px; background: #f1f1f1; border: 1px solid #ddd; border-radius: 4px; cursor: pointer; }
            .nav-btn:hover { background: #e1e1e1; }
            iframe { width: 100%; height: 75vh; border: none; margin-top: 10px; border-radius: 4px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>MSNR Proxy Site</h1>
            <div class="nav-buttons">
                <button class="nav-btn" onclick="goBack()">← Back</button>
                <button class="nav-btn" onclick="goForward()">→ Forward</button>
                <button class="nav-btn" onclick="refreshPage()">↻ Refresh</button>
            </div>
            <form id="url-form" onsubmit="loadSite(event)">
                <input id="url-input" type="text" placeholder="Enter website URL (e.g. https://example.com)" required>
                <button id="submit-btn" type="submit">Browse</button>
            </form>
            <iframe id="proxy-frame" src="about:blank"></iframe>
            <script>
                function loadSite(e) {
                    e.preventDefault();
                    const url = document.getElementById('url-input').value;
                    const frame = document.getElementById('proxy-frame');
                    frame.src = '/proxy-frame?url=' + encodeURIComponent(url);
                }

                function goBack() {
                    const frame = document.getElementById('proxy-frame');
                    try {
                        frame.contentWindow.history.back();
                    } catch (e) {
                        // Cross-origin error, fallback to reloading the iframe
                        const currentUrl = frame.src;
                        if (currentUrl && currentUrl !== 'about:blank') {
                            frame.src = currentUrl;
                        }
                    }
                }

                function goForward() {
                    const frame = document.getElementById('proxy-frame');
                    try {
                        frame.contentWindow.history.forward();
                    } catch (e) {
                        // Cross-origin error, fallback to reloading the iframe
                        const currentUrl = frame.src;
                        if (currentUrl && currentUrl !== 'about:blank') {
                            frame.src = currentUrl;
                        }
                    }
                }

                function refreshPage() {
                    const frame = document.getElementById('proxy-frame');
                    const currentUrl = frame.src;
                    if (currentUrl && currentUrl !== 'about:blank') {
                        frame.src = currentUrl;
                    }
                }

                window.onload = function() {
                    document.getElementById('url-input').value = 'https://www.wikipedia.org';
                    document.getElementById('submit-btn').click();
                };
            </script>
        </div>
    </body>
    </html>
    '''

@app.route('/proxy-frame')
def proxy_frame():
    url = request.args.get('url', '')
    if not url:
        return "No URL provided", 400

    if not url.startswith(('http://', 'https://')):
        url = 'http://' + url

    try:
        headers = {
            'User-Agent': USER_AGENT,
            'Accept': request.headers.get('Accept', '*/*'),
            'Accept-Language': request.headers.get('Accept-Language', 'en-US,en;q=0.9'),
            'Referer': url
        }

        cookies = {}
        if request.cookies:
            cookies = request.cookies.to_dict()

        # Include query parameters from original URL
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)

        response = requests.get(url, headers=headers, cookies=cookies, params=query_params, timeout=10)

        content = response.text
        if 'text/html' in response.headers.get('Content-Type', ''):
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            content = process_content(content, base_url)

        proxy_response = make_response(content)
        proxy_response.headers['Content-Type'] = response.headers.get('Content-Type', 'text/html')
        proxy_response.status_code = response.status_code

        proxy_response.headers['Access-Control-Allow-Origin'] = '*'
        proxy_response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        proxy_response.headers['Access-Control-Allow-Headers'] = 'Content-Type'

        return proxy_response

    except requests.exceptions.RequestException as e:
        return f'''
        <!DOCTYPE html>
        <html>
        <head><title>Proxy Error</title></head>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>Error accessing website</h2>
            <p>{str(e)}</p>
            <a href="/">Try another website</a>
        </body>
        </html>
        ''', 500

@app.route('/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
def proxy_all(subpath):
    referer = request.headers.get('Referer', '')
    base_url = get_base_url(referer)

    if not base_url:
        return "Invalid referer", 400

    # Construct full URL with query parameters
    full_url = urljoin(base_url, subpath)
    if request.query_string:
        full_url += '?' + request.query_string.decode()

    try:
        headers = {
            'User-Agent': USER_AGENT,
            'Accept': request.headers.get('Accept', '*/*'),
            'Accept-Language': request.headers.get('Accept-Language', 'en-US,en;q=0.9'),
            'Referer': referer
        }

        cookies = {}
        if request.cookies:
            cookies = request.cookies.to_dict()

        # Handle different HTTP methods with parameters
        if request.method == 'GET':
            response = requests.get(full_url, headers=headers, cookies=cookies, timeout=10)
        elif request.method == 'POST':
            response = requests.post(full_url, headers=headers, cookies=cookies, data=request.form, timeout=10)
        elif request.method == 'PUT':
            response = requests.put(full_url, headers=headers, cookies=cookies, data=request.form, timeout=10)
        elif request.method == 'DELETE':
            response = requests.delete(full_url, headers=headers, cookies=cookies, timeout=10)
        else:
            response = requests.options(full_url, headers=headers, cookies=cookies, timeout=10)

        content = response.text
        if 'text/html' in response.headers.get('Content-Type', ''):
            content = process_content(content, base_url)

        proxy_response = make_response(content)
        proxy_response.headers['Content-Type'] = response.headers.get('Content-Type', 'text/html')
        proxy_response.status_code = response.status_code

        proxy_response.headers['Access-Control-Allow-Origin'] = '*'
        proxy_response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        proxy_response.headers['Access-Control-Allow-Headers'] = 'Content-Type'

        return proxy_response

    except requests.exceptions.RequestException as e:
        return f'''
        <!DOCTYPE html>
        <html>
        <head><title>Proxy Error</title></head>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>Error accessing resource</h2>
            <p>{str(e)}</p>
            <a href="/">Back to homepage</a>
        </body>
        </html>
        ''', 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
