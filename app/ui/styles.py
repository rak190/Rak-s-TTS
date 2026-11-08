"""
Apple iPhone/Cupertino-inspired premium CSS styling for VoiceStudio AI (Stage 5C).
Includes:
- Full semantic token architecture for Light and OLED Dark modes.
- Systematic 4px spacing scale and harmonious border radii.
- Frosted glass (backdrop-filter) depth and subtle multi-layered shadows.
- Legally available system typography with extended line-height (1.65-1.7) for Khmer script.
- Responsive breakpoints down to 390px (iPhone 14/15/16).
- Accessible focus rings, micro-transitions, and custom Cupertino utility classes.
"""

IPHONE_INSPIRED_CSS = """
/* ==========================================================================
   VoiceStudio AI — Cupertino / iOS-Inspired Design System (Stage 5C)
   ========================================================================== */

/* --------------------------------------------------------------------------
   1. Design Tokens: Light Mode (Default)
   -------------------------------------------------------------------------- */
:root {
    /* Semantic Colors */
    --ios-bg: #F2F2F7;
    --ios-card-bg: rgba(255, 255, 255, 0.88);
    --ios-card-elevated: #FFFFFF;
    --ios-card-border: rgba(0, 0, 0, 0.08);
    --ios-card-border-subtle: rgba(0, 0, 0, 0.04);
    
    /* Apple System Blue & Accents */
    --ios-blue: #0071E3;
    --ios-blue-hover: #0077ED;
    --ios-blue-active: #006EDB;
    --ios-blue-subtle: rgba(0, 113, 227, 0.08);
    --ios-blue-glow: rgba(0, 113, 227, 0.22);
    
    /* Functional Status Colors */
    --ios-success: #34C759;
    --ios-success-bg: rgba(52, 199, 89, 0.12);
    --ios-warning: #FF9500;
    --ios-warning-bg: rgba(255, 149, 0, 0.12);
    --ios-error: #FF3B30;
    --ios-error-bg: rgba(255, 59, 48, 0.12);
    
    /* Cupertino Typography Colors */
    --ios-text-primary: #1D1D1F;
    --ios-text-secondary: #6E6E73;
    --ios-text-tertiary: #AEAEB2;
    --ios-text-on-accent: #FFFFFF;
    
    /* Controls & Inputs */
    --ios-input-bg: rgba(255, 255, 255, 0.95);
    --ios-input-border: rgba(0, 0, 0, 0.12);
    --ios-input-focus-border: #0071E3;
    
    /* Surfaces & Glass */
    --ios-header-bg: linear-gradient(135deg, rgba(255, 255, 255, 0.95) 0%, rgba(245, 245, 247, 0.88) 100%);
    --ios-glass-blur: blur(24px) saturate(180%);
    
    /* Harmonious Spacing Scale (4px Base Grid) */
    --space-1: 4px;
    --space-2: 8px;
    --space-3: 12px;
    --space-4: 16px;
    --space-5: 20px;
    --space-6: 24px;
    --space-8: 32px;
    --space-10: 40px;
    
    /* Border Radii */
    --ios-radius-xs: 8px;
    --ios-radius-sm: 10px;
    --ios-radius-md: 14px;
    --ios-radius-lg: 20px;
    --ios-radius-xl: 28px;
    --ios-radius-pill: 980px;
    
    /* Soft Layered Shadows */
    --ios-shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.04), 0 1px 2px rgba(0, 0, 0, 0.02);
    --ios-shadow-md: 0 4px 18px rgba(0, 0, 0, 0.05), 0 2px 6px rgba(0, 0, 0, 0.03);
    --ios-shadow-lg: 0 12px 36px rgba(0, 0, 0, 0.08), 0 4px 12px rgba(0, 0, 0, 0.04);
}

/* --------------------------------------------------------------------------
   2. Design Tokens: OLED Dark Mode
   -------------------------------------------------------------------------- */
@media (prefers-color-scheme: dark) {
    :root {
        --ios-bg: #000000;
        --ios-card-bg: rgba(28, 28, 30, 0.88);
        --ios-card-elevated: #2C2C2E;
        --ios-card-border: rgba(255, 255, 255, 0.12);
        --ios-card-border-subtle: rgba(255, 255, 255, 0.06);
        
        --ios-blue: #0A84FF;
        --ios-blue-hover: #409CFF;
        --ios-blue-active: #0071E3;
        --ios-blue-subtle: rgba(10, 132, 255, 0.16);
        --ios-blue-glow: rgba(10, 132, 255, 0.32);
        
        --ios-success: #30D158;
        --ios-success-bg: rgba(48, 209, 88, 0.16);
        --ios-warning: #FF9F0A;
        --ios-warning-bg: rgba(255, 159, 10, 0.16);
        --ios-error: #FF453A;
        --ios-error-bg: rgba(255, 69, 58, 0.16);
        
        --ios-text-primary: #F5F5F7;
        --ios-text-secondary: #8E8E93;
        --ios-text-tertiary: #636366;
        --ios-text-on-accent: #FFFFFF;
        
        --ios-input-bg: rgba(44, 44, 46, 0.85);
        --ios-input-border: rgba(255, 255, 255, 0.16);
        --ios-input-focus-border: #0A84FF;
        
        --ios-header-bg: linear-gradient(135deg, rgba(28, 28, 30, 0.95) 0%, rgba(18, 18, 20, 0.90) 100%);
        --ios-glass-blur: blur(28px) saturate(190%);
        
        --ios-shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.4);
        --ios-shadow-md: 0 4px 24px rgba(0, 0, 0, 0.55);
        --ios-shadow-lg: 0 14px 44px rgba(0, 0, 0, 0.75);
    }
}

.dark, [data-theme='dark'] {
    --ios-bg: #000000;
    --ios-card-bg: rgba(28, 28, 30, 0.88);
    --ios-card-elevated: #2C2C2E;
    --ios-card-border: rgba(255, 255, 255, 0.12);
    --ios-card-border-subtle: rgba(255, 255, 255, 0.06);
    
    --ios-blue: #0A84FF;
    --ios-blue-hover: #409CFF;
    --ios-blue-active: #0071E3;
    --ios-blue-subtle: rgba(10, 132, 255, 0.16);
    --ios-blue-glow: rgba(10, 132, 255, 0.32);
    
    --ios-success: #30D158;
    --ios-success-bg: rgba(48, 209, 88, 0.16);
    --ios-warning: #FF9F0A;
    --ios-warning-bg: rgba(255, 159, 10, 0.16);
    --ios-error: #FF453A;
    --ios-error-bg: rgba(255, 69, 58, 0.16);
    
    --ios-text-primary: #F5F5F7;
    --ios-text-secondary: #8E8E93;
    --ios-text-tertiary: #636366;
    --ios-text-on-accent: #FFFFFF;
    
    --ios-input-bg: rgba(44, 44, 46, 0.85);
    --ios-input-border: rgba(255, 255, 255, 0.16);
    --ios-input-focus-border: #0A84FF;
    
    --ios-header-bg: linear-gradient(135deg, rgba(28, 28, 30, 0.95) 0%, rgba(18, 18, 20, 0.90) 100%);
    --ios-glass-blur: blur(28px) saturate(190%);
    
    --ios-shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.4);
    --ios-shadow-md: 0 4px 24px rgba(0, 0, 0, 0.55);
    --ios-shadow-lg: 0 14px 44px rgba(0, 0, 0, 0.75);
}

/* --------------------------------------------------------------------------
   3. Global Layout & Typography Hierarchy
   -------------------------------------------------------------------------- */
body, .gradio-container {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Segoe UI", Roboto, "Helvetica Neue", "Kantumruy Pro", "Khmer OS Battambang", sans-serif !important;
    background-color: var(--ios-bg) !important;
    color: var(--ios-text-primary) !important;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    letter-spacing: -0.012em;
    line-height: 1.55;
    margin: 0;
    padding: 0;
}

/* Khmer Script & Multilingual Typography Line-Height Guarantee */
textarea, input, p, span, div, td, th, label {
    line-height: 1.6;
}

:lang(km), [data-lang="km"], .khmer-text {
    font-family: "Kantumruy Pro", "Khmer OS Battambang", -apple-system, sans-serif !important;
    line-height: 1.7 !important;
}

/* --------------------------------------------------------------------------
   4. Header Banner - Frosted Glass Cupertino Style
   -------------------------------------------------------------------------- */
.app-header {
    background: var(--ios-header-bg) !important;
    backdrop-filter: var(--ios-glass-blur);
    -webkit-backdrop-filter: var(--ios-glass-blur);
    border: 1px solid var(--ios-card-border) !important;
    border-radius: var(--ios-radius-lg) !important;
    padding: var(--space-6) var(--space-8) !important;
    margin-bottom: var(--space-5) !important;
    box-shadow: var(--ios-shadow-md) !important;
    transition: box-shadow 0.25s ease;
}

.app-header h1 {
    font-size: 28px !important;
    font-weight: 700 !important;
    letter-spacing: -0.03em !important;
    margin-top: 0 !important;
    margin-bottom: var(--space-1) !important;
    color: var(--ios-text-primary) !important;
}

.app-header h3 {
    font-size: 16px !important;
    font-weight: 500 !important;
    color: var(--ios-blue) !important;
    margin-top: 0 !important;
    margin-bottom: var(--space-2) !important;
}

.app-header p, .app-header em {
    font-size: 13px !important;
    color: var(--ios-text-secondary) !important;
}

/* --------------------------------------------------------------------------
   5. Card Containers & Panels
   -------------------------------------------------------------------------- */
.gr-box, .gr-panel, .tabitem, .cu-card {
    border-radius: var(--ios-radius-lg) !important;
    background: var(--ios-card-bg) !important;
    border: 1px solid var(--ios-card-border) !important;
    box-shadow: var(--ios-shadow-sm) !important;
    padding: var(--space-4) !important;
    margin-bottom: var(--space-4) !important;
    backdrop-filter: var(--ios-glass-blur);
    -webkit-backdrop-filter: var(--ios-glass-blur);
    transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
}

.cu-card:hover, .gr-box:hover, .gr-panel:hover {
    box-shadow: var(--ios-shadow-md) !important;
}

.cu-card-elevated {
    background: var(--ios-card-elevated) !important;
    border: 1px solid var(--ios-card-border) !important;
    box-shadow: var(--ios-shadow-md) !important;
    border-radius: var(--ios-radius-md) !important;
    padding: var(--space-4) !important;
}

/* --------------------------------------------------------------------------
   6. Buttons - iPhone Pill & Rounded Modern Action Styling
   -------------------------------------------------------------------------- */
.gr-button {
    border-radius: var(--ios-radius-pill) !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    padding: 10px 22px !important;
    transition: all 0.18s cubic-bezier(0.16, 1, 0.3, 1) !important;
    letter-spacing: -0.01em;
    cursor: pointer !important;
    border: 1px solid transparent !important;
}

.gr-button:active {
    transform: scale(0.97) !important;
}

.gr-button-primary {
    background: var(--ios-blue) !important;
    color: var(--ios-text-on-accent) !important;
    box-shadow: 0 4px 14px var(--ios-blue-glow) !important;
    border: none !important;
}

.gr-button-primary:hover {
    background: var(--ios-blue-hover) !important;
    transform: translateY(-1px);
    box-shadow: 0 6px 20px var(--ios-blue-glow) !important;
}

.gr-button-secondary {
    background: rgba(120, 120, 128, 0.12) !important;
    color: var(--ios-text-primary) !important;
    border: 1px solid var(--ios-card-border) !important;
}

.gr-button-secondary:hover {
    background: rgba(120, 120, 128, 0.18) !important;
    transform: translateY(-1px);
}

.gr-button-stop {
    background: var(--ios-error) !important;
    color: var(--ios-text-on-accent) !important;
    border: none !important;
    box-shadow: 0 4px 14px rgba(255, 59, 48, 0.25) !important;
}

.gr-button-stop:hover {
    background: #e03228 !important;
    transform: translateY(-1px);
}

/* --------------------------------------------------------------------------
   7. Form Controls, Textareas & Inputs
   -------------------------------------------------------------------------- */
input[type="text"], input[type="number"], textarea, select {
    border-radius: var(--ios-radius-sm) !important;
    border: 1px solid var(--ios-input-border) !important;
    background: var(--ios-input-bg) !important;
    color: var(--ios-text-primary) !important;
    font-size: 15px !important;
    padding: 10px 14px !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}

input:focus, textarea:focus, select:focus {
    border-color: var(--ios-input-focus-border) !important;
    box-shadow: 0 0 0 3px var(--ios-blue-glow) !important;
    outline: none !important;
}

/* Radio buttons & Checkboxes */
input[type="checkbox"], input[type="radio"] {
    accent-color: var(--ios-blue) !important;
    border-radius: 4px !important;
    cursor: pointer;
}

/* --------------------------------------------------------------------------
   8. Segmented Control & Navigation Tabs (Cupertino Capsule Nav)
   -------------------------------------------------------------------------- */
.tabs > .tab-nav {
    background: rgba(120, 120, 128, 0.12) !important;
    border-radius: var(--ios-radius-pill) !important;
    padding: var(--space-1) !important;
    display: inline-flex !important;
    margin-bottom: var(--space-5) !important;
    border: 1px solid var(--ios-card-border) !important;
    gap: 2px;
}

.tabs > .tab-nav > button {
    border-radius: var(--ios-radius-pill) !important;
    padding: 8px 18px !important;
    font-size: 13.5px !important;
    font-weight: 500 !important;
    color: var(--ios-text-secondary) !important;
    border: none !important;
    background: transparent !important;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
}

.tabs > .tab-nav > button:hover {
    color: var(--ios-text-primary) !important;
}

.tabs > .tab-nav > button.selected {
    background: var(--ios-card-elevated) !important;
    color: var(--ios-text-primary) !important;
    font-weight: 600 !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12) !important;
}

/* --------------------------------------------------------------------------
   9. Stat Cards & Metrics (Cupertino Metric Grid)
   -------------------------------------------------------------------------- */
.cu-metric-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: var(--space-3);
    margin-top: var(--space-2);
    margin-bottom: var(--space-4);
}

.cu-metric-card {
    background: rgba(120, 120, 128, 0.08);
    border-radius: var(--ios-radius-md);
    padding: var(--space-3) var(--space-4);
    border: 1px solid var(--ios-card-border);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.cu-metric-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--ios-shadow-sm);
}

.cu-metric-label {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--ios-text-secondary);
    margin-bottom: var(--space-1);
}

.cu-metric-value {
    font-size: 20px;
    font-weight: 700;
    color: var(--ios-text-primary);
    letter-spacing: -0.02em;
}

.cu-metric-note {
    font-size: 11.5px;
    color: var(--ios-text-secondary);
    margin-top: var(--space-1);
}

/* --------------------------------------------------------------------------
   10. Badges & Status Indicators
   -------------------------------------------------------------------------- */
.cu-badge {
    display: inline-flex;
    align-items: center;
    padding: 3px 10px;
    border-radius: var(--ios-radius-pill);
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.01em;
}

.cu-badge-green {
    background: var(--ios-success-bg);
    color: var(--ios-success);
    border: 1px solid rgba(52, 199, 89, 0.25);
}

.cu-badge-blue {
    background: var(--ios-blue-subtle);
    color: var(--ios-blue);
    border: 1px solid rgba(0, 113, 227, 0.25);
}

.cu-badge-orange {
    background: var(--ios-warning-bg);
    color: var(--ios-warning);
    border: 1px solid rgba(255, 149, 0, 0.25);
}

/* --------------------------------------------------------------------------
   11. Audio Player Surface
   -------------------------------------------------------------------------- */
.gr-audio {
    border-radius: var(--ios-radius-md) !important;
    border: 1px solid var(--ios-card-border) !important;
    background: var(--ios-card-bg) !important;
    overflow: hidden;
    padding: var(--space-3) !important;
}

/* --------------------------------------------------------------------------
   12. Data Tables & Dataframes
   -------------------------------------------------------------------------- */
.gr-dataframe {
    border-radius: var(--ios-radius-md) !important;
    overflow: hidden !important;
    border: 1px solid var(--ios-card-border) !important;
}

.gr-dataframe table {
    border-collapse: separate !important;
}

.gr-dataframe th {
    background: rgba(120, 120, 128, 0.08) !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    color: var(--ios-text-secondary) !important;
    border-bottom: 1px solid var(--ios-card-border) !important;
    padding: 10px 14px !important;
}

.gr-dataframe td {
    padding: 10px 14px !important;
    font-size: 13.5px !important;
    border-bottom: 1px solid var(--ios-card-border-subtle) !important;
}

/* --------------------------------------------------------------------------
   13. Responsive Breakpoints (Desktop, Tablet & iPhone 390px)
   -------------------------------------------------------------------------- */
@media (max-width: 1024px) {
    .app-header {
        padding: var(--space-5) var(--space-6) !important;
    }
    .cu-metric-grid {
        grid-template-columns: repeat(2, 1fr);
    }
}

@media (max-width: 768px) {
    .app-header {
        padding: var(--space-4) !important;
        margin-bottom: var(--space-4) !important;
    }
    .app-header h1 {
        font-size: 22px !important;
    }
    .tabs > .tab-nav {
        display: flex !important;
        flex-wrap: wrap !important;
        border-radius: var(--ios-radius-sm) !important;
        width: 100% !important;
    }
    .tabs > .tab-nav > button {
        padding: 6px 12px !important;
        font-size: 12.5px !important;
        flex: 1 1 auto;
        text-align: center;
    }
    .cu-metric-grid {
        grid-template-columns: 1fr;
    }
}

@media (max-width: 420px) {
    body, .gradio-container {
        padding: var(--space-2) !important;
    }
    .gr-box, .gr-panel, .tabitem, .cu-card {
        padding: var(--space-3) !important;
        border-radius: var(--ios-radius-md) !important;
    }
    .gr-button {
        padding: 8px 16px !important;
        font-size: 13px !important;
    }
}
"""
