-- Neovim 0.12 enables Markdown Treesitter by default, but fence parsers are
-- separate assets. Use native syntax here so every configured fence, including
-- Mermaid, is highlighted without parser installation or startup downloads.
pcall(vim.treesitter.stop, 0)
vim.bo.syntax = "markdown"
