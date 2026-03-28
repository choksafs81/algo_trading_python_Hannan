"""Polygon aggregates quick test using the installed polygon package.

This script uses `from polygon.rest import RESTClient` (the installed package
exports RESTClient from polygon.rest.__init__). It reads the API key from
POLYGON_API_KEY (env) or a top-level .env file. It queries a small date range
and prints a compact summary.
"""

import os
import json
from datetime import datetime


def read_key():
    key = os.environ.get("POLYGON_API_KEY") or os.environ.get("POLYGON_APIKEY")
    if key:
        return key
    # try .env in repo root
    try:
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if line.startswith('POLYGON_API_KEY') or line.startswith('POLYGON_APIKEY'):
                    parts = line.split('=', 1)
                    if len(parts) == 2:
                        return parts[1].strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return None


def main():
    api_key = read_key()
    if not api_key:
        print('POLYGON_API_KEY not found in environment or .env')
        return

    ticker = os.environ.get('TICKER', 'AAPL')

    try:
        # correct import path for the installed package
        from polygon.rest import RESTClient
    except Exception as e:
        print('Failed to import official polygon RESTClient:', type(e).__name__, e)
        return

    client = RESTClient(api_key)

    # Query a small date range to keep responses small
    start = '2025-10-10'
    end = '2025-10-13'

    try:
        it = client.list_aggs(ticker, 1, 'minute', start, end, limit=5000)
        sample = []
        for i, a in enumerate(it):
            if i < 5:
                try:
                    sample.append(a._asdict())
                except Exception:
                    sample.append(str(a))
            else:
                break
        print(json.dumps({'ticker': ticker, 'sample_count': len(sample), 'sample': sample}, default=str, indent=2))
    except Exception as e:
        # Polygon often returns provider JSON errors – surface them
        print('Query failed:', type(e).__name__, e)


if __name__ == '__main__':
    main()
