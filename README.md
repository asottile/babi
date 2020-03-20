[![Build Status](https://dev.azure.com/asottile/asottile/_apis/build/status/asottile.babi?branchName=master)](https://dev.azure.com/asottile/asottile/_build/latest?definitionId=29&branchName=master)
[![Azure DevOps coverage](https://img.shields.io/azure-devops/coverage/asottile/asottile/29/master.svg)](https://dev.azure.com/asottile/asottile/_build/latest?definitionId=29&branchName=master)

babi
====

a text editor, eventually...

### why is it called babi?

I usually use the text editor `nano`, frequently I typo this.  on a qwerty
keyboard, when the right hand is shifted left by one, `nano` becomes `babi`.

### quitting babi

currently you can quit `babi` by using <kbd>^X</kbd> (or via <kbd>esc</kbd> +
<kbd>:q</kbd>).

### key combinations

these are all of the current key bindings in babi

- <kbd>^S</kbd>: save
- <kbd>^O</kbd>: save as
- <kbd>^X</kbd>: quit
- <kbd>^P</kbd>: open file
- arrow keys: movement
- <kbd>^A</kbd> / <kbd>home</kbd>: move to beginning of line
- <kbd>^E</kbd> / <kbd>end</kbd>: move to end of line
- <kbd>^Y</kbd> / <kbd>pageup</kbd>: move up one page
- <kbd>^V</kbd> / <kbd>pagedown</kbd>: move down one page
- <kbd>^-left</kbd> / <kbd>^-right</kbd>: jump by word
- <kbd>^-home</kbd> / <kbd>^-end</kbd>: jump to beginning / end of file
- <kbd>^_</kbd>: jump to line number
- selection: <kbd>shift</kbd> + ...: extend the current selection
    - arrow keys
    - <kbd>home</kbd> / <kbd>end</kdb>
    - <kbd>pageup</kbd> / <kbd>pagedown</kbd>
    - <kbd>^-left</kbd> / <kbd>^-right</kbd>
    - <kbd>^-end</kbd> / <kbd>^-home</kbd>
- <kbd>tab</kbd> / <kbd>shift-tab</kbd>: indent or dedent current line (or
  selection)
- <kbd>^K</kbd> / <kbd>^U</kbd>: cut and uncut the current line (or selection)
- <kbd>M-u</kbd> / <kbd>M-U</kbd>: undo / redo
- <kbd>^W</kbd>: search
- <kbd>^\\</kbd>: search and replace
- <kbd>^C</kbd>: show the current position in the file
- <kbd>^-up</kbd> / <kbd>^-down</kbd>: scroll screen by a single line
- <kbd>M-left</kbd> / <kbd>M-right</kbd>: go to previous / next file
- <kbd>^Z</kbd>: background
- <kbd>esc</kbd>: open the command mode
    - <kbd>:q</kbd>: quit
    - <kbd>:w</kbd>: write the file
    - <kbd>:wq</kbd>: write the file and quit
    - <kbd>:sort</kbd>: sort the file (or selection)

in prompts (search, search replace, command):
- <kbd>^C</kbd>: cancel
- <kbd>^K</kbd>: cut to end
- <kbd>^R</kbd>: reverse search

### setting up syntax highlighting

the syntax highlighting setup is a bit manual right now

1. from a clone of babi, run `./bin/download-syntax` -- you will likely need
   to install some additional packages to download them (`pip install cson`)
2. find a visual studio code theme, convert it to json (if it is not already
   json) and put it at `~/.config/babi/theme.json`.  a helper script is
   provided to make this easier: `./bin/download-theme NAME URL`

## demos

most things work!  here's a few screenshots

### file view

this opens the file, displays it, and can be edited and can save! unknown keys
are displayed as errors in the status bar.  babi will scroll if the cursor
goes off screen either from resize events or from movement.  babi can edit
multiple files.  babi has a command mode (so you can quit it like vim
<kbd>:q</kbd>!).  babi also support syntax highlighting

![](https://i.fluffy.cc/5WFZBJ4mWs7wtThD9strQnGlJqw4Z9KS.png)

![](https://i.fluffy.cc/qrNhgCK34qKQ6tw4GHLSGs4984Qqnqh7.png)

![](https://i.fluffy.cc/DKlkjnZ4tgfnxH7cxjnLcB7GkBVdW35v.png)

![](https://i.fluffy.cc/VqHWHfWNW73sppZlHv0C4lw63TVczZfZ.png)

![](https://i.fluffy.cc/p8lv61TCql1MJfpBDqbNPWPf27lmGWFN.png)

![](https://i.fluffy.cc/ZH5sswB4FSbpW8FfcXL1KZWdJnjxRkbW.png)

![](https://i.fluffy.cc/Rw8nZKFC3R36mNrV01fL2gk4rfwWn7wX.png)

![](https://i.fluffy.cc/FSD92ZVN4xcMFPv1V7gc0Xzk8TCQTgdg.png)
