import json
import time
from datetime import datetime, timedelta

import pandas as pd
import requests
import streamlit as st
from plotly.subplots import make_subplots

from CONFIG import BACKEND_API_HOST, BACKEND_API_PASSWORD, BACKEND_API_PORT, BACKEND_API_USERNAME
from frontend.components.config_loader import get_default_config_loader
from frontend.components.save_config import render_save_config
from frontend.pages.config.ai_agent_v1.user_inputs import user_inputs
from frontend.pages.config.utils import get_candles
from frontend.st_utils import get_backend_api_client, initialize_st_page
from frontend.visualization import theme
from frontend.visualization.backtesting import create_backtesting_figure
from frontend.visualization.backtesting_metrics import (
    render_accuracy_metrics,
    render_backtesting_metrics,
    render_close_types
)
from frontend.visualization.candles import get_candlestick_trace
from frontend.visualization.indicators import get_volume_trace
from frontend.visualization.utils import add_traces_to_fig

# Initialize the Streamlit page
initialize_st_page(title="AI Agent V1", icon="🤖", initial_sidebar_state="expanded")
backend_api_client = get_backend_api_client()

# Build API base URL
if not BACKEND_API_HOST.startswith(('http://', 'https://')):
    API_BASE_URL = f"http://{BACKEND_API_HOST}:{BACKEND_API_PORT}"
else:
    API_BASE_URL = f"{BACKEND_API_HOST}:{BACKEND_API_PORT}"

AUTH = (BACKEND_API_USERNAME, BACKEND_API_PASSWORD)


# ============================================================================
# Helper Functions
# ============================================================================

def safe_float_format(value, precision=2, prefix="", suffix="", multiplier=1, default="N/A"):
    """
    Safely format a float value with error handling.
    
    Args:
        value: The value to format (can be None, str, int, float)
        precision: Number of decimal places
        prefix: String to prepend (e.g., "$")
        suffix: String to append (e.g., "%")
        multiplier: Multiply value before formatting (e.g., 100 for percentages)
        default: Default value if parsing fails
    
    Returns:
        Formatted string or default value
    """
    try:
        if value is None:
            return default
        
        # Convert to float
        if isinstance(value, str):
            value = float(value)
        elif not isinstance(value, (int, float)):
            return default
        
        # Apply multiplier
        value = value * multiplier
        
        # Format with precision
        formatted = f"{value:.{precision}f}"
        
        return f"{prefix}{formatted}{suffix}"
    except (ValueError, TypeError, AttributeError):
        return default


def safe_get_json_response(response):
    """
    Safely parse JSON response with error handling.
    
    Args:
        response: requests.Response object
    
    Returns:
        Parsed JSON data or None with error message
    """
    try:
        return response.json(), None
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON response: {str(e)}\nResponse text: {response.text[:200]}"
        return None, error_msg
    except Exception as e:
        error_msg = f"Error parsing response: {str(e)}"
        return None, error_msg


# ============================================================================
# Streamlit UI
# ============================================================================


st.markdown("""
## 🤖 AI Agent V1 - LLM-Powered Trading Controller

This AI trading agent uses LangChain and OpenRouter to make intelligent trading decisions based on:
- **Technical Indicators**: RSI, MACD, EMA, price action
- **Market Data**: Real-time prices, funding rates (for perpetuals)
- **Historical Performance**: Learning from past trades
- **Multi-Asset**: Monitors multiple trading pairs simultaneously

### 🎯 How it works:
1. **Data Collection**: Gathers market data and technical indicators for all trading pairs
2. **AI Decision**: Uses LLM to analyze data and generate trading signals
3. **Risk Management**: Validates decisions and applies position sizing rules
4. **Execution**: Opens/closes positions based on AI recommendations

### ⚠️ Important Notes:
- Requires a valid **OpenRouter API Key** (get one at https://openrouter.ai)
- LLM calls are **real** and will incur costs (recommend using `deepseek/deepseek-chat` for low cost)
- Backtesting will make **actual API calls** to the LLM
- This is an **experimental** controller - use with caution!
""")

