import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import re
import time
import yfinance as yf
import json

def get_youtube_videos():
    """Extract today's uploaded videos from YouTube channel using web scraping"""
    # url = "https://www.youtube.com/@ITNEWSBIKUL/videos"
    url = "https://www.youtube.com/@StockMarketPalantir/videos"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        text = response.text

        # YouTube embeds initial state in a JS variable ytInitialData. Extract it.
        if 'ytInitialData' not in text:
            # fallback to simple html parsing (older approach)
            soup = BeautifulSoup(response.content, 'html.parser')
            video_containers = soup.find_all('div', {'id': 'dismissible'})
            videos_data = []
            for container in video_containers:
                try:
                    title_element = container.find('a', {'id': 'video-title-link'})
                    title = title_element.text.strip() if title_element else "N/A"
                    meta_section = container.find('div', {'id': 'metadata-line'})
                    if meta_section:
                        time_elements = meta_section.find_all('span')
                        upload_time = time_elements[1].text if len(time_elements) > 1 else "N/A"
                        if any(x in upload_time.lower() for x in ['hour', 'minutes', 'minute', 'just', 'now']):
                            videos_data.append({
                                'title': title,
                                'upload_time': upload_time,
                                'full_timestamp': get_full_timestamp(upload_time)
                            })
                except Exception:
                    continue
            return videos_data

        # locate JSON start after the ytInitialData token
        idx = text.find('ytInitialData')
        # find first '{' after idx
        start = text.find('{', idx)
        if start == -1:
            print('Could not locate ytInitialData JSON start')
            return []

        # extract balanced JSON braces
        i = start
        depth = 0
        end = None
        while i < len(text):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
            i += 1

        if end is None:
            print('Could not extract full ytInitialData JSON')
            return []

        raw = text[start:end]
        try:
            data = json.loads(raw)
        except Exception as e:
            # sometimes the JSON is not strict; try to clean common JS artifacts
            try:
                cleaned = re.sub(r"\n", " ", raw)
                data = json.loads(cleaned)
            except Exception as e2:
                print('Failed to parse ytInitialData JSON:', e2)
                return []

        # recursively collect all videoRenderer objects
        def collect_video_renderers(obj, out):
            if isinstance(obj, dict):
                if 'videoRenderer' in obj:
                    out.append(obj['videoRenderer'])
                for v in obj.values():
                    collect_video_renderers(v, out)
            elif isinstance(obj, list):
                for item in obj:
                    collect_video_renderers(item, out)

        renderers = []
        collect_video_renderers(data, renderers)

        videos_data = []
        for vr in renderers:
            try:
                title = ''
                if 'title' in vr:
                    if isinstance(vr['title'], dict) and 'runs' in vr['title']:
                        title = ''.join([r.get('text', '') for r in vr['title'].get('runs', [])]).strip()
                    else:
                        title = vr['title']

                published = ''
                if 'publishedTimeText' in vr:
                    published = vr['publishedTimeText'].get('simpleText', '') if isinstance(vr['publishedTimeText'], dict) else str(vr['publishedTimeText'])

                # Normalize published text
                pub_l = published.lower()
                # consider recent if mentions hours/minutes/just now/streamed or contains 'ago' but not 'day'
                is_recent = False
                if any(k in pub_l for k in ('hour', 'hours', 'minute', 'minutes', 'just', 'now', 'streamed', 'premiered')):
                    is_recent = True
                if 'day' in pub_l:
                    # treat '0 day' as recent (rare) otherwise skip
                    m = re.search(r"(\d+)\s*day", pub_l)
                    if m and int(m.group(1)) == 1:
                        is_recent = True

                if is_recent:
                    videos_data.append({
                        'title': title or 'N/A',
                        'upload_time': published or 'N/A',
                        'full_timestamp': get_full_timestamp(published)
                    })
            except Exception:
                continue

        return videos_data

    except Exception as e:
        print(f"Error fetching YouTube data: {e}")
        return []

