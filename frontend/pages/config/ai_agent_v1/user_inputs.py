import streamlit as st

from frontend.components.risk_management import get_risk_management_inputs


def user_inputs():
    """AI Agent V1 的用户输入界面"""
    default_config = st.session_state.get("default_config", {})
    
    # ==================== 基本配置 ====================
    with st.expander("🔧 Basic Configuration", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            connector_name = st.selectbox(
                "Connector",
                ["binance_perpetual", "okx_perpetual", "bybit_perpetual"],
                index=0
            )
            leverage = st.number_input("Leverage", min_value=1, max_value=20, value=default_config.get("leverage", 5))
        with c2:
            total_amount_quote = st.number_input(
                "Total Amount (USDT)",
                min_value=10,
                max_value=100000,
                value=default_config.get("total_amount_quote", 1000)
            )
            max_concurrent_positions = st.number_input(
                "Max Concurrent Positions",
                min_value=1,
                max_value=10,
                value=default_config.get("max_concurrent_positions", 2)
            )
    
    # ==================== 交易对配置 ====================
    with st.expander("💱 Trading Pairs", expanded=True):
        trading_pairs_str = st.text_area(
            "Trading Pairs (one per line)",
            value=default_config.get("trading_pairs_str", "BTC-USDT\nETH-USDT"),
            height=100
        )
        trading_pairs = [pair.strip() for pair in trading_pairs_str.split("\n") if pair.strip()]
        st.info(f"📊 Monitoring {len(trading_pairs)} trading pairs")
    
    # ==================== AI 配置 ====================
    with st.expander("🤖 AI Configuration", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            openrouter_api_key = st.text_input(
                "OpenRouter API Key",
                value=default_config.get("openrouter_api_key", ""),
                type="password",
                help="Get your API key from https://openrouter.ai. Leave empty to use OPENROUTER_API_KEY env var."
            )
            llm_model = st.selectbox(
                "LLM Model",
                [
                    "deepseek/deepseek-chat",
                    "anthropic/claude-3.5-sonnet",
                    "openai/gpt-4-turbo"
                ],
                index=0
            )
        with c2:
            decision_interval = st.number_input(
                "Decision Interval (seconds)",
                min_value=60,
                max_value=3600,
                value=default_config.get("decision_interval", 300),
                help="How often the AI makes trading decisions"
            )
            llm_temperature = st.slider(
                "LLM Temperature",
                min_value=0.0,
                max_value=1.0,
                value=default_config.get("llm_temperature", 0.1),
                step=0.1
            )
    
    # ==================== 自定义 System Prompt ====================
    with st.expander("📝 Custom System Prompt (Advanced)", expanded=False):
        st.markdown("""
        **Customize the AI's trading strategy and decision-making framework.**
        
        Leave empty to use the default high-probability trading framework, or provide your own custom instructions.
        
        💡 **Tips:**
        - Define specific trading rules and conditions
        - Set risk tolerance and position management guidelines
        - Specify indicator preferences (RSI, MACD, EMA, etc.)
        - Add market condition filters
        - Include your trading philosophy
        """)
        
        custom_system_prompt = st.text_area(
            "Custom System Prompt",
            value=default_config.get("custom_system_prompt", ""),
            height=400,
            placeholder="""Example:
# Custom Trading Framework

## Market Analysis
- Focus on momentum breakouts with volume confirmation
- Avoid choppy/sideways markets (wait for clear trend)
- RSI must be between 40-70 for entries

## Position Management
- Maximum 2% risk per trade
- Always use 2:1 minimum risk/reward ratio
- Scale out at 50% profit, let remainder run

## Entry Rules
- LONG: Price > EMA(20), MACD crossing up, RSI 40-60, volume > average
- SHORT: Price < EMA(20), MACD crossing down, RSI 40-60, volume > average

## Exit Rules
- Stop loss: Below recent swing low (LONG) or above swing high (SHORT)
- Take profit: Previous resistance (LONG) or support (SHORT)
- Exit immediately if MACD crosses against position

Your custom framework here...""",
            help="This will replace the default trading framework. The AI will follow these instructions instead."
        )
        
        if custom_system_prompt:
            st.success(f"✅ Custom system prompt configured ({len(custom_system_prompt)} characters)")
            with st.expander("👁️ Preview Custom Prompt"):
                st.text(custom_system_prompt)
        else:
            st.info("ℹ️ Using default high-probability trading framework")
    
    # ==================== K线配置 ====================
    with st.expander("📊 Candles Configuration", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            candles_interval = st.selectbox(
                "Candles Interval",
                ["1m", "3m", "5m", "15m", "1h"],
                index=2  # 5m
            )
        with c2:
            candles_max_records = st.number_input(
                "Max Records",
                min_value=20,
                max_value=500,
                value=default_config.get("candles_max_records", 100)
            )
    
    # ==================== 资金管理 ====================
    with st.expander("💰 Position Sizing", expanded=True):
        single_position_size_pct = st.slider(
            "Single Position Size (%)",
            min_value=10,
            max_value=100,
            value=int(default_config.get("single_position_size_pct", 0.4) * 100),
            help="Percentage of total amount for each position"
        ) / 100
    
    # ==================== 风险控制 ====================
    with st.expander("🛡️ Risk Management", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            stop_loss = st.number_input(
                "Stop Loss (%)",
                min_value=0.5,
                max_value=10.0,
                value=default_config.get("stop_loss", 2.5) * 100 if isinstance(default_config.get("stop_loss"), (int, float)) else 2.5,
                step=0.5,
                format="%.1f",
                help="Exit position if loss reaches this percentage"
            ) / 100
        with c2:
            take_profit = st.number_input(
                "Take Profit (%)",
                min_value=1.0,
                max_value=20.0,
                value=default_config.get("take_profit", 5.0) * 100 if isinstance(default_config.get("take_profit"), (int, float)) else 5.0,
                step=0.5,
                format="%.1f",
                help="Exit position if profit reaches this percentage"
            ) / 100
        
        st.info("ℹ️ Time limit and trailing stop are disabled for AI Agent V1 (AI controls exit timing)")
    
    # 返回配置
    return {
        "controller_name": "ai_agent_v1",
        "controller_type": "directional_trading",
        "connector_name": connector_name,
        "trading_pair": trading_pairs[0] if trading_pairs else "BTC-USDT",  # 主交易对
        "trading_pairs": trading_pairs,
        
        # Candles configuration (required for backtesting)
        # 注意：interval 和 candles_interval 必须保持一致
        "candles_connector": connector_name,
        "candles_trading_pair": trading_pairs[0] if trading_pairs else "BTC-USDT",
        "interval": candles_interval,  # 与 candles_interval 保持一致
        
        # Trading parameters
        "leverage": leverage,
        "total_amount_quote": total_amount_quote,
        "max_concurrent_positions": max_concurrent_positions,
        "single_position_size_pct": single_position_size_pct,
        
        # AI configuration
        "openrouter_api_key": openrouter_api_key,
        "llm_model": llm_model,
        "llm_temperature": llm_temperature,
        "llm_max_tokens": 4000,
        "decision_interval": decision_interval,
        "custom_system_prompt": custom_system_prompt if custom_system_prompt else None,
        
        # Candles settings
        "candles_interval": candles_interval,
        "candles_max_records": candles_max_records,
        
        # Risk management (flat structure, not nested)
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "time_limit": None,  # AI controls exit timing
        "trailing_stop": None,  # AI controls exit timing
        
        # Position mode
        "position_mode": "ONEWAY"
    }


