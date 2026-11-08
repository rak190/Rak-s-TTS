"""
VoiceStudio Pro — Apple Creative Workspace Design System.
Synthesizes:
- ElevenLabs Studio: Large script editing canvas, voice selection, waveform audio timeline.
- Apple Human Interface Guidelines: Mac/iOS creative workspace, clean typography, refined hierarchy.
- Linear: Quiet dark sidebar, restrained borders, layered surfaces (#0B0D12, #11131A, #191C25, #222634).
- Descript: Text-and-audio workflow, audio waveform timeline, contextual inspector properties.
Supports seamless Light and Dark modes, legally available typography, and extended line-height for Khmer script.
"""

STUDIO_PRO_CSS = """
/* ==========================================================================
   VoiceStudio Pro — Apple Creative Workspace Design System
   ========================================================================== */

/* --------------------------------------------------------------------------
   1. Design Tokens: Dark Mode (Linear / Apple Dark First)
   -------------------------------------------------------------------------- */
:root, .dark, [data-theme='dark'] {
    /* Surface Palette (Layered Obsidian & Slate) */
    --studio-bg: #0B0D12;
    --studio-sidebar-bg: #11131A;
    --studio-surface: #181B24;
    --studio-surface-elevated: #222634;
    --studio-surface-card: #1D212C;
    --studio-surface-hover: #2A2F40;
    --studio-surface-active: #32384D;
    
    /* Borders & Hairlines */
    --studio-border: #2C303F;
    --studio-border-subtle: #1E222E;
    --studio-border-focus: #8F7CF2;
    
    /* Linear Restrained Accents (Electric Violet / Lavender) */
    --studio-accent: #8F7CF2;
    --studio-accent-hover: #A08FF8;
    --studio-accent-active: #7A66E8;
    --studio-accent-subtle: rgba(143, 124, 242, 0.12);
    --studio-accent-glow: rgba(143, 124, 242, 0.28);
    --studio-accent-text: #FFFFFF;

    /* Functional Semantics */
    --studio-success: #58C9A1;
    --studio-success-bg: rgba(88, 201, 161, 0.12);
    --studio-warning: #E9B76E;
    --studio-warning-bg: rgba(233, 183, 110, 0.12);
    --studio-error: #F26C6D;
    --studio-error-bg: rgba(242, 108, 109, 0.14);
    
    /* Typography Colors */
    --studio-text-primary: #F6F7FB;
    --studio-text-secondary: #9FA4B5;
    --studio-text-muted: #64697B;
    --studio-text-link: #8F7CF2;
    
    /* Controls & Inputs */
    --studio-input-bg: #141720;
    --studio-input-border: #2C303F;
    
    /* Waveform & Audio Player Colors */
    --studio-wave-bg: #131620;
    --studio-wave-bar: #8F7CF2;
    --studio-wave-played: #A08FF8;
    
    /* Spacing & Radii */
    --space-1: 4px;
    --space-2: 8px;
    --space-3: 12px;
    --space-4: 16px;
    --space-5: 20px;
    --space-6: 24px;
    --space-8: 32px;
    
    --radius-sm: 8px;
    --radius-md: 12px;
    --radius-lg: 16px;
    --radius-xl: 20px;
    --radius-pill: 980px;

    /* Shadows */
    --shadow-soft: 0 4px 20px rgba(0, 0, 0, 0.35);
    --shadow-elevated: 0 12px 36px rgba(0, 0, 0, 0.55);
}

/* --------------------------------------------------------------------------
   2. Design Tokens: Light Mode (Apple Studio Clean Light)
   -------------------------------------------------------------------------- */
body:not(.dark) {
    --studio-bg: #F4F5F8;
    --studio-sidebar-bg: #EAECEF;
    --studio-surface: #FFFFFF;
    --studio-surface-elevated: #F8F9FA;
    --studio-surface-card: #FFFFFF;
    --studio-surface-hover: #F0F2F5;
    --studio-surface-active: #E4E7EB;
    
    --studio-border: #E0E2E7;
    --studio-border-subtle: #ECEEF2;
    --studio-border-focus: #6E56CF;
    
    --studio-accent: #6E56CF;
    --studio-accent-hover: #5B44BA;
    --studio-accent-active: #4F38AA;
    --studio-accent-subtle: rgba(110, 86, 207, 0.08);
    --studio-accent-glow: rgba(110, 86, 207, 0.20);
    --studio-accent-text: #FFFFFF;

    --studio-success: #2A9D6E;
    --studio-success-bg: rgba(42, 157, 110, 0.10);
    --studio-warning: #C97D1A;
    --studio-warning-bg: rgba(201, 125, 26, 0.10);
    --studio-error: #D64242;
    --studio-error-bg: rgba(214, 66, 66, 0.10);
    
    --studio-text-primary: #121417;
    --studio-text-secondary: #606775;
    --studio-text-muted: #8E95A5;
    --studio-text-link: #6E56CF;
    
    --studio-input-bg: #FFFFFF;
    --studio-input-border: #D5D8DF;
    
    --studio-wave-bg: #F0F2F6;
    --studio-wave-bar: #6E56CF;
    --studio-wave-played: #5B44BA;

    --shadow-soft: 0 2px 10px rgba(0, 0, 0, 0.04);
    --shadow-elevated: 0 8px 24px rgba(0, 0, 0, 0.08);
}

/* --------------------------------------------------------------------------
   3. Global Layout & Typography
   -------------------------------------------------------------------------- */
body, .gradio-container {
    background-color: var(--studio-bg) !important;
    color: var(--studio-text-primary) !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, "Helvetica Neue", "Kantumruy Pro", "Khmer OS Battambang", sans-serif !important;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    letter-spacing: -0.011em;
    line-height: 1.55;
    padding: 0 !important;
    margin: 0 !important;
    max-width: 100% !important;
}

/* Khmer Script & Multilingual Line-Height Optimization */
textarea, input, p, span, div, td, th, label {
    line-height: 1.6;
}

:lang(km), [data-lang="km"], .khmer-text {
    font-family: "Kantumruy Pro", "Khmer OS Battambang", -apple-system, sans-serif !important;
    line-height: 1.7 !important;
}

/* --------------------------------------------------------------------------
   4. Desktop App Shell: Left Sidebar + Main Workspace
   -------------------------------------------------------------------------- */
/* --------------------------------------------------------------------------
   4. Desktop App Shell: Sleek macOS / Linear Creative Toolbar & Workspace
   -------------------------------------------------------------------------- */
.studio-app-header {
    display: flex !important;
    justify-content: space-between !important;
    align-items: center !important;
    padding: 12px 24px !important;
    background: var(--studio-sidebar-bg) !important;
    border-bottom: 1px solid var(--studio-border) !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.25) !important;
}

@media (max-width: 768px) {
    .studio-app-header {
        flex-direction: column !important;
        align-items: flex-start !important;
        gap: 8px !important;
        padding: 10px 14px !important;
    }
}

.main-studio-tabs {
    background: transparent !important;
    border: none !important;
    margin: 0 !important;
    padding: 0 !important;
}

/* Linear & macOS Segmented Tab Navigation Bar */
.main-studio-tabs > .tab-nav {
    display: flex !important;
    align-items: center !important;
    gap: 6px !important;
    background: var(--studio-sidebar-bg) !important;
    border-bottom: 1px solid var(--studio-border) !important;
    padding: 8px 16px !important;
    margin: 0 0 20px 0 !important;
    border-radius: 0 !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2) !important;
    overflow-x: auto !important;
    white-space: nowrap !important;
    border: none !important;
    border-bottom: 1px solid var(--studio-border) !important;
}

/* Tab Navigation Buttons (Apple Segmented Pill / Linear Nav) */
.main-studio-tabs > .tab-nav > button {
    display: inline-flex !important;
    align-items: center !important;
    gap: 8px !important;
    padding: 8px 16px !important;
    border-radius: var(--radius-sm) !important;
    font-size: 13.5px !important;
    font-weight: 500 !important;
    color: var(--studio-text-secondary) !important;
    background: transparent !important;
    border: 1px solid transparent !important;
    transition: all 0.15s ease !important;
    cursor: pointer !important;
    white-space: nowrap !important;
    margin: 0 !important;
}

.main-studio-tabs > .tab-nav > button:hover {
    background: var(--studio-surface-hover) !important;
    color: var(--studio-text-primary) !important;
}

.main-studio-tabs > .tab-nav > button.selected {
    background: var(--studio-surface-elevated) !important;
    color: var(--studio-text-primary) !important;
    font-weight: 600 !important;
    border: 1px solid var(--studio-border) !important;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.25) !important;
    border-bottom: 2px solid var(--studio-accent) !important;
}

/* Main Workspace Canvas Container */
.main-studio-tabs > div:not(.tab-nav) {
    padding: 0 24px 32px 24px !important;
    max-width: 1440px !important;
    margin: 0 auto !important;
    width: 100% !important;
}

/* --------------------------------------------------------------------------
   5. Elimination of Generic Blue Labels & Nested Box Clutter
   -------------------------------------------------------------------------- */
/* Eliminate bright blue background rectangles on labels */
.gr-form, .gr-block, .gr-box {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
}

label span, .gr-form > label {
    font-size: 11.5px !important;
    font-weight: 600 !important;
    color: var(--studio-text-secondary) !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    margin-bottom: 6px !important;
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
}

/* Form Controls & Inputs */
input[type="text"], input[type="number"], textarea, select {
    background: var(--studio-input-bg) !important;
    border: 1px solid var(--studio-input-border) !important;
    color: var(--studio-text-primary) !important;
    border-radius: var(--radius-sm) !important;
    padding: 10px 14px !important;
    font-size: 14.5px !important;
    transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
}

input:focus, textarea:focus, select:focus {
    border-color: var(--studio-border-focus) !important;
    box-shadow: 0 0 0 3px var(--studio-accent-subtle) !important;
    outline: none !important;
}

/* --------------------------------------------------------------------------
   6. ElevenLabs & Descript Flagship Components
   -------------------------------------------------------------------------- */
/* Studio Workspace Canvas */
.studio-canvas-card {
    background: var(--studio-surface) !important;
    border: 1px solid var(--studio-border) !important;
    border-radius: var(--radius-lg) !important;
    padding: var(--space-5) !important;
    box-shadow: var(--shadow-soft) !important;
    margin-bottom: var(--space-4) !important;
}

/* Large Script Editor (ElevenLabs Style) */
.script-editor-canvas textarea {
    font-size: 17px !important;
    line-height: 1.7 !important;
    padding: 18px 22px !important;
    border-radius: var(--radius-md) !important;
    background: var(--studio-surface-card) !important;
    border: 1px solid var(--studio-border) !important;
    min-height: 280px !important;
    color: var(--studio-text-primary) !important;
    letter-spacing: -0.01em !important;
}

.script-editor-canvas textarea:focus {
    border-color: var(--studio-border-focus) !important;
    box-shadow: 0 0 0 4px var(--studio-accent-subtle) !important;
}

/* Studio Inspector Panel (Right Column) */
.studio-inspector {
    background: var(--studio-surface-card) !important;
    border: 1px solid var(--studio-border) !important;
    border-radius: var(--radius-lg) !important;
    padding: 18px !important;
}

/* Speaker Profile Pill / Card */
.speaker-avatar-card {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 14px;
    background: var(--studio-surface-elevated);
    border: 1px solid var(--studio-border);
    border-radius: var(--radius-md);
    margin-bottom: 12px;
}

.speaker-avatar-badge {
    width: 38px;
    height: 38px;
    border-radius: var(--radius-pill);
    background: linear-gradient(135deg, var(--studio-accent) 0%, #4F38AA 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    font-weight: 700;
    color: #FFFFFF;
}

/* Signature Waveform & Audio Player (Descript Style) */
.studio-waveform-player {
    background: var(--studio-wave-bg) !important;
    border: 1px solid var(--studio-border) !important;
    border-radius: var(--radius-md) !important;
    padding: 16px 20px !important;
    margin-top: 14px !important;
}

.studio-transport-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-top: 10px;
    border-top: 1px solid var(--studio-border-subtle);
    margin-top: 10px;
}

/* --------------------------------------------------------------------------
   7. Buttons & Micro-Interactions (Linear Restrained Accent)
   -------------------------------------------------------------------------- */
.gr-button {
    border-radius: var(--radius-pill) !important;
    font-size: 13.5px !important;
    font-weight: 600 !important;
    padding: 9px 20px !important;
    letter-spacing: -0.01em !important;
    cursor: pointer !important;
    transition: all 0.16s ease !important;
    border: 1px solid transparent !important;
}

.gr-button:active {
    transform: scale(0.98) !important;
}

/* Hero Primary Action (Linear Violet) */
.gr-button-primary, .studio-btn-primary {
    background: var(--studio-accent) !important;
    color: var(--studio-accent-text) !important;
    border: none !important;
    box-shadow: 0 4px 14px var(--studio-accent-glow) !important;
}

.gr-button-primary:hover, .studio-btn-primary:hover {
    background: var(--studio-accent-hover) !important;
    box-shadow: 0 6px 20px var(--studio-accent-glow) !important;
    transform: translateY(-1px);
}

.gr-button-secondary, .studio-btn-secondary {
    background: var(--studio-surface-elevated) !important;
    color: var(--studio-text-primary) !important;
    border: 1px solid var(--studio-border) !important;
}

.gr-button-secondary:hover, .studio-btn-secondary:hover {
    background: var(--studio-surface-hover) !important;
    border-color: var(--studio-border-focus) !important;
}

.gr-button-stop {
    background: var(--studio-error-bg) !important;
    color: var(--studio-error) !important;
    border: 1px solid rgba(242, 108, 109, 0.3) !important;
}

.gr-button-stop:hover {
    background: var(--studio-error) !important;
    color: #FFFFFF !important;
}

/* --------------------------------------------------------------------------
   8. Status Pills, Metric Cards & Badges
   -------------------------------------------------------------------------- */
.studio-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 3px 10px;
    border-radius: var(--radius-pill);
    font-size: 12px;
    font-weight: 600;
}

.studio-pill-success {
    background: var(--studio-success-bg);
    color: var(--studio-success);
    border: 1px solid rgba(88, 201, 161, 0.25);
}

.studio-pill-accent {
    background: var(--studio-accent-subtle);
    color: var(--studio-accent);
    border: 1px solid rgba(143, 124, 242, 0.25);
}

.studio-pill-muted {
    background: rgba(100, 105, 123, 0.12);
    color: var(--studio-text-muted);
    border: 1px solid var(--studio-border-subtle);
}

/* Studio Metric Grid */
.studio-metric-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
    gap: 12px;
    margin-bottom: 16px;
}

.studio-metric-card {
    background: var(--studio-surface-card);
    border: 1px solid var(--studio-border);
    border-radius: var(--radius-md);
    padding: 12px 16px;
    transition: transform 0.15s ease;
}

.studio-metric-card:hover {
    transform: translateY(-1px);
    border-color: var(--studio-border-focus);
}

.studio-metric-label {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--studio-text-secondary);
    margin-bottom: 4px;
}

.studio-metric-value {
    font-size: 19px;
    font-weight: 700;
    color: var(--studio-text-primary);
    letter-spacing: -0.02em;
}

.studio-metric-sub {
    font-size: 11px;
    color: var(--studio-text-muted);
    margin-top: 3px;
}
"""

# Maintain backwards compatibility aliases
IPHONE_INSPIRED_CSS = STUDIO_PRO_CSS