get_default_config_loader("ai_agent_v1")

# Get user inputs
inputs = user_inputs()
st.session_state["default_config"].update(inputs)

# Validate API key
if not inputs.get("openrouter_api_key"):
    st.warning("⚠️ Please enter your OpenRouter API Key in the AI Configuration section!")
else:
    st.success("✅ OpenRouter API Key configured")

st.write("---")
st.write("### 📊 Market Data Preview")
st.write(f"**Monitoring:** {', '.join(inputs['trading_pairs'])}")

# Show candles for the first trading pair
days_to_visualize = st.number_input("Days to Visualize", min_value=1, max_value=30, value=7)

try:
    # Load candle data for the primary trading pair
    candles = get_candles(
        connector_name=inputs["connector_name"],
        trading_pair=inputs["trading_pairs"][0],
        interval=inputs["candles_interval"],
        days=days_to_visualize
    )
    
    # Create a subplot with 2 rows
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.02,
        subplot_titles=(f'{inputs["trading_pairs"][0]} - Price', 'Volume'),
        row_heights=[0.8, 0.2]
    )
    
    add_traces_to_fig(fig, [get_candlestick_trace(candles)], row=1, col=1)
    add_traces_to_fig(fig, [get_volume_trace(candles)], row=2, col=1)
    
    fig.update_layout(**theme.get_default_layout())
    st.plotly_chart(fig, use_container_width=True)
    
except Exception as e:
    st.error(f"Error loading candles: {e}")

st.write("---")

# ============================================================================
# NEW: Async Backtesting Section with Real-time Monitoring
# ============================================================================

st.write("### 🔬 Async Backtest Configuration")

# Create tabs for different sections
tab_config, tab_monitor, tab_history = st.tabs(["⚙️ New Backtest", "📊 Monitor Runs", "📜 History"])

