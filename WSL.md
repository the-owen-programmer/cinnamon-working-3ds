# How to build on Windows using WSL
# UNTESTED, should work.

WSL (Windows Subsystem for Linux) lets you run Linux directly inside Windows. It's the easiest way to build this project on windows.
## 1. Install WSL

Go to your search bar and search for **Powershell** then **right click** and **Run as Administrator**

A blueish window with a text prompt should pop up.

Type this command into the window.

```powershell
wsl --install
```
Follow any on-screen instructions

# 2. After installing

Check installed distros:

```powershell
wsl --list --verbose
```

## 3. Install a Linux distro

Ubuntu is recommended, but if you know what your doing you can choose a lighter distro.

See available distros:

```powershell
wsl --list --online
```

install any of them, if you do not know just run this command.

```powershell
wsl --install -d Ubuntu-24.04
```

## 4. First launch

Open **Ubuntu** from the Start Menu.

It will ask you to create:

* username
* password

This account is separate from your windows login, set it to anything you want, but you will **NEED** to remember.

## 4.5. common Linux commands
This **CAN** be skipped.
Some basic commands are as follows.

List current folder
```bash
ls
```

List any folder, for example the C drive.

```bash
ls /mnt/c
```

Open a folder, for example again, the C drive.
```bash
cd /mnt/c
```

Follow a proper tutorial if you **WANT** to learn more linux commands.

## 5. Access Windows files from Linux

Your Windows drive is here:

```bash
ls /mnt/c
```

Example:

*Replace "YourName" with your **windows** username*

```bash
ls /mnt/c/Users/YourName/Desktop
```

## 6. Use Docker with WSL

Copy and paste these commands **EXACTLY**
*Use CTRL+SHIFT+V to paste in the command prompt*

```bash
# Add Docker's official GPG key:
sudo apt update
sudo apt install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

## 7. Build Cinnamon

Inside WSL:

```bash
cd /mnt/c
mkdir -p cinnamon
cd cinnamon
mkdir -p workspace
cd workspace
docker run -it --rm -v "$PWD:/workspace" -w /workspace kurplunk/cinnamon-3ds-builder
```

## 8. Install on your 3DS!
The 3dsx should appear in C:/cinnamon/workspace/output/

Copy this 3dsx to your Sd Card *for example D:/*

D:/3ds/

Undertale should show up in your Homebrew folder.
