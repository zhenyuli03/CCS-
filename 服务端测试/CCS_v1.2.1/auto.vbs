DIM objShell
set objShell=wscript.createObject("wscript.shell")
iReturn=objShell.Run("cmd.exe /C D:\CCS\v3start.py", 0, TRUE)