with tab_config:
    st.write("#### Configure and Start a New Backtest")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        run_name = st.text_input("Backtest Name", value=f"AI Agent Test {datetime.now().strftime('%Y%m%d_%H%M')}")
        
    with col2:
        default_end_time = datetime.now().date() - timedelta(days=1)
        default_start_time = default_end_time - timedelta(days=2)
        start_date = st.date_input("Start Date", default_start_time)
        
    with col3:
        end_date = st.date_input("End Date", default_end_time)
    
    col4, col5 = st.columns(2)
    
    with col4:
        backtesting_resolution = st.selectbox("Resolution", ["1m", "3m", "5m", "15m", "30m", "1h"], index=2)
        
    with col5:
        trade_cost = st.number_input("Trade Cost (%)", min_value=0.0, max_value=1.0, value=0.06, step=0.01, format="%.3f")
    
    # Build config for API call
    backtest_config = {
        "controller_name": inputs["controller_name"],
        "controller_type": inputs["controller_type"],
        "connector_name": inputs["connector_name"],
        "trading_pair": inputs["trading_pair"],
        "total_amount_quote": inputs["total_amount_quote"],
        "trading_pairs": inputs["trading_pairs"],
        "max_concurrent_positions": inputs["max_concurrent_positions"],
        "single_position_size_pct": inputs["single_position_size_pct"],
        "decision_interval": inputs["decision_interval"],
        "candles_connector": inputs["candles_connector"],
        "candles_trading_pair": inputs["candles_trading_pair"],
        "candles_interval": inputs["candles_interval"],
        "interval": inputs["interval"],
        "candles_max_records": inputs["candles_max_records"],
        # "openrouter_api_key": inputs["openrouter_api_key"],
        "llm_model": inputs["llm_model"],
        "llm_temperature": inputs["llm_temperature"],
        "llm_max_tokens": inputs["llm_max_tokens"],
        "leverage": inputs["leverage"],
        "position_mode": inputs["position_mode"],
        "stop_loss": inputs["stop_loss"],
        "take_profit": inputs["take_profit"],
        "time_limit": inputs["time_limit"],
        "trailing_stop": inputs["trailing_stop"],
        "custom_system_prompt": inputs.get("custom_system_prompt")
    }
    
    # Show config preview
    with st.expander("📋 View Full Config"):
        st.json(backtest_config)
    
    # Start backtest button
    if st.button("🚀 Start Backtest", type="primary", use_container_width=True):
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())
        
        payload = {
            "run_name": run_name,
            "start_time": int(start_datetime.timestamp()),
            "end_time": int(end_datetime.timestamp()),
            "backtesting_resolution": backtesting_resolution,
            "trade_cost": trade_cost / 100,
            "config": backtest_config
        }
        
        try:
            with st.spinner("Starting backtest..."):
                response = requests.post(
                    f"{API_BASE_URL}/backtesting/start",
                    json=payload,
                    auth=AUTH,
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    run_id = result.get("run_id")
                    st.success(f"✅ Backtest started successfully!")
                    st.info(f"**Run ID:** `{run_id}`")
                    st.info("Switch to the **Monitor Runs** tab to track progress")
                    
                    # Store in session state for easy access
                    if "active_runs" not in st.session_state:
                        st.session_state["active_runs"] = []
                    st.session_state["active_runs"].append(run_id)
                else:
                    st.error(f"❌ Failed to start backtest: {response.status_code} - {response.text}")
                    
        except Exception as e:
            st.error(f"❌ Error starting backtest: {e}")

with tab_monitor:
    st.write("#### Monitor Backtest Runs")
    
    # Step 1: Fetch and display list of recent runs
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.write("**Select a backtest run to monitor:**")
    
    with col2:
        if st.button("🔄 Refresh List", use_container_width=True, key="refresh_monitor_list"):
            # Force refresh by clearing cache
            if "monitor_selected_run" in st.session_state:
                del st.session_state["monitor_selected_run"]
            st.rerun()
    
    try:
        # Fetch recent runs (prioritize RUNNING and PENDING)
        response = requests.get(
            f"{API_BASE_URL}/backtesting/list",
            params={"limit": 20},
            auth=AUTH,
            timeout=10
        )
        
        if response.status_code == 200:
            data, error = safe_get_json_response(response)
            if error:
                st.error(f"❌ {error}")
                monitor_run_id = None
            else:
                runs = data.get("runs", [])
                
                if runs and len(runs) > 0:
                    # Sort: RUNNING first, then PENDING, then others by created_at (newest first)
                    status_priority = {"RUNNING": 0, "PENDING": 1, "COMPLETED": 2, "FAILED": 3, "CANCELLED": 4}
                    
                    # Sort by status priority and created_at (descending)
                    sorted_runs = sorted(
                        runs, 
                        key=lambda x: (
                            status_priority.get(x.get("status", ""), 999),
                            x.get("created_at", "2000-01-01") or "2000-01-01"
                        ),
                        reverse=False  # Status ascending
                    )
                    
                    # Now reverse within each status group to get newest first
                    final_sorted = []
                    current_status = None
                    current_group = []
                    
                    for run in sorted_runs:
                        run_status = run.get("status", "")
                        if current_status is None:
                            current_status = run_status
                        
                        if run_status == current_status:
                            current_group.append(run)
                        else:
                            # Reverse current group and add to final
                            current_group.reverse()
                            final_sorted.extend(current_group)
                            # Start new group
                            current_status = run_status
                            current_group = [run]
                    
                    # Don't forget the last group
                    if current_group:
                        current_group.reverse()
                        final_sorted.extend(current_group)
                    
                    sorted_runs = final_sorted
                    
                    # Create a selection table
                    st.write(f"Found **{len(sorted_runs)}** backtest runs (sorted by status and time):")
                    
                    # Build selection options with status emoji
                    options = []
                    for run in sorted_runs:
                        status = run.get("status", "UNKNOWN")
                        status_emoji = {
                            "PENDING": "⏳",
                            "RUNNING": "🏃",
                            "COMPLETED": "✅",
                            "FAILED": "❌",
                            "CANCELLED": "🛑"
                        }.get(status, "❓")
                        
                        run_name = run.get("run_name", "N/A")
                        created_at = run.get("created_at", "")
                        created_display = created_at[:19] if created_at else "N/A"
                        total_trades = run.get("total_trades")
                        trades_display = f"{total_trades} trades" if total_trades is not None else "No trades"
                        
                        option_text = f"{status_emoji} {status} | {run_name} | {created_display} | {trades_display}"
                        options.append(option_text)
                    
                    # Selection box
                    selected_idx = st.selectbox(
                        "Choose a run:",
                        range(len(sorted_runs)),
                        format_func=lambda i: options[i],
                        key="monitor_run_selector"
                    )
                    
                    # Store selected run
                    monitor_run_id = sorted_runs[selected_idx]["run_id"]
                    
                    # Add manual input option for advanced users
                    with st.expander("🔧 Advanced: Enter Run ID Manually"):
                        manual_run_id = st.text_input(
                            "Manual Run ID",
                            value="",
                            placeholder="Paste run_id here if not in list",
                            key="manual_run_id_input"
                        )
                        if manual_run_id:
                            monitor_run_id = manual_run_id
                            st.info(f"Using manual run_id: `{manual_run_id[:8]}...`")
                    
                else:
                    st.info("📝 No backtest runs found yet.")
                    st.write("**Get started:**")
                    st.write("1. Go to the **'⚙️ New Backtest'** tab")
                    st.write("2. Configure your backtest parameters")
                    st.write("3. Click **'🚀 Start Backtest'**")
                    st.write("4. Come back here to monitor progress!")
                    monitor_run_id = None
                    
        else:
            st.error(f"❌ Failed to fetch runs: {response.status_code} - {response.text}")
            monitor_run_id = None
            
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        st.error(f"❌ Error fetching runs: {str(e)}")
        with st.expander("🔍 Error Details (for debugging)"):
            st.code(error_details)
        monitor_run_id = None
    
    # Step 2: Display detailed status for selected run
    if monitor_run_id:
        st.write("---")
        st.write(f"### 📊 Monitoring: `{monitor_run_id[:8]}...`")
        
        col1, col2 = st.columns([4, 1])
        with col1:
            st.caption("Auto-refresh: Use the refresh button to update status")
        with col2:
            if st.button("🔄 Update Status", use_container_width=True, key="refresh_status_detail"):
                st.rerun()
        
        try:
            # Fetch status
            response = requests.get(
                f"{API_BASE_URL}/backtesting/status/{monitor_run_id}",
                auth=AUTH,
                timeout=10
            )
            
            if response.status_code == 200:
                data, error = safe_get_json_response(response)
                if error:
                    st.error(f"❌ {error}")
                else:
                    status_data = data
                    
                    # Display status
                    status = status_data.get("status", "UNKNOWN")
                    status_emoji = {
                        "PENDING": "⏳",
                        "RUNNING": "🏃",
                        "COMPLETED": "✅",
                        "FAILED": "❌",
                        "CANCELLED": "🛑"
                    }.get(status, "❓")
                    
                    st.write(f"### {status_emoji} Status: **{status}**")
                    
                    # Display key metrics
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("Run Name", status_data.get("run_name", "N/A"))
                        
                    with col2:
                        st.metric("Controller", status_data.get("controller_name", "N/A"))
                        
                    with col3:
                        total_trades = status_data.get("total_trades")
                        st.metric("Total Trades", total_trades if total_trades is not None else "N/A")
                        
                    with col4:
                        net_pnl_pct = status_data.get("net_pnl_pct")
                        pnl_display = safe_float_format(net_pnl_pct, precision=2, multiplier=100, suffix="%")
                        st.metric("Net PnL", pnl_display, delta=pnl_display if net_pnl_pct is not None else None)
                    
                    # Show more metrics if completed
                    if status == "COMPLETED":
                        st.write("---")
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            win_rate = status_data.get("win_rate")
                            win_rate_display = safe_float_format(win_rate, precision=1, multiplier=100, suffix="%")
                            st.metric("Win Rate", win_rate_display)
                        
                        with col2:
                            sharpe = status_data.get("sharpe_ratio")
                            sharpe_display = safe_float_format(sharpe, precision=2)
                            st.metric("Sharpe Ratio", sharpe_display)
                        
                        with col3:
                            max_dd = status_data.get("max_drawdown")
                            max_dd_display = safe_float_format(max_dd, precision=2, multiplier=100, suffix="%")
                            st.metric("Max Drawdown", max_dd_display)
                        
                        with col4:
                            net_pnl_quote = status_data.get("net_pnl_quote")
                            net_pnl_quote_display = safe_float_format(net_pnl_quote, precision=2, prefix="$")
                            st.metric("Net PnL (USDT)", net_pnl_quote_display)
                    
                    # Show timing info
                    with st.expander("⏱️ Timing Details"):
                        st.write(f"**Created:** {status_data.get('created_at', 'N/A')}")
                        st.write(f"**Started:** {status_data.get('started_at', 'N/A')}")
                        st.write(f"**Completed:** {status_data.get('completed_at', 'N/A')}")
                    
                    # Show error if failed
                    if status == "FAILED":
                        st.error(f"**Error:** {status_data.get('error_message', 'Unknown error')}")
                    
                    # Show stop button if running
                    if status in ["PENDING", "RUNNING"]:
                        col1, col2 = st.columns([1, 1])
                        with col1:
                            if st.button("🛑 Stop Backtest", type="secondary", use_container_width=True):
                                try:
                                    stop_response = requests.post(
                                        f"{API_BASE_URL}/backtesting/stop/{monitor_run_id}",
                                        auth=AUTH,
                                        timeout=10
                                    )
                                    
                                    if stop_response.status_code == 200:
                                        st.success("✅ Stop signal sent")
                                        time.sleep(1)
                                        st.rerun()
                                    else:
                                        st.error(f"❌ Failed to stop: {stop_response.text}")
                                except Exception as e:
                                    st.error(f"❌ Error: {e}")
                        
                        with col2:
                            if st.button("📜 View Live Logs", type="primary", use_container_width=True):
                                st.session_state["view_live_logs_run_id"] = monitor_run_id
                                st.rerun()
                    
                    # Show results button if completed
                    if status == "COMPLETED":
                        st.write("---")
                        col1, col2 = st.columns([1, 1])
                        with col1:
                            if st.button("📊 View Full Results", type="primary", use_container_width=True):
                                st.session_state["view_results_run_id"] = monitor_run_id
                                st.rerun()
                        with col2:
                            if st.button("📜 View All Logs", type="secondary", use_container_width=True):
                                st.session_state["view_live_logs_run_id"] = monitor_run_id
                                st.rerun()
                    
                    # Live logs preview (for RUNNING status)
                    if status == "RUNNING" and "view_live_logs_run_id" not in st.session_state:
                        st.write("---")
                        st.write("#### 📜 Recent Logs (Last 10)")
                        
                        try:
                            logs_response = requests.get(
                                f"{API_BASE_URL}/backtesting/results/{monitor_run_id}",
                                params={"include_logs": True, "log_limit": 10},
                                auth=AUTH,
                                timeout=10
                            )
                            
                            if logs_response.status_code == 200:
                                logs_data, logs_error = safe_get_json_response(logs_response)
                                if not logs_error:
                                    logs = logs_data.get("logs", [])
                                    if logs:
                                        for log in reversed(logs[-10:]):  # Show most recent first
                                            if not isinstance(log, dict):
                                                continue
                                            
                                            log_level = log.get("log_level", "INFO")
                                            log_emoji = {
                                                "INFO": "ℹ️",
                                                "DEBUG": "🐛",
                                                "WARNING": "⚠️",
                                                "ERROR": "❌"
                                            }.get(log_level, "📝")
                                            
                                            timestamp = log.get("timestamp", "")[:19]
                                            category = log.get("log_category", "UNKNOWN")
                                            message = log.get("log_message", "")[:150]
                                            
                                            st.text(f"{log_emoji} [{timestamp}] {category}: {message}...")
                                    else:
                                        st.info("No logs yet")
                        except Exception as e:
                            st.warning(f"Could not fetch logs: {e}")
                
            else:
                st.error(f"❌ Failed to fetch status: {response.status_code} - {response.text}")
                
        except Exception as e:
            st.error(f"❌ Error fetching status: {e}")

with tab_history:
    st.write("#### Backtest History")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        history_limit = st.number_input("Limit", min_value=5, max_value=100, value=20, step=5)
    
    with col2:
        filter_status = st.selectbox("Filter by Status", ["All", "COMPLETED", "FAILED", "RUNNING", "PENDING"])
    
    with col3:
        st.write("")  # Spacing
        st.write("")  # Spacing
        refresh_history = st.button("🔄 Refresh History", use_container_width=True)
    
    try:
        # Build query params
        params = {"limit": history_limit}
        if filter_status != "All":
            params["status"] = filter_status
        
        response = requests.get(
            f"{API_BASE_URL}/backtesting/list",
            params=params,
            auth=AUTH,
            timeout=10
        )
        
        if response.status_code == 200:
            data, error = safe_get_json_response(response)
            if error:
                st.error(f"❌ {error}")
            else:
                runs = data.get("runs", [])
                
                if runs:
                    st.write(f"Found **{len(runs)}** backtest runs:")
                    
                    # Convert to DataFrame for better display
                    df_data = []
                    for run in runs:
                        # Safely get total_trades with None check
                        total_trades = run.get("total_trades")
                        trades_display = total_trades if total_trades is not None else 0
                        
                        # Safely format net_pnl_pct
                        net_pnl_pct = run.get("net_pnl_pct")
                        pnl_display = safe_float_format(net_pnl_pct, precision=2, multiplier=100, suffix="%")
                        
                        # Safely format win_rate
                        win_rate = run.get("win_rate")
                        win_rate_display = safe_float_format(win_rate, precision=1, multiplier=100, suffix="%")
                        
                        # Safely get created_at
                        created_at = run.get("created_at")
                        created_display = created_at[:19] if created_at else "N/A"
                        
                        df_data.append({
                            "Run ID": run["run_id"][:8] + "...",
                            "Name": run.get("run_name", "N/A"),
                            "Controller": run.get("controller_name", "N/A"),
                            "Status": run.get("status", "UNKNOWN"),
                            "Trades": trades_display,
                            "Net PnL %": pnl_display,
                            "Win Rate": win_rate_display,
                            "Created": created_display,
                            "Full Run ID": run["run_id"]
                        })
                    
                    df = pd.DataFrame(df_data)
                    
                    # Display table (hide full run_id column)
                    st.dataframe(
                        df.drop(columns=["Full Run ID"]),
                        use_container_width=True,
                        hide_index=True
                    )
                    
                    # Allow selection to view details
                    st.write("---")
                    selected_idx = st.selectbox(
                        "Select a run to view details:",
                        range(len(runs)),
                        format_func=lambda i: f"{runs[i]['run_name']} - {runs[i]['status']}"
                    )
                    
                    if st.button("📊 View Selected Run", use_container_width=True):
                        selected_run_id = runs[selected_idx]["run_id"]
                        st.session_state["view_results_run_id"] = selected_run_id
                        st.rerun()
                        
                else:
                    st.info("No backtest runs found")
                
        else:
            st.error(f"❌ Failed to fetch history: {response.status_code} - {response.text}")
            
    except Exception as e:
        st.error(f"❌ Error fetching history: {e}")

# ============================================================================
# Live Logs Viewer (separate section)
# ============================================================================

if "view_live_logs_run_id" in st.session_state:
    st.write("---")
    st.write("### 📜 Live Logs Viewer")
    
    run_id = st.session_state["view_live_logs_run_id"]
    
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        st.write(f"**Run ID:** `{run_id[:8]}...`")
    with col2:
        if st.button("🔄 Refresh Logs", use_container_width=True):
            st.rerun()
    with col3:
        if st.button("❌ Close", use_container_width=True):
            del st.session_state["view_live_logs_run_id"]
            st.rerun()
    
    try:
        # Fetch logs
        col1, col2 = st.columns([1, 1])
        with col1:
            log_limit = st.slider("Number of logs to display", min_value=10, max_value=200, value=50, step=10)
        with col2:
            auto_scroll = st.checkbox("Show newest first", value=True)
        
        response = requests.get(
            f"{API_BASE_URL}/backtesting/results/{run_id}",
            params={"include_logs": True, "log_limit": log_limit},
            auth=AUTH,
            timeout=30
        )
        
        if response.status_code == 200:
            results, error = safe_get_json_response(response)
            if error:
                st.error(f"❌ {error}")
            else:
                logs = results.get("logs", [])
                
                if logs:
                    # Filter by category
                    try:
                        log_categories = sorted(list(set(
                            log.get("log_category", "UNKNOWN") 
                            for log in logs 
                            if isinstance(log, dict)
                        )))
                    except Exception:
                        log_categories = ["UNKNOWN"]
                    
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        selected_category = st.selectbox("Filter by Category", ["All"] + log_categories, key="live_log_category")
                    with col2:
                        selected_level = st.selectbox("Filter by Level", ["All", "INFO", "DEBUG", "WARNING", "ERROR"], key="live_log_level")
                    
                    # Filter logs
                    filtered_logs = logs
                    if selected_category != "All":
                        filtered_logs = [log for log in filtered_logs if isinstance(log, dict) and log.get("log_category") == selected_category]
                    if selected_level != "All":
                        filtered_logs = [log for log in filtered_logs if isinstance(log, dict) and log.get("log_level") == selected_level]
                    
                    # Reverse if newest first
                    if auto_scroll:
                        filtered_logs = list(reversed(filtered_logs))
                    
                    st.write(f"**Showing {len(filtered_logs)} logs:**")
                    
                    # Display logs in a container
                    with st.container():
                        for log in filtered_logs:
                            if not isinstance(log, dict):
                                continue
                            
                            log_level = log.get("log_level", "INFO")
                            log_emoji = {
                                "INFO": "ℹ️",
                                "DEBUG": "🐛",
                                "WARNING": "⚠️",
                                "ERROR": "❌"
                            }.get(log_level, "📝")
                            
                            timestamp = log.get("timestamp", "")
                            timestamp_display = timestamp[:19] if timestamp else "N/A"
                            
                            log_category = log.get("log_category", "UNKNOWN")
                            log_message = log.get("log_message", "")
                            message_preview = log_message[:100] if log_message else "Empty log"
                            
                            with st.expander(f"{log_emoji} [{timestamp_display}] {log_category} - {message_preview}"):
                                st.text(log_message)
                else:
                    st.info("No logs available yet")
        else:
            st.error(f"❌ Failed to fetch logs: {response.status_code} - {response.text}")
            
    except Exception as e:
        st.error(f"❌ Error fetching logs: {e}")


# ============================================================================
# Results Viewer (separate section)
# ============================================================================

if "view_results_run_id" in st.session_state:
    st.write("---")
    st.write("### 📊 Detailed Results")
    
    run_id = st.session_state["view_results_run_id"]
    
    col1, col2 = st.columns([4, 1])
    with col1:
        st.write(f"**Run ID:** `{run_id}`")
    with col2:
        if st.button("❌ Close Results"):
            del st.session_state["view_results_run_id"]
            st.rerun()
    
    try:
        # Fetch full results
        response = requests.get(
            f"{API_BASE_URL}/backtesting/results/{run_id}",
            params={"include_logs": True, "log_limit": 100},
            auth=AUTH,
            timeout=30
        )
        
        if response.status_code == 200:
            results, error = safe_get_json_response(response)
            if error:
                st.error(f"❌ {error}")
            else:
                # Display summary
                run_info = results.get("run_info", {})
                trades = results.get("trades", [])
                logs = results.get("logs", [])
                
                # Metrics
                col1, col2, col3, col4, col5 = st.columns(5)
                
                with col1:
                    total_trades = run_info.get("total_trades")
                    st.metric("Total Trades", total_trades if total_trades is not None else 0)
                with col2:
                    net_pnl_pct = run_info.get("net_pnl_pct")
                    pnl_display = safe_float_format(net_pnl_pct, precision=2, multiplier=100, suffix="%")
                    st.metric("Net PnL", pnl_display)
                with col3:
                    win_rate = run_info.get("win_rate")
                    win_rate_display = safe_float_format(win_rate, precision=1, multiplier=100, suffix="%")
                    st.metric("Win Rate", win_rate_display)
                with col4:
                    sharpe = run_info.get("sharpe_ratio")
                    sharpe_display = safe_float_format(sharpe, precision=2)
                    st.metric("Sharpe", sharpe_display)
                with col5:
                    max_dd = run_info.get("max_drawdown")
                    max_dd_display = safe_float_format(max_dd, precision=2, multiplier=100, suffix="%")
                    st.metric("Max DD", max_dd_display)
                
                # Trades table
                if trades:
                    st.write("---")
                    st.write(f"#### 💼 Trades ({len(trades)})")
                    
                    trades_df_data = []
                    for t in trades:
                        # Safely handle all fields with None checks
                        entry_price = t.get("entry_price", 0)
                        exit_price = t.get("exit_price")
                        amount = t.get("amount", 0)
                        net_pnl_pct = t.get("net_pnl_pct", 0)
                        net_pnl_quote = t.get("net_pnl_quote", 0)
                        
                        trades_df_data.append({
                            "Symbol": t.get("trading_pair", "N/A"),
                            "Side": t.get("side", "N/A"),
                            "Entry Price": f"${entry_price:.2f}" if entry_price else "N/A",
                            "Exit Price": f"${exit_price:.2f}" if exit_price else "N/A",
                            "Amount": f"{amount:.4f}" if amount else "N/A",
                            "PnL %": f"{net_pnl_pct*100:.2f}%" if net_pnl_pct is not None else "N/A",
                            "PnL Quote": f"${net_pnl_quote:.2f}" if net_pnl_quote is not None else "N/A",
                            "Close Type": t.get("close_type", "N/A"),
                            "Status": t.get("status", "N/A")
                        })
                    
                    trades_df = pd.DataFrame(trades_df_data)
                    st.dataframe(trades_df, use_container_width=True, hide_index=True)
                
                # Logs section
                if logs:
                    st.write("---")
                    st.write(f"#### 📜 Logs ({len(logs)})")
                    
                    # Filter logs by category - safely handle empty or invalid log entries
                    try:
                        log_categories = sorted(list(set(
                            log.get("log_category", "UNKNOWN") 
                            for log in logs 
                            if isinstance(log, dict)
                        )))
                    except Exception as e:
                        st.warning(f"⚠️ Error parsing log categories: {e}")
                        log_categories = ["UNKNOWN"]
                    
                    selected_category = st.selectbox("Filter by Category", ["All"] + log_categories)
                    
                    filtered_logs = logs
                    if selected_category != "All":
                        filtered_logs = [
                            log for log in logs 
                            if isinstance(log, dict) and log.get("log_category") == selected_category
                        ]
                    
                    # Display logs with safe parsing
                    for log in filtered_logs:
                        if not isinstance(log, dict):
                            continue
                            
                        log_level = log.get("log_level", "INFO")
                        log_emoji = {
                            "INFO": "ℹ️",
                            "DEBUG": "🐛",
                            "WARNING": "⚠️",
                            "ERROR": "❌"
                        }.get(log_level, "📝")
                        
                        timestamp = log.get("timestamp", "")
                        timestamp_display = timestamp[:19] if timestamp else "N/A"
                        
                        log_category = log.get("log_category", "UNKNOWN")
                        log_message = log.get("log_message", "")
                        message_preview = log_message[:100] if log_message else "Empty log"
                        
                        with st.expander(f"{log_emoji} [{timestamp_display}] {log_category} - {message_preview}"):
                            st.text(log_message)
            
        else:
            st.error(f"❌ Failed to fetch results: {response.status_code} - {response.text}")
            
    except Exception as e:
        st.error(f"❌ Error fetching results: {e}")

st.write("---")
render_save_config(st.session_state["default_config"]["id"], st.session_state["default_config"])


