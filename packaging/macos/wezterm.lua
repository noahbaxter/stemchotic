-- Single-purpose host config for Stemchotic (prove-it build).
-- The app renders with truecolor SGR, so colors here are just window chrome.
-- Generalization (env-driven, per-app palette from the chotic-ui theme) is Plan 3.
local wezterm = require 'wezterm'
local config = wezterm.config_builder()

config.initial_cols = 90
config.initial_rows = 40
config.enable_tab_bar = false
config.window_close_confirmation = 'NeverPrompt'
config.exit_behavior = 'Close'
config.window_padding = { left = '1cell', right = '1cell', top = '0.5cell', bottom = '0.5cell' }
config.font = wezterm.font 'JetBrains Mono'
config.font_size = 13.0

-- kanagawa-ish window chrome to match stemchotic's default theme
config.colors = {
  foreground = '#dcd7ba',
  background = '#1f1f28',
  cursor_bg = '#c8c093',
  cursor_fg = '#1f1f28',
}

return config
