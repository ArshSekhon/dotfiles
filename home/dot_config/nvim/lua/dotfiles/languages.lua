-- Native LSP, Neovim 0.11+. Servers are installed separately on PATH.
-- One client is reused per server/project; missing tools leave native editing usable.
if vim.fn.has("nvim-0.11") == 0 then
  return
end

vim.opt.completeopt = { "menu", "menuone", "noselect", "popup" }
vim.diagnostic.config({
  underline = true,
  signs = true,
  severity_sort = true,
  update_in_insert = false,
  virtual_text = false, -- Keep review text clear; Space d shows the details.
})

-- Prefer a project marker, then its Git checkout. Standalone files use their folder.
-- Skip large/generated buffers instead of making a language server index them.
local function root(markers)
  return function(bufnr, on_dir)
    local name = vim.api.nvim_buf_get_name(bufnr)
    if name == "" or vim.fn.getfsize(name) > 1024 * 1024
      or vim.api.nvim_buf_line_count(bufnr) > 20000 then
      return
    end
    on_dir(vim.fs.root(bufnr, markers) or vim.fs.dirname(name))
  end
end

local servers = {
  ts_ls = {
    cmd = { "typescript-language-server", "--stdio" },
    filetypes = { "javascript", "javascriptreact", "typescript", "typescriptreact" },
    root_dir = root({ "tsconfig.json", "jsconfig.json", "package.json", ".git" }),
    init_options = {
      disableAutomaticTypingAcquisition = true,
      tsserver = { useSyntaxServer = "never" }, -- One TS worker per project.
    },
  },
  pyright = {
    cmd = { "pyright-langserver", "--stdio" },
    filetypes = { "python" },
    root_dir = root({ "pyrightconfig.json", "pyproject.toml", "setup.py", ".git" }),
    settings = { python = { analysis = {
      diagnosticMode = "openFilesOnly", -- Avoid checking the whole agent checkout.
      typeCheckingMode = "basic",
      autoSearchPaths = true,
    } } },
  },
  rust_analyzer = {
    cmd = { "rust-analyzer" },
    filetypes = { "rust" },
    root_dir = root({ "Cargo.toml", "rust-project.json", ".git" }),
    settings = { ["rust-analyzer"] = {
      cargo = { extraArgs = { "--offline" }, buildScripts = { enable = false } },
      procMacro = { enable = false },
      checkOnSave = false, -- Run cargo check deliberately; no builds per save.
    } },
  },
  html = {
    cmd = { "vscode-html-language-server", "--stdio" },
    filetypes = { "html" },
    root_dir = root({ "package.json", ".git" }),
  },
  marksman = {
    cmd = { "marksman", "server" },
    filetypes = { "markdown" },
    root_dir = root({ ".marksman.toml", ".git" }),
  },
  jdtls = {
    -- JDT locks its workspace: separate both checkouts and simultaneous editors.
    -- Generated indexes are disposable cache, while undo stays in durable state.
    cmd = function(dispatchers, config)
      local workspace = vim.fn.stdpath("cache") .. "/jdtls/"
        .. vim.fn.sha256(config.root_dir) .. "/" .. vim.fn.getpid()
      vim.fn.mkdir(workspace, "p", 448)
      return vim.lsp.rpc.start({ "jdtls", "-data", workspace }, dispatchers)
    end,
    filetypes = { "java" },
    root_dir = root({ "pom.xml", "build.gradle", "build.gradle.kts", ".git" }),
    settings = { java = {
      autobuild = { enabled = false },
      configuration = { updateBuildConfiguration = "disabled" },
      import = {
        gradle = { offline = { enabled = true }, wrapper = { enabled = false } },
        maven = { offline = { enabled = true } },
      },
      maven = { downloadSources = false },
      eclipse = { downloadSources = false },
    } },
  },
}

local available = {}
for name, config in pairs(servers) do
  vim.lsp.config(name, config)
  local executable = name == "jdtls" and "jdtls" or config.cmd[1]
  if vim.fn.executable(executable) == 1 then
    available[#available + 1] = name
    vim.lsp.enable(name)
  end
end

-- Release language-server resources when doing a plain review; toggle again to attach.
vim.keymap.set("n", "<leader>lt", function()
  local enable = true
  for _, name in ipairs(available) do
    if vim.lsp.is_enabled(name) then enable = false; break end
  end
  vim.lsp.enable(available, enable)
  vim.notify("Language services " .. (enable and "enabled" or "disabled"))
end, { desc = "Toggle installed language services" })

vim.api.nvim_create_autocmd("LspAttach", {
  group = vim.api.nvim_create_augroup("DotfilesLsp", { clear = true }),
  desc = "Native completion and language navigation for attached buffers",
  callback = function(event)
    local client = vim.lsp.get_client_by_id(event.data.client_id)
    if client and client:supports_method("textDocument/completion") then
      -- Trigger on server-defined punctuation; Ctrl+Space requests completion anytime.
      vim.lsp.completion.enable(true, client.id, event.buf, { autotrigger = true })
      vim.keymap.set("i", "<C-Space>", vim.lsp.completion.get,
        { buffer = event.buf, desc = "Request language completion" })
    end
    vim.keymap.set("n", "gd", vim.lsp.buf.definition,
      { buffer = event.buf, desc = "Go to definition" })
  end,
})

vim.keymap.set("n", "<leader>d", vim.diagnostic.open_float, { desc = "Show line diagnostics" })
-- Native defaults: K hover, grr references, grn rename, gra actions, gri implementation,
-- grt type definition, gO symbols, [d/]d diagnostics, Ctrl+O/Ctrl+I jump history.
