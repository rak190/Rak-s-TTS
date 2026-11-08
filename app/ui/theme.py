"""Browser appearance helpers for the persisted Studio theme preference."""
import json


def theme_bootstrap_js(preference: str) -> str:
    """Return the Gradio launch JavaScript that applies the saved appearance."""
    initial = preference if preference in {"system", "light", "dark"} else "system"
    return f"""() => {{
      const preference = {json.dumps(initial)};
      const media = window.matchMedia('(prefers-color-scheme: dark)');
      const state = window.voiceStudioAppearance = {{ preference }};
      state.apply = () => {{
        const dark = state.preference === 'dark' || (state.preference === 'system' && media.matches);
        document.documentElement.classList.toggle('dark', dark);
        document.body?.classList.toggle('dark', dark);
        document.documentElement.dataset.studioAppearance = dark ? 'dark' : 'light';
      }};
      state.apply();
      media.addEventListener?.('change', () => {{ if (state.preference === 'system') state.apply(); }});
    }}"""


def theme_change_js() -> str:
    """Apply a changed Gradio appearance preference before its save callback."""
    return """(preference) => {
      if (window.voiceStudioAppearance) {
        window.voiceStudioAppearance.preference = preference;
        window.voiceStudioAppearance.apply();
      }
      return [preference];
    }"""


def save_theme_preference(preference: str) -> str:
    """Persist a validated theme preference without touching other settings."""
    from app.services.settings_service import SettingsService

    if preference not in {"system", "light", "dark"}:
        return "Choose System, Light, or Dark appearance."
    SettingsService().set_setting("theme", preference)
    return "Appearance saved."
