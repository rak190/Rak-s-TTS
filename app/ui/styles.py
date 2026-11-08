"""
Apple iPhone/Cupertino-inspired premium CSS styling for VoiceStudio AI.
Supports seamless Light and Dark modes, frosted glass surfaces, responsive layouts,
and legally available system typography (SF Pro / Segoe UI / Kantumruy Pro for Khmer).
"""

IPHONE_INSPIRED_CSS = """
/* -------------------------------------------------------------
   VoiceStudio AI — Cupertino / iPhone-Inspired Design Theme
   ------------------------------------------------------------- */

:root {
    --ios-bg: #fbfbfd;
    --ios-card-bg: rgba(255, 255, 255, 0.88);
    --ios-card-border: rgba(0, 0, 0, 0.08);
    --ios-card-shadow: 0 4px 20px rgba(0, 0, 0, 0.04);
    --ios-card-shadow-hover: 0 8px 30px rgba(0, 0, 0, 0.08);
    --ios-blue: #0071e3;
    --ios-blue-hover: #0077ed;
    --ios-blue-active: #006edb;
    --ios-text-primary: #1d1d1f;
    --ios-text-secondary: #86868b;
    --ios-input-bg: rgba(255, 255, 255, 0.95);
    --ios-input-border: rgba(0, 0, 0, 0.12);
    --ios-header-bg: linear-gradient(135deg, rgba(255,255,255,0.92) 0%, rgba(245,245,247,0.85) 100%);
    --ios-radius: 16px;
    --ios-radius-sm: 10px;
}

/* Automatic & Manual Dark Mode (Cupertino OLED Dark) */
@media (prefers-color-scheme: dark) {
    :root {
        --ios-bg: #000000;
        --ios-card-bg: rgba(28, 28, 30, 0.88);
        --ios-card-border: rgba(255, 255, 255, 0.12);
        --ios-card-shadow: 0 4px 24px rgba(0, 0, 0, 0.4);
        --ios-card-shadow-hover: 0 8px 32px rgba(0, 0, 0, 0.6);
        --ios-blue: #0a84ff;
        --ios-blue-hover: #409cff;
        --ios-blue-active: #0071e3;
        --ios-text-primary: #f5f5f7;
        --ios-text-secondary: #8e8e93;
        --ios-input-bg: rgba(44, 44, 46, 0.85);
        --ios-input-border: rgba(255, 255, 255, 0.16);
        --ios-header-bg: linear-gradient(135deg, rgba(28,28,30,0.95) 0%, rgba(18,18,20,0.9) 100%);
    }
}

.dark, [data-theme='dark'] {
    --ios-bg: #000000;
    --ios-card-bg: rgba(28, 28, 30, 0.88);
    --ios-card-border: rgba(255, 255, 255, 0.12);
    --ios-card-shadow: 0 4px 24px rgba(0, 0, 0, 0.4);
    --ios-card-shadow-hover: 0 8px 32px rgba(0, 0, 0, 0.6);
    --ios-blue: #0a84ff;
    --ios-blue-hover: #409cff;
    --ios-blue-active: #0071e3;
    --ios-text-primary: #f5f5f7;
    --ios-text-secondary: #8e8e93;
    --ios-input-bg: rgba(44, 44, 46, 0.85);
    --ios-input-border: rgba(255, 255, 255, 0.16);
    --ios-header-bg: linear-gradient(135deg, rgba(28,28,30,0.95) 0%, rgba(18,18,20,0.9) 100%);
}

body, .gradio-container {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Segoe UI", Roboto, "Kantumruy Pro", "Khmer OS Battambang", sans-serif !important;
    background-color: var(--ios-bg) !important;
    color: var(--ios-text-primary) !important;
    -webkit-font-smoothing: antialiased;
    letter-spacing: -0.015em;
}

/* Header Banner - Frosted Glass Cupertino Style */
.app-header {
    background: var(--ios-header-bg) !important;
    backdrop-filter: blur(25px) saturate(180%);
    -webkit-backdrop-filter: blur(25px) saturate(180%);
    border: 1px solid var(--ios-card-border) !important;
    border-radius: var(--ios-radius) !important;
    padding: 24px 28px !important;
    margin-bottom: 22px !important;
    box-shadow: var(--ios-card-shadow);
}

.app-header h1 {
    font-weight: 700 !important;
    letter-spacing: -0.025em !important;
    margin-bottom: 4px !important;
    color: var(--ios-text-primary) !important;
}

.app-header h3 {
    font-weight: 500 !important;
    color: var(--ios-blue) !important;
    margin-top: 0 !important;
}

/* Card Containers & Panels */
.gr-box, .gr-panel, .tabitem, .cu-card {
    border-radius: var(--ios-radius) !important;
    background: var(--ios-card-bg) !important;
    border: 1px solid var(--ios-card-border) !important;
    box-shadow: var(--ios-card-shadow) !important;
    padding: 16px !important;
    margin-bottom: 14px !important;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.cu-card:hover {
    box-shadow: var(--ios-card-shadow-hover) !important;
}
    border: 1px solid var(--ios-card-border) !important;
    background: var(--ios-card-bg) !important;
    box-shadow: var(--ios-card-shadow);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.gr-box:hover, .gr-panel:hover {
    box-shadow: var(--ios-card-shadow-hover);
}

/* Buttons - iPhone Pill Styling */
.gr-button {
    border-radius: 980px !important;
    font-weight: 600 !important;
    padding: 10px 22px !important;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
    letter-spacing: -0.01em;
}

.gr-button-primary {
    background: var(--ios-blue) !important;
    color: #ffffff !important;
    border: none !important;
    box-shadow: 0 4px 14px rgba(0, 113, 227, 0.25) !important;
}

.gr-button-primary:hover {
    background: var(--ios-blue-hover) !important;
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(0, 113, 227, 0.35) !important;
}

.gr-button-secondary {
    background: rgba(120, 120, 128, 0.12) !important;
    color: var(--ios-text-primary) !important;
    border: 1px solid var(--ios-card-border) !important;
}

.gr-button-secondary:hover {
    background: rgba(120, 120, 128, 0.18) !important;
}

.gr-button-stop {
    background: #ff3b30 !important;
    color: #ffffff !important;
    border: none !important;
}

/* Input Fields & Textareas */
input, textarea, select {
    border-radius: var(--ios-radius-sm) !important;
    border: 1px solid var(--ios-input-border) !important;
    background: var(--ios-input-bg) !important;
    color: var(--ios-text-primary) !important;
    font-size: 15px !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

input:focus, textarea:focus, select:focus {
    border-color: var(--ios-blue) !important;
    box-shadow: 0 0 0 3px rgba(10, 132, 255, 0.25) !important;
    outline: none !important;
}

/* Segmented Control Navigation Tabs */
.tabs > .tab-nav {
    background: rgba(120, 120, 128, 0.12) !important;
    border-radius: 980px !important;
    padding: 4px !important;
    display: inline-flex !important;
    margin-bottom: 22px !important;
    border: 1px solid var(--ios-card-border) !important;
}

.tabs > .tab-nav > button {
    border-radius: 980px !important;
    padding: 8px 20px !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    color: var(--ios-text-secondary) !important;
    border: none !important;
    background: transparent !important;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
}

.tabs > .tab-nav > button.selected {
    background: var(--ios-card-bg) !important;
    color: var(--ios-text-primary) !important;
    box-shadow: 0 3px 12px rgba(0, 0, 0, 0.12) !important;
}

/* Telemetry & Metric Cards */
.telemetry-card {
    background: rgba(120, 120, 128, 0.08);
    border-radius: var(--ios-radius-sm);
    padding: 16px;
    border: 1px solid var(--ios-card-border);
    margin-top: 12px;
}

/* Audio Player Card */
.gr-audio {
    border-radius: var(--ios-radius) !important;
    border: 1px solid var(--ios-card-border) !important;
    background: var(--ios-card-bg) !important;
    overflow: hidden;
}

/* Responsive Mobile Layouts */
@media (max-width: 768px) {
    .app-header {
        padding: 18px !important;
    }
    .tabs > .tab-nav {
        display: flex !important;
        flex-wrap: wrap !important;
        border-radius: var(--ios-radius-sm) !important;
    }
    .tabs > .tab-nav > button {
        padding: 6px 12px !important;
        font-size: 13px !important;
    }
}
"""
