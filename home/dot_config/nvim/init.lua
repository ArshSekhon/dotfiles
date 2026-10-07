-- Fast review/editing defaults. Installs and updates happen during bootstrap.
-- Edit the repository source to keep changes across chezmoi applications.
vim.g.mapleader = " "
vim.g.maplocalleader = ","

local opt = vim.opt
opt.number = true
opt.cursorline = true
opt.wrap = false
opt.scrolloff = 4
opt.sidescrolloff = 4
opt.splitbelow = true
opt.splitright = true
opt.ignorecase = true
opt.smartcase = true
opt.inccommand = "split"
opt.wildmode = "longest:full,full"
opt.termguicolors = true
opt.laststatus = 3
opt.statusline = " %<%f %m%r%=%l:%c  %p%% "
opt.signcolumn = "yes" -- Diagnostics/Git signs do not shift the text sideways.
opt.synmaxcol = 300 -- Bound syntax work on generated/minified lines.
vim.cmd.colorscheme("habamax")

-- Filetype defaults and native EditorConfig can override this fallback.
opt.expandtab = true
opt.tabstop = 4
opt.shiftwidth = 4
opt.softtabstop = -1

-- Keep undo outside checkouts; retain native swap/crash recovery.
local undo = vim.fn.stdpath("state") .. "/undo"
vim.fn.mkdir(undo, "p", 448) -- 0700 for newly created private directories.
opt.undodir = undo .. "//"
opt.undofile = true

local map = vim.keymap.set
map("n", "<Esc>", "<Cmd>nohlsearch<CR>", { desc = "Clear search highlights" })
map("n", "<leader>w", "<Cmd>write<CR>", { desc = "Save file" })
map("n", "<leader>q", "<Cmd>quit<CR>", { desc = "Close window" })
map("n", "<leader>e", "<Cmd>Explore<CR>", { desc = "Browse files" })
map("n", "<leader>fo", ":edit ", { desc = "Open file (Tab completes paths)" })
map("n", "<leader>vc", function()
  vim.cmd.edit(vim.fn.fnameescape(vim.fn.stdpath("config") .. "/init.lua"))
end, { desc = "Open installed Neovim config" })
map("n", "<leader>vl", function()
  vim.cmd.edit(vim.fn.fnameescape(vim.fn.stdpath("config") .. "/lua/dotfiles/languages.lua"))
end, { desc = "Open language configuration" })
map("n", "<leader>?", "<Cmd>help dotfiles<CR>", { desc = "Open Neovim cheatsheet" })
for key, direction in pairs({ h = "h", j = "j", k = "k", l = "l" }) do
  map("n", "<C-" .. key .. ">", "<C-w>" .. direction, { desc = "Move to split " .. direction })
end

local events = vim.api.nvim_create_augroup("DotfilesEditor", { clear = true })
vim.api.nvim_create_autocmd("FileType", {
  group = events,
  pattern = "help",
  callback = function(event)
    map("n", "q", "<Cmd>quit<CR>", { buffer = event.buf, desc = "Close help" })
  end,
  desc = "Close the cheatsheet or native help with q",
})
opt.autoread = true
vim.api.nvim_create_autocmd({ "FocusGained", "BufEnter" }, {
  group = events,
  command = "checktime",
  desc = "Notice external changes when returning to a file",
})
if vim.fn.executable("rg") == 1 then
  opt.grepprg = "rg --vimgrep --smart-case"
  opt.grepformat = "%f:%l:%c:%m"
  map("n", "<leader>/", ":silent grep! ", { desc = "Search project (ripgrep)" })
  vim.api.nvim_create_autocmd("QuickFixCmdPost", {
    group = events,
    pattern = "grep",
    command = "cwindow",
    desc = "Show project search results",
  })
end

-- Copy explicitly over SSH; ordinary yanks/pastes use native registers.
-- Load OSC 52 only on demand and never query the remote clipboard.
if (vim.env.SSH_CONNECTION or vim.env.SSH_TTY) and vim.fn.exists("*getregion") == 1 then
  local function copy(lines)
    require("vim.ui.clipboard.osc52").copy("+")(lines)
  end
  map("n", "<leader>y", function()
    local row = vim.api.nvim_win_get_cursor(0)[1] - 1
    copy(vim.api.nvim_buf_get_lines(0, row, row + vim.v.count1, false))
  end, { desc = "Copy line(s) to device clipboard" })
  map("x", "<leader>y", function()
    copy(vim.fn.getregion(vim.fn.getpos("v"), vim.fn.getpos("."), {
      type = vim.fn.mode(),
      exclusive = vim.o.selection == "exclusive",
    }))
    vim.api.nvim_feedkeys("\27", "n", false)
  end, { desc = "Copy selection to device clipboard" })
else
  map("n", "<leader>y", '"+yy', { desc = "Copy line(s) to system clipboard" })
  map("x", "<leader>y", '"+y', { desc = "Copy selection to system clipboard" })
end

-- Native highlighting includes Markdown fences and standalone Mermaid files.
-- A fence alias (left) selects its built-in syntax file (right).
vim.g.markdown_fenced_languages = {
  "java", "javascript", "js=javascript", "typescript", "ts=typescript",
  "jsx=javascriptreact", "tsx=typescriptreact", "rust", "python", "html", "mermaid",
}
vim.filetype.add({ extension = { mmd = "mermaid", mermaid = "mermaid" } })
require("dotfiles.languages")
require("dotfiles.plugins")

-- Unmanaged machine/employer preferences stay outside the repository.
local override = vim.fn.stdpath("config") .. "/init.local.lua"
if vim.fn.filereadable(override) == 1 then
  dofile(override)
end