def get_full_timestamp(relative_time):
    """Convert relative time (e.g., '2 hours ago') to full timestamp"""
    try:
        now = datetime.now()
        if 'hour' in relative_time:
            hours = int(re.search(r'(\d+)\s*hour', relative_time).group(1))
            return (now - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        elif 'minute' in relative_time:
            minutes = int(re.search(r'(\d+)\s*minute', relative_time).group(1))
            return (now - timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
        elif 'day' in relative_time:
            days = int(re.search(r'(\d+)\s*day', relative_time).group(1))
            return (now - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        else:
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def extract_stock_symbols(title):
    """Extract potential stock symbols from video title with improved logic"""
    # Common stock patterns (uppercase words 1-5 characters, potentially with . or ^)
    patterns = [
        r'\b[A-Z]{1,5}\b',  # Basic uppercase tickers
        r'\$[A-Z]{1,5}',    # $TICKER format
        r'\b[A-Z]+\.[A-Z]+\b',  # FOREX pairs or special symbols
    ]
    
    symbols = []
    for pattern in patterns:
        matches = re.findall(pattern, title)
        for match in matches:
            # Clean the symbol
            symbol = match.replace('$', '').strip()
            # Filter out common words that aren't stock symbols
            common_words = ['THE', 'AND', 'FOR', 'YOU', 'ARE', 'NEW', 'LIVE', 'TODAY', 'STOCK', 'STOCKS', 'MARKET', 'TECH', 'INC']
            if (symbol not in common_words and 
                len(symbol) >= 1 and 
                len(symbol) <= 5 and 
                symbol.isalpha()):
                symbols.append(symbol)
    
    return list(set(symbols))  # Remove duplicates

def check_halal_status(symbol):
    """Check if stock is Halal using MuslimXchange website"""
    url = f"https://muslimxchange.com/ticker/{symbol.upper()}/"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Look for Halal status indicators in the page text lines
        page_text = soup.get_text()
        page_text_upper = page_text.upper()

        halal_status = 'Unknown'
        company_name = 'Unknown'

        # First, look for explicit lines that start with YES or NO (e.g.,
        # "NO, TLRY (TILRAY BRANDS INC) STOCK IS SHARIAH NOT COMPLIANT")
        for raw_line in page_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            m = re.match(r'^(YES|NO)\s*[,:-]?\s*(.+)$', line, flags=re.IGNORECASE)
            if m:
                val = m.group(1).upper()
                rest = m.group(2).strip()
                halal_status = 'Yes' if val == 'YES' else 'No'
                # Try to extract company name inside parentheses if present
                par = re.search(r'\(([^)]+)\)', rest)
                if par:
                    company_name = par.group(1).strip()
                else:
                    # fallback: take remaining words after comma (e.g., "NO, TLRY - TILRAY BRANDS INC ...")
                    # try to pull words in all-caps that look like a company name
                    cand = re.search(r'[A-Z][A-Z\s&\.]{2,}', rest)
                    if cand:
                        company_name = cand.group(0).strip()
                    else:
                        # if rest begins with a symbol then the company name may follow in uppercase words
                        parts = rest.split()
                        if len(parts) > 1 and parts[0].isalpha() and parts[0].isupper():
                            # join following words until punctuation
                            company_name = ' '.join([p for p in parts[1:6] if re.match(r"[A-Za-z&\.]+", p)])
                break

        # If not found by the YES/NO pattern, fall back to previous heuristics
        if halal_status == 'Unknown':
            if 'HALAL: YES' in page_text_upper or 'IS HALAL: YES' in page_text_upper or 'HALAL✅' in page_text_upper:
                halal_status = 'Yes'
            elif 'HALAL: NO' in page_text_upper or 'IS HALAL: NO' in page_text_upper or 'HARAM' in page_text_upper:
                halal_status = 'No'
        
        # If company_name still unknown, try to extract from the <title>
        if company_name == 'Unknown':
            title_tag = soup.find('title')
            if title_tag:
                title_text = title_tag.text
                # Extract company name from title (assuming format "Symbol - Company Name")
                name_match = re.search(r'-\s*(.+?)\s*\|', title_text)
                if name_match:
                    company_name = name_match.group(1).strip()
                else:
                    # Alternative pattern matching
                    name_match = re.search(r'([A-Z][A-Za-z\s\.&]+(?:Inc|Corp|Company|Ltd)\.?)', title_text)
                    if name_match:
                        company_name = name_match.group(1).strip()
        
        return {
            'halal_status': halal_status,
            'company_name': company_name
        }
        
    except Exception as e:
        print(f"Error checking Halal status for {symbol}: {e}")
        return {'halal_status': 'Error', 'company_name': 'Unknown'}

def get_trend_from_yahoo(symbol):
    """Get stock trend analysis using yfinance"""
    try:
        stock = yf.Ticker(symbol)
        
        # Get historical data for trend analysis
        hist = stock.history(period="1mo")
        
        if hist.empty:
            return {'trend': 'No Data', 'current_price': 'N/A', 'change_percent': 'N/A'}
        
        # Calculate simple trend indicators
        current_price = hist['Close'].iloc[-1]
        avg_20d = hist['Close'].tail(20).mean()
        avg_5d = hist['Close'].tail(5).mean()
        
        # Determine trend
        if avg_5d > avg_20d and current_price > avg_5d:
            trend = "Uptrend"
        elif avg_5d < avg_20d and current_price < avg_5d:
            trend = "Downtrend"
        else:
            trend = "Sideways"
        
        # Get additional info
        info = stock.info
        current_price = info.get('currentPrice', info.get('regularMarketPrice', 'N/A'))
        change_percent = info.get('regularMarketChangePercent', 'N/A')
        
        return {
            'trend': trend,
            'current_price': current_price,
            'change_percent': change_percent
        }
        
    except Exception as e:
        print(f"Error getting Yahoo Finance data for {symbol}: {e}")
        return {'trend': 'Error', 'current_price': 'N/A', 'change_percent': 'N/A'}

def main():
    # print("🔍 Starting analysis of ITNEWSBIKUL YouTube channel...")
    print("🔍 Starting analysis of StockMarketPalantir YouTube channel...")
    
    # Step 1: Get today's uploaded videos
    print("📹 Fetching today's uploaded videos...")
    videos_data = get_youtube_videos()
    
    if not videos_data:
        print("No recent videos found from today.")
        return
    
    print(f"Found {len(videos_data)} recent video(s)")
    
    # Step 2: Analyze each video and extract stock information
    analysis_results = []
    
    for video in videos_data:
        print(f"\n📺 Analyzing video: {video['title']}")
        
        # Extract stock symbols from title
        symbols = extract_stock_symbols(video['title'])
        
        if not symbols:
            print("   No stock symbols found in title")
            continue
            
        print(f"   Found symbols: {', '.join(symbols)}")
        
        # Analyze each stock symbol
        for symbol in symbols:
            print(f"   📊 Analyzing {symbol}...")
            
            # Check Halal status
            print(f"   🕌 Checking Halal status for {symbol}...")
            halal_info = check_halal_status(symbol)
            time.sleep(1)  # Be polite to the server
            
            # Get trend analysis
            print(f"   📈 Checking trend for {symbol}...")
            trend_info = get_trend_from_yahoo(symbol)
            
            # Compile results
            result = {
                'Video Title': video['title'][:100] + '...' if len(video['title']) > 100 else video['title'],
                'Upload Time': video['upload_time'],
                'Stock Symbol': symbol,
                'Company Name': halal_info['company_name'],
                'Halal Status': halal_info['halal_status'],
                'Trend': trend_info['trend'],
                'Current Price': f"${trend_info['current_price']}" if isinstance(trend_info['current_price'], (int, float)) else trend_info['current_price'],
                'Change %': f"{trend_info['change_percent']:.2f}%" if isinstance(trend_info['change_percent'], (int, float)) else trend_info['change_percent']
            }
            
            analysis_results.append(result)
            
            # Small delay between requests
            time.sleep(1)
    
    # Step 3: Display results in table format
    if analysis_results:
        print("\n" + "="*100)
        print("📊 FINAL ANALYSIS RESULTS")
        print("="*100)
        
        df = pd.DataFrame(analysis_results)
        
        # Format the table for better readability
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        pd.set_option('display.max_colwidth', 50)
        
        print(df.to_string(index=False))
        
        # Save to CSV for reference
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"stock_analysis_{timestamp}.csv"
        df.to_csv(filename, index=False)
        print(f"\n💾 Results saved to: {filename}")
        
    else:
        print("\n❌ No stock data could be extracted from the videos.")

if __name__ == "__main__":
    # Install required packages if not already installed
    try:
        import yfinance
    except ImportError:
        print("Please install required packages:")
        print("pip install requests beautifulsoup4 pandas yfinance")
    
    main()
