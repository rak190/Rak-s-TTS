"""
Apple iPhone-inspired premium CSS styling for VoiceStudio AI.
Implements Cupertino design language: frosted glass surfaces, SF Pro typography,
smooth rounded corners, micro-elevation shadows, and refined pill controls.
"""

IPHONE_INSPIRED_CSS = """
/* -------------------------------------------------------------
   VoiceStudio AI — Cupertino / iPhone-Inspired Design Theme
   ------------------------------------------------------------- */

:root {
    --ios-bg: #fbfbfd;
    --ios-card-bg: rgba(255, 255, 255, 0.85);
    --ios-card-border: rgba(0, 0, 0, 0.08);
    --ios-card-shadow: 0 4px 20px rgba(0, 0, 0, 0.04);
    --ios-card-shadow-hover: 0 8px 30px rgba(0, 0, 0, 0.08);
    --ios-blue: #0071e3;
    --ios-blue-hover: #0077ed;
    --ios-blue-active: #006edb;
    --ios-text-primary: #1d1d1f;
    --ios-text-secondary: #86868b;
    --ios-radius: 16px;
    --ios-radius-sm: 10px;
}

body, .gradio-container {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Segoe UI", Roboto, "Khmer OS Battambang", "Kantumruy Pro", sans-serif !important;
    background-color: var(--ios-bg) !important;
    color: var(--ios-text-primary) !important;
    -webkit-font-smoothing: antialiased;
}

/* Header Banner */
.app-header {
    background: linear-gradient(135deg, rgba(255,255,255,0.9) 0%, rgba(245,245,247,0.8) 100%);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid var(--ios-card-border);
    border-radius: var(--ios-radius);
    padding: 24px;
    margin-bottom: 20px;
    box-shadow: var(--ios-card-shadow);
}

/* Card Containers */
.gr-box, .gr-panel, .tabitem {
    border-radius: var(--ios-radius) !important;
    border: 1px solid var(--ios-card-border) !important;
    background: var(--ios-card-bg) !important;
    box-shadow: var(--ios-card-shadow);
    transition: all 0.25s ease-in-out;
}

/* Buttons - iPhone Pill Styling */
.gr-button {
    border-radius: 980px !important;
    font-weight: 500 !important;
    padding: 10px 22px !important;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
    letter-spacing: -0.01em;
}

.gr-button-primary {
    background: var(--ios-blue) !important;
    color: #ffffff !important;
    border: none !important;
    box-shadow: 0 4px 14px rgba(0, 113, 227, 0.28) !important;
}

.gr-button-primary:hover {
    background: var(--ios-blue-hover) !important;
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(0, 113, 227, 0.36) !important;
}

.gr-button-secondary {
    background: rgba(0, 0, 0, 0.04) !important;
    color: var(--ios-text-primary) !important;
    border: 1px solid rgba(0, 0, 0, 0.06) !important;
}

.gr-button-secondary:hover {
    background: rgba(0, 0, 0, 0.07) !important;
}

/* Input Fields */
input, textarea, select {
    border-radius: var(--ios-radius-sm) !important;
    border: 1px solid rgba(0, 0, 0, 0.12) !important;
    background: rgba(255, 255, 255, 0.9) !important;
    font-size: 15px !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

input:focus, textarea:focus, select:focus {
    border-color: var(--ios-blue) !important;
    box-shadow: 0 0 0 3px rgba(0, 113, 227, 0.2) !important;
    outline: none !important;
}

/* Tabs Navigation - Segmented Control */
.tabs > .tab-nav {
    background: rgba(0, 0, 0, 0.05) !important;
    border-radius: 980px !important;
    padding: 4px !important;
    display: inline-flex !important;
    margin-bottom: 20px !important;
    border: 1px solid rgba(0, 0, 0, 0.04) !important;
}

.tabs > .tab-nav > button {
    border-radius: 980px !important;
    padding: 8px 18px !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    color: var(--ios-text-secondary) !important;
    border: none !important;
    background: transparent !important;
    transition: all 0.2s ease !important;
}

.tabs > .tab-nav > button.selected {
    background: #ffffff !important;
    color: var(--ios-text-primary) !important;
    box-shadow: 0 3px 10px rgba(0, 0, 0, 0.1) !important;
}

/* Badges & Telemetry Cards */
.telemetry-card {
    background: rgba(245, 245, 247, 0.7);
    border-radius: var(--ios-radius-sm);
    padding: 16px;
    border: 1px solid rgba(0, 0, 0, 0.06);
    margin-top: 12px;
}

/* Progress Bar */
.progress-bar-container {
    height: 8px;
    border-radius: 980px;
    background: rgba(0, 0, 0, 0.06);
    overflow: hidden;
}

.progress-bar-fill {
    height: 100%;
    background: var(--ios-blue);
    border-radius: 980px;
    transition: width 0.3s ease;
}
"""
