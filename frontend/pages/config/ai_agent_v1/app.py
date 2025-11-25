import streamlit as st
from plotly.subplots import make_subplots

from frontend.components.backtesting import backtesting_section
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
st.write("### 🔬 Backtest Configuration")

# Backtesting section
bt_results = backtesting_section(inputs, backend_api_client)

if bt_results:
    st.write("### 📈 Backtest Results")
    
    # Create figure
    fig = create_backtesting_figure(
        df=bt_results["processed_data"],
        executors=bt_results["executors"],
        config=inputs
    )
    
    c1, c2 = st.columns([0.9, 0.1])
    with c1:
        render_backtesting_metrics(bt_results["results"])
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        render_accuracy_metrics(bt_results["results"])
        st.write("---")
        render_close_types(bt_results["results"])
    
    # Additional AI-specific metrics
    st.write("---")
    st.write("### 🤖 AI Agent Insights")
    
    executors = bt_results["executors"]
    if executors:
        # Group by trading pair
        pairs_stats = {}
        for executor in executors:
            pair = executor.get("config", {}).get("trading_pair", "Unknown")
            if pair not in pairs_stats:
                pairs_stats[pair] = {"count": 0, "wins": 0, "pnl": 0}
            
            pairs_stats[pair]["count"] += 1
            pnl = executor.get("net_pnl_quote", 0)
            pairs_stats[pair]["pnl"] += pnl
            if pnl > 0:
                pairs_stats[pair]["wins"] += 1
        
        # Display per-pair statistics
        st.write("**Performance by Trading Pair:**")
        cols = st.columns(len(pairs_stats))
        for i, (pair, stats) in enumerate(pairs_stats.items()):
            with cols[i]:
                win_rate = (stats["wins"] / stats["count"]) * 100 if stats["count"] > 0 else 0
                st.metric(
                    label=pair,
                    value=f"${stats['pnl']:.2f}",
                    delta=f"{win_rate:.1f}% win rate"
                )
                st.caption(f"{stats['count']} trades")

st.write("---")
render_save_config(st.session_state["default_config"]["id"], st.session_state["default_config"])


