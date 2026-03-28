from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.responses import JSONResponse, Response
from fastapi.templating import Jinja2Templates
import asyncio
import csv
import io
import os
import json as _json
from datetime import datetime, timedelta

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# State for auto-run
_auto_run_enabled = False
_auto_run_task = None
_last_results = None
_last_run_at = None
_auto_interval_minutes = 10
_next_run_at = None

# persistence paths
DATA_DIR = os.path.join(os.getcwd(), 'data')
os.makedirs(DATA_DIR, exist_ok=True)
LAST_JSON = os.path.join(DATA_DIR, 'scraper_last_results.json')
LAST_CSV = os.path.join(DATA_DIR, 'scraper_last_results.csv')


def _results_to_csv(results):
    if not results:
        return ""
    output = io.StringIO()
    fieldnames = list(results[0].keys())
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for r in results:
        writer.writerow(r)
    return output.getvalue()


def _persist_results(results):
    try:
        # write JSON
        with open(LAST_JSON, 'w', encoding='utf-8') as f:
            _json.dump(results, f, ensure_ascii=False, indent=2)
        # write CSV
        csv_text = _results_to_csv(results)
        with open(LAST_CSV, 'w', encoding='utf-8') as f:
            f.write(csv_text)
    except Exception:
        pass


def _log_error(msg: str):
    try:
        with open(os.path.join(DATA_DIR, 'auto_run.log'), 'a', encoding='utf-8') as f:
            f.write(f"{datetime.utcnow().isoformat()} - {msg}\n")
    except Exception:
        pass


def _load_persisted_results():
    try:
        if os.path.exists(LAST_JSON):
            with open(LAST_JSON, 'r', encoding='utf-8') as f:
                return _json.load(f)
    except Exception:
        return None
    return None

# concurrency limiter: only 1 active run at a time
_run_semaphore = asyncio.Semaphore(1)
_min_seconds_between_runs = 30  # throttle repeated manual runs
_last_manual_run_ts = None


async def _auto_runner(interval_minutes: int = 10):
    global _auto_run_enabled, _last_results, _last_run_at
    # helper to run the blocking scraper code in a thread
    def _run_sync_scraper():
        try:
            from youtube_stock_vid_Scraping_halal_check import get_youtube_videos, extract_stock_symbols, check_halal_status, get_trend_from_yahoo
            results = []
            videos = get_youtube_videos()
            for v in videos:
                symbols = extract_stock_symbols(v['title'])
                for s in symbols:
                    halal = check_halal_status(s)
                    trend = get_trend_from_yahoo(s)
                    results.append({
                        'Video Title': v['title'],
                        'Upload Time': v['upload_time'],
                        'Stock Symbol': s,
                        'Company Name': halal.get('company_name','Unknown'),
                        'Halal Status': halal.get('halal_status','Unknown'),
                        'Trend': trend.get('trend','Unknown'),
                        'Current Price': trend.get('current_price','N/A'),
                        'Change %': trend.get('change_percent','N/A')
                    })
            return results
        except Exception:
            return []

    while _auto_run_enabled:
        # schedule next run timestamp immediately
        global _next_run_at
        _next_run_at = (datetime.utcnow() + timedelta(minutes=interval_minutes)).isoformat()

        # Use semaphore to avoid overlapping runs
        async with _run_semaphore:
            try:
                # run blocking scraper in a thread so we don't block the event loop
                results = await asyncio.to_thread(_run_sync_scraper)
                _last_results = results
                _last_run_at = datetime.utcnow().isoformat()
                _persist_results(results)
            except Exception:
                import traceback
                _log_error('auto_runner exception: ' + traceback.format_exc())

        # sleep until next iteration
        await asyncio.sleep(interval_minutes * 60)


async def _run_once_and_persist():
    """Run one scrape cycle under semaphore and persist results. Safe to schedule as a background task."""
    global _last_results, _last_run_at
    async with _run_semaphore:
        try:
            # Use the same sync scraper helper inside _auto_runner scope
            def _run_sync_scraper_local():
                try:
                    from youtube_stock_vid_Scraping_halal_check import get_youtube_videos, extract_stock_symbols, check_halal_status, get_trend_from_yahoo
                    results = []
                    videos = get_youtube_videos()
                    for v in videos:
                        symbols = extract_stock_symbols(v['title'])
                        for s in symbols:
                            halal = check_halal_status(s)
                            trend = get_trend_from_yahoo(s)
                            results.append({
                                'Video Title': v['title'],
                                'Upload Time': v['upload_time'],
                                'Stock Symbol': s,
                                'Company Name': halal.get('company_name','Unknown'),
                                'Halal Status': halal.get('halal_status','Unknown'),
                                'Trend': trend.get('trend','Unknown'),
                                'Current Price': trend.get('current_price','N/A'),
                                'Change %': trend.get('change_percent','N/A')
                            })
                    return results
                except Exception:
                    return []

            results = await asyncio.to_thread(_run_sync_scraper_local)
            _last_results = results
            _last_run_at = datetime.utcnow().isoformat()
            _persist_results(results)
        except Exception:
            import traceback
            _log_error('run_once exception: ' + traceback.format_exc())


