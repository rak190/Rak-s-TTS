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

STUDIO_PRO_CSS += r"""
/* Stage 5C TTS workstation: compact navigation rail and writing-first canvas */
.studio-app-header {
  position: fixed !important; inset: 0 auto 0 0 !important; width: 218px !important;
  z-index: 100 !important; display: flex !important; flex-direction: column !important;
  justify-content: flex-start !important; align-items: flex-start !important;
  padding: 25px 20px !important; border: 0 !important; border-right: 1px solid var(--studio-border) !important;
  box-shadow: none !important; background: var(--studio-sidebar-bg) !important;
}
.studio-app-header > div:first-child { flex-wrap: wrap; gap: 9px !important; }
.studio-app-header > div:last-child { display: none !important; }
.gradio-container .main { width:100% !important; max-width:none !important; }
.gradio-container main.contain { width:100% !important; max-width:none !important; margin:0 !important; padding:0 !important; }
.gradio-container main.contain > .column { width:100% !important; min-width:0 !important; }
.main-studio-tabs > .tab-wrapper {
  position:fixed !important; z-index:101 !important; left:0 !important; top:86px !important;
  bottom:0 !important; width:218px !important; height:auto !important; max-width:none !important;
  box-sizing:border-box !important; padding:12px !important; margin:0 !important;
  overflow-y:auto !important; border:0 !important; border-right:1px solid var(--studio-border) !important;
  border-radius:0 !important; background:var(--studio-sidebar-bg) !important;
}
.main-studio-tabs > .tab-wrapper > .tab-container {
  width:100% !important; display:flex !important; flex-direction:column !important;
  align-items:stretch !important; justify-content:flex-start !important; gap:3px !important;
  border:0 !important; background:transparent !important; overflow:visible !important;
}
.main-studio-tabs > .tab-wrapper [role="tab"] { justify-content:flex-start !important; width:100% !important; min-height:38px !important; padding:9px 11px !important; border:0 !important; border-radius:8px !important; font-size:13px !important; color:var(--studio-text-secondary) !important; }
.main-studio-tabs > .tab-wrapper [role="tab"][aria-selected="true"] { color:var(--studio-text-primary) !important; background:var(--studio-surface-active) !important; box-shadow:inset 2px 0 var(--studio-accent) !important; }
.main-studio-tabs > .tabitem { margin:0 0 0 218px !important; padding:30px 38px 48px !important; width:calc(100% - 218px) !important; max-width:none !important; box-sizing:border-box !important; }
.main-studio-tabs > .tabitem > .column { width:100% !important; min-width:0 !important; max-width:1420px !important; margin:0 auto !important; }
.gradio-container .block.padded { padding:0 !important; background:transparent !important; border-color:transparent !important; box-shadow:none !important; }
.tts-workspace .form { background:transparent !important; border:0 !important; box-shadow:none !important; padding:0 !important; }
.tts-page-head { display:flex; align-items:center; justify-content:space-between; gap:20px; margin:0 auto 26px; max-width:1420px; }
.tts-page-head h1 { margin:2px 0 4px; font-size:30px; line-height:1.2; letter-spacing:-.035em; font-weight:650; color:var(--studio-text-primary); }
.tts-page-head p { margin:0; font-size:14px; color:var(--studio-text-secondary); }
.eyebrow { font-size:10px; font-weight:650; letter-spacing:.11em; color:var(--studio-text-muted); text-transform:uppercase; }
.local-status { color:var(--studio-text-secondary); font-size:12px; display:flex; align-items:center; gap:8px; }
.local-status i { width:7px;height:7px;border-radius:50%;background:var(--studio-success); display:inline-block; }
.tts-workspace { max-width:1420px; margin:0 auto !important; gap:34px !important; align-items:flex-start !important; }
.tts-editor-column { min-width:0 !important; }
.project-row { align-items:end !important; gap:20px !important; }
.project-title { max-width:440px; }
.script-count { font-size:12px !important; color:var(--studio-text-secondary) !important; text-align:right; padding-bottom:9px; }
.script-count p { margin:0 !important; }
.editor-caption { display:flex; justify-content:space-between; align-items:center; margin:18px 2px 8px; color:var(--studio-text-primary); font-size:14px; font-weight:600; }
.editor-caption span+span { color:var(--studio-text-muted); font-size:11px; font-weight:500; }
.script-editor-canvas textarea { min-height:385px !important; height: min(48vh, 500px) !important; background:var(--studio-surface) !important; border:1px solid var(--studio-border-subtle) !important; border-radius:12px !important; padding:24px 26px !important; font-size:17px !important; line-height:1.82 !important; resize:vertical !important; }
.script-editor-canvas textarea::placeholder { color:var(--studio-text-muted) !important; }
.editor-footer { align-items:center !important; gap:16px !important; padding:12px 2px 0 !important; }
.workflow-mode { flex:1; }
.workflow-mode > label { text-transform:none !important; letter-spacing:0 !important; font-size:12px !important; }
.workflow-mode [role=radio] { padding:7px 11px !important; background:transparent !important; border-color:var(--studio-border) !important; }
.chapter-preview { margin-top:8px !important; }
.section-divider,.inspector-rule { height:1px; background:var(--studio-border-subtle); margin:24px 0 20px; }
.output-heading { display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }
.output-heading h2,.inspector-heading h2 { margin:4px 0 0; font-size:17px; font-weight:620; letter-spacing:-.02em; }
.output-note { font-size:11px; color:var(--studio-text-muted); }
.studio-audio-output { min-height:90px; }
.audio-actions { display:grid !important; grid-template-columns:minmax(0,1fr) minmax(120px,auto) auto !important; align-items:center !important; gap:12px !important; }
.audio-actions > * { width:auto !important; min-width:0 !important; flex:none !important; }
.audio-actions .mp3-export { width:100% !important; }
.mp3-export { height:82px !important; min-height:82px !important; max-height:82px !important; overflow:hidden !important; }
.mp3-export .empty { height:78px !important; min-height:78px !important; padding:4px !important; }
.mp3-export .empty .icon svg { width:18px !important; height:18px !important; }
.mp3-export .empty::after { content:"Long-form MP3 export will appear here"; display:block; font-size:11px; color:var(--studio-text-muted); }
.audio-actions .engine-status { font-size:12px !important; color:var(--studio-text-secondary) !important; }
.tts-workspace input[type="radio"] { accent-color:var(--studio-accent) !important; }
.generation-details { font-size:12px; color:var(--studio-text-secondary); }
.tts-inspector { position:sticky !important; top:22px; padding:18px 18px 20px !important; border-left:1px solid var(--studio-border-subtle) !important; background:transparent !important; }
.inspector-heading { margin:0 0 20px; }
.voice-mark { display:flex; gap:11px; align-items:center; margin-bottom:13px; }
.voice-mark>span { width:38px;height:38px;border-radius:12px;display:grid;place-items:center;background:linear-gradient(145deg,#C2B7FF,#7A69D4);color:#171323;font-weight:700; }
.voice-mark b,.voice-mark small { display:block; }
.voice-mark b { font-size:13px; }
.voice-mark small { margin-top:2px;font-size:11px;color:var(--studio-text-muted); }
.tts-inspector .gr-button { border-radius:8px !important; }
.tts-inspector .studio-btn-primary { width:100%; min-height:44px; margin-top:20px; }
.tts-inspector .gradio-radio label { text-transform:none !important; letter-spacing:0 !important; font-size:12px !important; }
.tts-inspector .gradio-radio [role=radio] { padding:6px 8px !important; }
.tts-inspector .gr-accordion { background:transparent !important; border:0 !important; overflow:hidden !important; }
.tts-inspector .inspector-rule { margin:20px 0 14px; }
.gradio-container label span,.gradio-container .gr-form>label { text-transform:none !important; letter-spacing:0 !important; font-size:12px !important; font-weight:550 !important; }
@media(max-width:900px) {
 .main-studio-tabs > .tabitem { padding:24px 22px 40px !important; }
 .tts-workspace { gap:18px !important; }
 .tts-inspector { min-width:230px !important; }
}
@media(max-width:1120px) {
 .tts-workspace { display:flex !important; flex-direction:column !important; }
 .tts-workspace>div { width:100% !important; min-width:0 !important; }
 .tts-inspector { position:static !important; border-left:0 !important; border-top:1px solid var(--studio-border-subtle) !important; padding:20px 0 0 !important; }
}
@media(max-width:820px) {
 .studio-app-header { inset:0 0 auto 0 !important; width:auto !important; height:54px !important; padding:10px 15px !important; border-right:0 !important; border-bottom:1px solid var(--studio-border) !important; }
 .main-studio-tabs > .tab-wrapper { position:fixed !important; left:0 !important; top:54px !important; bottom:auto !important; width:100vw !important; height:56px !important; padding:4px 6px !important; border-right:0 !important; border-bottom:1px solid var(--studio-border) !important; overflow-x:auto !important; overflow-y:hidden !important; }
 .main-studio-tabs > .tab-wrapper > .tab-container { width:max-content !important; min-width:100% !important; height:100% !important; flex-direction:row !important; align-items:center !important; justify-content:flex-start !important; overflow:visible !important; }
 .main-studio-tabs > .tab-wrapper [role="tab"] { width:auto !important; flex:0 0 auto !important; justify-content:center !important; min-height:40px !important; padding:8px 10px !important; font-size:11px !important; }
 .main-studio-tabs > .tabitem { margin:0 !important; width:100% !important; padding:82px 15px 32px !important; }
 .tts-page-head { align-items:flex-start; margin-bottom:18px; }
 .tts-page-head h1 { font-size:25px; }
 .local-status { display:none; }
 .tts-workspace { display:flex !important; flex-direction:column !important; gap:22px !important; }
 .tts-workspace>div { width:100% !important; min-width:0 !important; }
 .script-editor-canvas textarea { min-height:300px !important; height:42vh !important; font-size:16px !important; }
 .audio-actions { grid-template-columns:minmax(0,1fr) auto !important; }
 .audio-actions .mp3-export { grid-column:1 / -1; }
}

/* Batch Queue & Background Monitor */
.queue-toolbar { display: flex !important; gap: 10px !important; margin-bottom: 18px !important; align-items: center !important; }
.queue-toolbar .gr-button { border-radius: 8px !important; font-size: 13px !important; font-weight: 600 !important; }
.pending-jobs-table table, .history-jobs-table table { border-collapse: separate !important; border-spacing: 0 !important; width: 100% !important; border-radius: 10px !important; overflow: hidden !important; }
.opt-in-warning { color: #f59e0b !important; font-size: 12px !important; margin-top: 6px !important; font-weight: 500 !important; }

/* Smart Script Studio — 4-Zone Apple-Inspired Storyboard Workspace */
.smart-script-workspace { max-width: 1460px; margin: 0 auto !important; gap: 20px !important; align-items: flex-start !important; }
.smart-left-nav { background: var(--studio-surface) !important; border: 1px solid var(--studio-border-subtle) !important; border-radius: 14px !important; padding: 16px !important; }
.smart-center-canvas { background: var(--studio-surface) !important; border: 1px solid var(--studio-border-subtle) !important; border-radius: 14px !important; padding: 20px !important; }
.smart-right-inspector { background: var(--studio-surface) !important; border: 1px solid var(--studio-border-subtle) !important; border-radius: 14px !important; padding: 18px !important; }
.smart-bottom-dock { max-width: 1460px; margin: 18px auto 0 !important; background: var(--studio-surface) !important; border: 1px solid var(--studio-border) !important; border-radius: 14px !important; padding: 18px 22px !important; }
.dialogue-block-card { background: var(--studio-surface-card); border: 1px solid var(--studio-border-subtle); border-radius: 10px; padding: 12px 14px; margin-bottom: 10px; }
.dialogue-role-pill { display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: 11px; font-weight: 650; background: var(--studio-accent-subtle); color: var(--studio-accent); margin-right: 8px; }
.production-excluded-box { background: rgba(143, 124, 242, 0.05); border: 1px dashed var(--studio-border); border-radius: 10px; padding: 12px 14px; font-size: 12.5px; color: var(--studio-text-secondary); }
"""
IPHONE_INSPIRED_CSS = STUDIO_PRO_CSS
