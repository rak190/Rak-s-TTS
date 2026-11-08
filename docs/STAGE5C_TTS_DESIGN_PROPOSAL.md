# VoiceStudio Pro — TTS design proposal

## Audit

The supplied Stage 5C screenshots show a centered web page with a full-width brand strip and a horizontal row of tabs. The TTS screen repeats that header inside the page, wraps the editor and playback in multiple bordered boxes, and gives the voice inspector nearly a third of the work area. Technical badges compete with the script for attention. The 1440px screenshot shows only the upper part of the editor because the controls and nested containers consume vertical space. The 390px screenshot is a compressed desktop tab layout, not a task-specific mobile arrangement. No `design-references` directory is present; the supplied screenshots were reviewed.

## Two directions considered

1. **Narration desk** — a compact left navigation rail, open script canvas, contextual voice inspector, and a real audio output area directly below the script. This keeps the writing task dominant and makes voice controls available without giving them equal visual weight.
2. **Chapter timeline** — a project/chapter list at left, script and waveform tracks in the center, and clip properties at right. This is strong for assembled long-form productions but would add an empty or decorative timeline before audio exists and reduce the space available to compose a new script.

The narration desk is selected for this personal speech workstation. It borrows the script-first workflow and paragraph-level settings model documented for ElevenCreative Studio, the quiet navigation and restrained surface contrast visible in Linear, and Descript's close relationship between text and playback. It uses its own spacing, components, labels, and lavender accent rather than reproducing those products.

## Specification

- **Navigation:** persistent 218px desktop rail with the existing seven destinations; active tab uses a restrained lavender marker. Below 700px the rail becomes a horizontally scrollable bottom bar.
- **Workspace:** title and local status at top, writing column at left, contextual voice/delivery controls at right. The inspector stacks below the script on mobile.
- **Editor:** project title, language-aware live character summary, open multiline script surface, Standard/Long-form workflow, and expandable chapter preview.
- **Output:** native Gradio audio control and MP3 export appear below the editor. No waveform is drawn before real audio is generated.
- **Inspector:** saved voice profile, refresh action, generation mode, collapsed guidance/timestep controls, and primary Generate speech action.
- **Color:** dark base `#0B0D12`, sidebar `#11131A`, surface `#181B24`, elevated surface `#222634`, hairline `#2C303F`, primary text `#F6F7FB`, secondary text `#9FA4B5`, lavender accent `#8F7CF2`, success `#58C9A1`. Existing light tokens remain available through Gradio's light theme selector.
- **Type:** system/Segoe UI/Inter fallbacks with Khmer-capable fallbacks; 30px page title, 17px script, 14px body, relaxed 1.82 editor line-height for bilingual text.
- **Component treatment:** quiet labels, fewer enclosing borders, one primary action, native audio controls, status text rather than colored label badges.

## Interaction and scope

The existing standard generation callback, voice refresh, mode selector, cancellation, and sentence-aware chunk analysis remain wired. A long-form action now invokes the existing checkpoint-aware synthesis callback and exposes WAV playback plus MP3 export. The existing audio component remains the source of truth; no illustrative waveform is presented as generated data. This pass changes the TTS page and shared shell only. Other six pages remain on the existing composition until the TTS layout is reviewed.
