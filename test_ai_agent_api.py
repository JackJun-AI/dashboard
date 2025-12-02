#!/usr/bin/env python3
"""
Test script for AI Agent V1 Async Backtesting API

This script tests all the endpoints used by the dashboard interface.
"""

import json
import time
from datetime import datetime, timedelta

import requests

# Configuration
API_BASE_URL = "http://localhost:8010"
AUTH = ("admin", "admin")

def test_start_backtest():
    """Test starting a new backtest"""
    print("\n" + "="*80)
    print("TEST 1: Start Backtest")
    print("="*80)
    
    # Calculate date range (2 days, ending yesterday)
    end_date = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=2)
    
    payload = {
        "run_name": f"Test Run {datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "start_time": int(start_date.timestamp()),
        "end_time": int(end_date.timestamp()),
        "backtesting_resolution": "5m",
        "trade_cost": 0.0006,
        "config": {
            "controller_name": "ai_agent_v1",
            "controller_type": "directional_trading",
            "connector_name": "binance_perpetual",
            "trading_pair": "BTC-USDT",
            "total_amount_quote": 1000,
            "trading_pairs": ["BTC-USDT"],
            "max_concurrent_positions": 2,
            "single_position_size_pct": 0.4,
            "decision_interval": 300,
            "candles_connector": "binance_perpetual",
            "candles_trading_pair": "BTC-USDT",
            "candles_interval": "5m",
            "interval": "5m",
            "candles_max_records": 100,
            "openrouter_api_key": "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",
            "llm_model": "anthropic/claude-3.5-sonnet",
            "llm_temperature": 0.1,
            "llm_max_tokens": 4000,
            "leverage": 1,
            "position_mode": "ONEWAY",
            "triple_barrier_config": {
                "stop_loss": 0.02,
                "take_profit": 0.04,
                "time_limit": None,
                "trailing_stop": None
            }
        }
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/backtesting/start",
            json=payload,
            auth=AUTH,
            timeout=10
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Success!")
            print(json.dumps(result, indent=2))
            return result.get("run_id")
        else:
            print(f"❌ Failed: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def test_get_status(run_id):
    """Test getting backtest status"""
    print("\n" + "="*80)
    print("TEST 2: Get Status")
    print("="*80)
    
    try:
        response = requests.get(
            f"{API_BASE_URL}/backtesting/status/{run_id}",
            auth=AUTH,
            timeout=10
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Success!")
            print(json.dumps(result, indent=2))
            return result.get("status")
        else:
            print(f"❌ Failed: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def test_list_backtests():
    """Test listing all backtests"""
    print("\n" + "="*80)
    print("TEST 3: List Backtests")
    print("="*80)
    
    try:
        response = requests.get(
            f"{API_BASE_URL}/backtesting/list",
            params={"limit": 10, "status": "COMPLETED"},
            auth=AUTH,
            timeout=10
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Success!")
            print(f"Total runs: {result.get('total', 0)}")
            
            for i, run in enumerate(result.get("runs", [])[:3], 1):
                print(f"\n{i}. {run.get('run_name')}")
                print(f"   Status: {run.get('status')}")
                print(f"   Trades: {run.get('total_trades', 0)}")
                print(f"   Net PnL: {run.get('net_pnl_pct', 0)*100:.2f}%")
                
            return result.get("runs", [])
        else:
            print(f"❌ Failed: {response.text}")
            return []
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return []


def test_get_results(run_id):
    """Test getting detailed results"""
    print("\n" + "="*80)
    print("TEST 4: Get Results")
    print("="*80)
    
    try:
        response = requests.get(
            f"{API_BASE_URL}/backtesting/results/{run_id}",
            params={"include_logs": True, "log_limit": 10},
            auth=AUTH,
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Success!")
            
            run_info = result.get("run_info", {})
            trades = result.get("trades", [])
            logs = result.get("logs", [])
            
            print(f"\nRun Info:")
            print(f"  - Name: {run_info.get('run_name')}")
            print(f"  - Status: {run_info.get('status')}")
            print(f"  - Total Trades: {run_info.get('total_trades', 0)}")
            print(f"  - Net PnL: {run_info.get('net_pnl_pct', 0)*100:.2f}%")
            print(f"  - Win Rate: {run_info.get('win_rate', 0)*100:.1f}%")
            
            print(f"\nTrades: {len(trades)}")
            for i, trade in enumerate(trades[:3], 1):
                print(f"  {i}. {trade['trading_pair']} {trade['side']}: "
                      f"PnL {trade['net_pnl_pct']*100:.2f}%")
            
            print(f"\nLogs: {len(logs)}")
            for i, log in enumerate(logs[:3], 1):
                print(f"  {i}. [{log['log_level']}] {log['log_category']}: "
                      f"{log['log_message'][:50]}...")
            
            return True
        else:
            print(f"❌ Failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_stop_backtest(run_id):
    """Test stopping a backtest"""
    print("\n" + "="*80)
    print("TEST 5: Stop Backtest")
    print("="*80)
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/backtesting/stop/{run_id}",
            auth=AUTH,
            timeout=10
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Success!")
            print(json.dumps(result, indent=2))
            return True
        else:
            print(f"❌ Failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    print("="*80)
    print("AI Agent V1 Async Backtesting API - Test Suite")
    print("="*80)
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Auth: {AUTH[0]}:{'*'*len(AUTH[1])}")
    
    # Test 1: Start a new backtest
    run_id = test_start_backtest()
    
    if not run_id:
        print("\n⚠️  Cannot continue tests without a valid run_id")
        print("Trying to get an existing completed run from history...")
        runs = test_list_backtests()
        if runs:
            run_id = runs[0]["run_id"]
            print(f"Using run_id: {run_id}")
        else:
            print("❌ No runs found. Exiting.")
            return
    
    # Wait a bit for the backtest to start
    print("\n⏳ Waiting 2 seconds...")
    time.sleep(2)
    
    # Test 2: Get status
    status = test_get_status(run_id)
    
    # Test 3: List all backtests
    runs = test_list_backtests()
    
    # Test 4: Get results (use a completed run if available)
    if runs:
        completed_run_id = runs[0]["run_id"]
        test_get_results(completed_run_id)
    else:
        print("\n⚠️  No completed runs to test results")
    
    # Test 5: Stop backtest (only if still running)
    if status in ["PENDING", "RUNNING"]:
        print("\n⚠️  Backtest is still running. Do you want to stop it? (y/n)")
        # For automation, skip this
        # test_stop_backtest(run_id)
        print("Skipping stop test (automated mode)")
    
    print("\n" + "="*80)
    print("Test Suite Complete!")
    print("="*80)


if __name__ == "__main__":
    main()

