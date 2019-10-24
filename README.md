[![Build Status](https://dev.azure.com/asottile/asottile/_apis/build/status/asottile.babi?branchName=master)](https://dev.azure.com/asottile/asottile/_build/latest?definitionId=29&branchName=master)
[![Azure DevOps coverage](https://img.shields.io/azure-devops/coverage/asottile/asottile/29/master.svg)](https://dev.azure.com/asottile/asottile/_build/latest?definitionId=29&branchName=master)

babi
====

a text editor, eventually...

### why is it called babi?

I usually use the text editor `nano`, frequently I typo this.  on a qwerty
keyboard, when the right hand is shifted left by one, `nano` becomes `babi`.

### quitting babi

currently you can quit `babi` by using `^X` (or `^C` which triggers a
backtrace).

## demos

not much works yet, here's a few things

### color test (`babi --color-test`)

this is just to demo color support, this test mode will probably be deleted
eventually.  it uses a little trick to invert foreground and background to
get all of the color combinations.  there's one additional color not in this
grid which is the "inverted default"

![](https://i.fluffy.cc/rwdVdMsmZGDZrsT2qVlZHL5Z0XGj9v5v.png)

### file view

this opens the file, displays it, and can be edited in some ways and can save!
movement is currently enabled through the arrow keys, home + `^A`, end + `^E`,
and some key combinations are detected.  unknown keys are displayed as errors
in the status bar.  babi will scroll if the cursor goes off screen either from
resize events or from movement.  babi can edit multiple files.  babi has a
command mode (so you can quit it like vim `:q`!).

![](https://i.fluffy.cc/14Xc4hZg87CBnRBPGgFTKWbQFXFDmmwx.png)

![](https://i.fluffy.cc/wLvTm86lbLnjBgF0WtVQpsxW90QbJwz5.png)

![](https://i.fluffy.cc/RhVmwb8MQkZZbC399GtV99RSH3SB6FTZ.png)

![](https://i.fluffy.cc/dKDd9rBm7hsXVsgZfvXM63gC8QQxJdhk.png)

![](https://i.fluffy.cc/PQq1sqpcx59tWNFGF4nThQH1gSVHjVCn.png)

![](https://i.fluffy.cc/KfGg7NhNTTH5X4ZsxdsMt72RVg5nR79H.png)
