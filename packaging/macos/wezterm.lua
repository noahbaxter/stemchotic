-- Single-purpose host config for Stemchotic.
-- The app renders with truecolor SGR, so colors here are just window chrome.
local wezterm = require 'wezterm'
local config = wezterm.config_builder()

-- Remember the window size across launches. WezTerm has no built-in
-- persistence, so we save the cell size whenever the window is resized and
-- read it back here at startup. Falls back to a sensible default first run.
local DEFAULT_COLS, DEFAULT_ROWS = 90, 30

local function size_file()
  local appdata = os.getenv('LOCALAPPDATA')
  if appdata then return appdata .. '\\Stemchotic\\Data\\window.txt' end   -- Windows
  local home = os.getenv('HOME') or '.'
  return home .. '/Library/Application Support/Stemchotic/window.txt'       -- macOS
end

local cols, rows = DEFAULT_COLS, DEFAULT_ROWS
do
  local f = io.open(size_file(), 'r')
  if f then
    local c = tonumber(f:read('l') or '')
    local r = tonumber(f:read('l') or '')
    f:close()
    -- guard against a corrupt/absurd saved value
    if c and r and c >= 60 and c <= 400 and r >= 20 and r <= 200 then
      cols, rows = c, r
    end
  end
end
config.initial_cols = cols
config.initial_rows = rows

wezterm.on('window-resized', function(_window, pane)
  local dims = pane:get_dimensions()
  local f = io.open(size_file(), 'w')
  if f then
    f:write(tostring(dims.cols) .. '\n' .. tostring(dims.viewport_rows) .. '\n')
    f:close()
  end
end)

config.enable_tab_bar = false
config.window_close_confirmation = 'NeverPrompt'
config.exit_behavior = 'Close'
config.window_padding = { left = '1cell', right = '1cell', top = '0.5cell', bottom = '0.5cell' }
config.font = wezterm.font 'JetBrains Mono'
-- MUST stay 12.0: any other size triggers WezTerm's window-doubling bug on
-- non-Retina external monitors (wezterm/wezterm#4851), which blows initial_cols
-- / initial_rows up to ~2x and ignores the intended size. At 12 the window is
-- exactly initial_cols x initial_rows on every display tested.
config.font_size = 12.0

-- kanagawa-ish window chrome to match stemchotic's default theme
config.colors = {
  foreground = '#dcd7ba',
  background = '#1f1f28',
  cursor_bg = '#c8c093',
  cursor_fg = '#1f1f28',
}

return config
