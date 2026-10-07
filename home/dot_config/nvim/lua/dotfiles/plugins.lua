-- Optional native packages: load on a shortcut, never download during startup.
-- Install under stdpath('data')/site/pack/dotfiles/opt; no plugin manager is needed.
local loaded = {}
local function load(package, module, options)
  if loaded[package] then
    return loaded[package]
  end
  local ok = pcall(vim.cmd.packadd, package)
  if not ok then
    vim.notify(package .. " is missing; see BOOTSTRAP.md", vim.log.levels.WARN)
    return
  end
  local found, plugin = pcall(require, module)
  if not found then
    vim.notify(package .. " is missing or could not load; see BOOTSTRAP.md", vim.log.levels.WARN)
    return
  end
  plugin.setup(options)
  loaded[package] = plugin
  return plugin
end

local function picker(method)
  return function()
    local fzf = load("fzf-lua", "fzf-lua", {
      winopts = { height = 0.85, width = 0.9, preview = { hidden = true } },
      file_icons = false, git_icons = false, color_icons = false,
      files = { cmd = "rg --files --hidden -g '!.git'" },
      grep = { rg_opts = "--column --line-number --no-heading --color=always --smart-case --hidden -g '!.git'" },
      keymap = { fzf = { ["ctrl-j"] = "down", ["ctrl-k"] = "up", ["ctrl-/"] = "toggle-preview" } },
    })
    if fzf then
      -- Search the checkout containing this file; standalone files use current cwd.
      fzf[method]({ cwd = vim.fs.root(0, { ".git" }) or vim.fn.getcwd() })
    end
  end
end
local map = vim.keymap.set
map("n", "<C-p>", picker("files"), { desc = "Find project files" })
for key, action in pairs({
  ff = { "files", "Find project files" },
  fg = { "live_grep_native", "Search project text" }, -- fzf reloads rg directly.
  fb = { "buffers", "Find open buffers" },
  fr = { "oldfiles", "Find recently opened files" },
  fs = { "lsp_document_symbols", "Find file symbols" },
  fS = { "lsp_live_workspace_symbols", "Search workspace symbols" },
  gf = { "git_status", "Find changed Git files" },
}) do
  map("n", "<leader>" .. key, picker(action[1]), { desc = action[2] })
end

-- Flash labels the matches as you type. Keep /, f/t and native s unchanged.
map({ "n", "x", "o" }, "<leader>j", function()
  local flash = load("flash.nvim", "flash", {
    modes = { search = { enabled = false }, char = { enabled = false } },
  })
  if flash then flash.jump() end
end, { desc = "Jump to a labeled match" })

-- Git signs/diff work starts only when requested; watchers are event based.
map("n", "<leader>gg", function()
  load("gitsigns.nvim", "gitsigns", {
    update_debounce = 200,
    max_file_length = 20000,
    on_attach = function(bufnr)
      local gs = require("gitsigns")
      map("n", "<leader>gh", gs.preview_hunk, { buffer = bufnr, desc = "Preview changed hunk" })
      for key, direction in pairs({ ["]c"] = "next", ["[c"] = "prev" }) do
        map("n", key, function()
          if vim.wo.diff then
            vim.cmd.normal({ key, bang = true })
          else
            gs.nav_hunk(direction)
          end
        end, { buffer = bufnr, desc = "Go to " .. direction .. " changed hunk" })
      end
    end,
  })
end, { desc = "Enable Git signs and hunk navigation" })

-- Explicit formatting only; Conform preserves cursor/marks with minimal edits.
map({ "n", "x" }, "<leader>=", function()
  local conform = load("conform.nvim", "conform", {
    formatters_by_ft = {
      javascript = { "prettier" }, javascriptreact = { "prettier" },
      typescript = { "prettier" }, typescriptreact = { "prettier" },
      html = { "prettier" }, markdown = { "prettier" },
      python = { "ruff_format" }, rust = { "rustfmt" },
      java = { lsp_format = "fallback" },
    },
    default_format_opts = { lsp_format = "fallback", timeout_ms = 2000 },
  })
  if conform then conform.format({ async = true }) end
end, { desc = "Format file or visual selection" })
