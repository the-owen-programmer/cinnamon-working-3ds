# Cinnamon working 3DS
A fork of cinnamon (my old project) with stable 3DS support.

# How to build stable using docker?
Copy the **ENTIRE** Undertale folder to
/romfs/cinnamon/data.win after the first command

Run these commands, use WSL on Windows.

Linux
```bash
git clone https://github.com/KurplunkVR/cinnamon-working-3ds.git
cd cinnamon-working-3ds
docker compose up
```

WSL
```bash
sudo git clone https://github.com/KurplunkVR/cinnamon-working-3ds.git
cd cinnamon-working-3ds
sudo docker compose up
```



# How to use WSL? (Windows)
This is more complicated, but I have provided full instructions with commands you can just copy and paste into your Command Prompt!
[WSL Setup](WSL.md)