@router.get('/tools/scraper')
async def tools_scraper_page(request: Request):
    return templates.TemplateResponse('tools_scraper.html', {'request': request})


@router.post('/api/tools/scraper/run')
async def run_scraper():
    """Run the scraper on demand and return JSON results and CSV text"""
    global _last_results, _last_run_at
    # Acquire semaphore to limit concurrent runs
    global _last_manual_run_ts
    now_ts = datetime.utcnow().timestamp()
    if _last_manual_run_ts and (now_ts - _last_manual_run_ts) < _min_seconds_between_runs:
        return JSONResponse({'error': f'Please wait {_min_seconds_between_runs} seconds between runs.'}, status_code=429)

    async with _run_semaphore:
        try:
            _last_manual_run_ts = now_ts
            from youtube_stock_vid_Scraping_halal_check import get_youtube_videos, extract_stock_symbols, check_halal_status, get_trend_from_yahoo
            results = []
            videos = get_youtube_videos()
            for v in videos:
                symbols = extract_stock_symbols(v['title'])
                for s in symbols:
                    halal = check_halal_status(s)
                    trend = get_trend_from_yahoo(s)
                    results.append({
                        'Video Title': v['title'],
                        'Upload Time': v['upload_time'],
                        'Stock Symbol': s,
                        'Company Name': halal.get('company_name','Unknown'),
                        'Halal Status': halal.get('halal_status','Unknown'),
                        'Trend': trend.get('trend','Unknown'),
                        'Current Price': trend.get('current_price','N/A'),
                        'Change %': trend.get('change_percent','N/A')
                    })

            _last_results = results
            _last_run_at = datetime.utcnow().isoformat()
            # persist
            _persist_results(results)
            csv_text = _results_to_csv(results)
            return JSONResponse({'results': results, 'csv': csv_text, 'last_run_at': _last_run_at})
        except Exception as e:
            return JSONResponse({'error': str(e)}, status_code=500)


@router.get('/api/tools/scraper/status')
async def scraper_status():
    # load persisted if in-memory empty
    global _last_results
    if _last_results is None:
        _last_results = _load_persisted_results()
    return JSONResponse({'auto_run_enabled': _auto_run_enabled, 'last_run_at': _last_run_at, 'last_count': len(_last_results) if _last_results else 0, 'interval_minutes': _auto_interval_minutes, 'next_run_at': _next_run_at})


@router.post('/api/tools/scraper/auto')
async def set_auto_run(enable: bool = True, interval_minutes: int = None, background_tasks: BackgroundTasks = None):
    """Enable or disable automated scraping"""
    global _auto_run_enabled, _auto_run_task
    global _auto_interval_minutes, _next_run_at
    _auto_run_enabled = bool(enable)
    if interval_minutes is not None:
        try:
            _auto_interval_minutes = int(interval_minutes)
        except Exception:
            pass

    if _auto_run_enabled:
        # start background task
        if _auto_run_task is None or _auto_run_task.done():
            loop = asyncio.get_event_loop()
            _next_run_at = (datetime.utcnow() + timedelta(minutes=_auto_interval_minutes)).isoformat()
            _auto_run_task = loop.create_task(_auto_runner(_auto_interval_minutes))
            # trigger an immediate run in background so UI gets results quickly
            loop.create_task(_run_once_and_persist())
    else:
        # task will exit on next loop
        _auto_run_task = None
        _next_run_at = None
    return JSONResponse({'auto_run_enabled': _auto_run_enabled, 'interval_minutes': _auto_interval_minutes, 'next_run_at': _next_run_at})


@router.get('/api/tools/scraper/last')
async def get_last_results():
    global _last_results
    if _last_results is None:
        _last_results = _load_persisted_results() or []
    return JSONResponse({'results': _last_results, 'last_run_at': _last_run_at})


@router.get('/api/tools/scraper/csv')
async def download_csv():
    """Stream the persisted CSV file directly."""
    if not os.path.exists(LAST_CSV):
        return JSONResponse({'error': 'No CSV available'}, status_code=404)
    # return as streaming response by reading the file
    from fastapi.responses import FileResponse
    return FileResponse(LAST_CSV, media_type='text/csv', filename='scraper_results.csv')


@router.post('/api/tools/ticker-lookup')
async def ticker_lookup(youtube_url: str = None, ticker: str = None):
    """
    Manual ticker lookup from YouTube video or multiple tickers.
    Supports comma-separated tickers. If ticker is provided, use it; 
    otherwise try to extract from video title.
    Returns halal status, trend, and other stock info for each ticker.
    """
    try:
        from youtube_stock_vid_Scraping_halal_check import (
            extract_stock_symbols, check_halal_status, get_trend_from_yahoo
        )
        import re
        
        # Parse multiple tickers if provided
        tickers_to_lookup = []
        
        if ticker and ticker.strip():
            # User provided ticker(s) - split by comma and clean
            tickers_to_lookup = [t.strip().upper() for t in ticker.split(',') if t.strip()]
        elif youtube_url:
            # Try to extract from URL or fetch video info
            try:
                video_title = youtube_url
                symbols = extract_stock_symbols(video_title)
                if symbols:
                    tickers_to_lookup = symbols
            except Exception as e:
                pass
        
        if not tickers_to_lookup:
            return JSONResponse(
                {'error': 'Please provide a ticker symbol or a YouTube URL with stock symbols in the title'},
                status_code=400
            )
        
        # Fetch stock information for each ticker
        results = []
        errors = []
        
        for resolved_ticker in tickers_to_lookup:
            try:
                halal_info = check_halal_status(resolved_ticker)
                trend_info = get_trend_from_yahoo(resolved_ticker)
                
                result = {
                    'ticker': resolved_ticker,
                    'company_name': halal_info.get('company_name', 'Unknown'),
                    'halal_status': halal_info.get('halal_status', 'Unknown'),
                    'trend': trend_info.get('trend', 'Unknown'),
                    'current_price': trend_info.get('current_price', 'N/A'),
                    'change_percent': trend_info.get('change_percent', 'N/A'),
                    'timestamp': datetime.utcnow().isoformat()
                }
                results.append(result)
            except Exception as stock_error:
                errors.append({
                    'ticker': resolved_ticker,
                    'error': str(stock_error)
                })
        
        if not results and errors:
            return JSONResponse(
                {'error': f'Failed to fetch data for all tickers: {"; ".join([e["error"] for e in errors])}'},
                status_code=500
            )
        
        return JSONResponse({
            'results': results,
            'errors': errors,
            'source': 'manual_entry' if (ticker and ticker.strip()) else 'extracted_from_url',
            'timestamp': datetime.utcnow().isoformat()
        })
            
    except Exception as e:
        return JSONResponse({'error': str(e)}, status_code=500)


@router.get('/api/tools/manual-ticker/csv')
async def export_manual_ticker_csv(tickers: str = None):
    """Export manual ticker lookup results to CSV"""
    if not tickers:
        return JSONResponse({'error': 'No tickers provided'}, status_code=400)
    
    try:
        from youtube_stock_vid_Scraping_halal_check import (
            check_halal_status, get_trend_from_yahoo
        )
        
        ticker_list = [t.strip().upper() for t in tickers.split(',') if t.strip()]
        results = []
        
        for ticker in ticker_list:
            try:
                halal_info = check_halal_status(ticker)
                trend_info = get_trend_from_yahoo(ticker)
                
                results.append({
                    'Ticker': ticker,
                    'Company Name': halal_info.get('company_name', 'Unknown'),
                    'Halal Status': halal_info.get('halal_status', 'Unknown'),
                    'Trend': trend_info.get('trend', 'Unknown'),
                    'Current Price': trend_info.get('current_price', 'N/A'),
                    'Change %': trend_info.get('change_percent', 'N/A')
                })
            except Exception:
                results.append({
                    'Ticker': ticker,
                    'Company Name': 'Error',
                    'Halal Status': 'Error',
                    'Trend': 'Error',
                    'Current Price': 'N/A',
                    'Change %': 'N/A'
                })
        
        # Generate CSV
        csv_text = _results_to_csv(results)
        
        return Response(
            content=csv_text,
            media_type='text/csv',
            headers={'Content-Disposition': 'attachment; filename="manual_ticker_results.csv"'}
        )
    except Exception as e:
        return JSONResponse({'error': str(e)}, status_code=500)
